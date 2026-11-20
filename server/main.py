from typing import List, Literal
from pathlib import Path
from html import escape
import mimetypes
from threading import Event, Thread
import time

from fastapi import APIRouter, Depends, FastAPI, HTTPException, UploadFile, Response, Request, Header
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from flatnotes import api_messages
from flatnotes.attachments.base import BaseAttachments
from flatnotes.attachments.models import AttachmentCreateResponse
from flatnotes.auth.base import BaseAuth
from flatnotes.auth.models import Login, Token
from flatnotes.global_config import AuthType, GlobalConfig, GlobalConfigResponseModel
from flatnotes.helpers import replace_base_href
from flatnotes.notes.base import BaseNotes
from flatnotes.notes.models import Note, NoteCreate, NoteUpdate, SearchResult
from flatnotes.publications import PublicationStore, SlugConflictError, content_revision
from flatnotes.encrypted_storage import EncryptedNoteStore, EncryptedPublicationStore
from flatnotes.expiration import ExpirationStore, ExpirationError, parse_policy
from flatnotes.expiration_models import ExpirationSettings, SingleViewProof
from flatnotes.helpers import is_valid_filename
from flatnotes.publication_models import PublicationSettings, PublicationInfo, PublicNote, PublicNoteUpdate

global_config = GlobalConfig()
auth: BaseAuth = global_config.load_auth()
note_storage: BaseNotes = global_config.load_note_storage()
attachment_storage: BaseAttachments = global_config.load_attachment_storage()
publication_store = PublicationStore(note_storage.storage_path)
encrypted_store = EncryptedNoteStore(note_storage.storage_path)
encrypted_publications = EncryptedPublicationStore(publication_store)
expiration_store = ExpirationStore(publication_store)
note_storage.is_indexable = expiration_store.is_indexable
note_storage._sync_index_with_retry()
expiration_store.cleanup(note_storage, encrypted_store, encrypted_publications)
cleanup_stopped = Event()


def cleanup_expired_notes():
    while not cleanup_stopped.wait(60):
        try:
            expiration_store.cleanup(note_storage, encrypted_store, encrypted_publications)
        except Exception:
            from flatnotes.logger import logger
            logger.exception("Expiration cleanup failed; retrying")


auth_deps = [Depends(auth.authenticate)] if auth else []
router = APIRouter()
app = FastAPI(
    docs_url=global_config.path_prefix + "/docs",
    openapi_url=global_config.path_prefix + "/openapi.json",
)
FRONTEND_DIR = Path(__file__).resolve().parent / "web" / "dist"


@app.on_event("startup")
def start_cleanup():
    cleanup_stopped.clear()
    Thread(target=cleanup_expired_notes, daemon=True, name="flatnotes-expiration").start()


@app.on_event("shutdown")
def stop_cleanup():
    cleanup_stopped.set()


def ensure_active(kind, note_id, db=None):
    try:
        expiration_store.ensure_available(kind, note_id, db)
    except ExpirationError:
        raise HTTPException(410, "Note has expired or has already been viewed")


def require_expiration_writes():
    if not global_config.expiration_enabled or global_config.auth_type == AuthType.READ_ONLY:
        raise HTTPException(403, "Expiration configuration is disabled")


def selected_expiration(policy):
    value = policy if policy is not None else (
        global_config.expiration_default if global_config.expiration_enabled else "none"
    )
    if not global_config.expiration_enabled and value != "none":
        raise HTTPException(403, "Expiration configuration is disabled")
    try:
        parse_policy(value)
    except ValueError as error:
        raise HTTPException(422, str(error))
    return value



# region UI
@router.get("/", include_in_schema=False)
@router.get("/login", include_in_schema=False)
@router.get("/search", include_in_schema=False)
@router.get("/new", include_in_schema=False)
@router.get("/encrypted", include_in_schema=False)
@router.get("/expiring", include_in_schema=False)
@router.get("/note/{title}", include_in_schema=False)
@router.get("/n/{title}", include_in_schema=False)
@router.get("/e/{id}", include_in_schema=False)
@router.get("/p/{slug}", include_in_schema=False)
def root(request: Request, title: str = ""):
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    html = replace_base_href(html, global_config.path_prefix)
    html = html.replace("<title>flatnotes</title>", f"<title>{escape(global_config.site_title)}</title>")
    headers = {}
    is_public = request.url.path.startswith(global_config.path_prefix + "/p/")
    is_encrypted = request.url.path.startswith(global_config.path_prefix + "/e/")
    if is_public:
        slug = request.url.path.rsplit("/", 1)[-1]
        is_encrypted = encrypted_publications.get(slug=slug) is not None
    if is_public or is_encrypted:
        image_sources = "img-src 'self' data: blob:; " if is_encrypted else "img-src 'self' data: https:; "
        headers = {
            "Content-Security-Policy": (
                "default-src 'self' data:; "
                "script-src 'self' 'wasm-unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                + image_sources +
                "worker-src 'self' blob:; "
                "connect-src 'self'; object-src 'none'; "
                "frame-src 'none'; frame-ancestors 'none'; base-uri 'self'"
            ),
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex",
        }
    return HTMLResponse(content=html, headers=headers)


# endregion


# region Auth
if global_config.auth_type not in [AuthType.NONE, AuthType.READ_ONLY]:

    @router.post("/api/token", response_model=Token)
    def token(data: Login):
        try:
            return auth.login(data)
        except ValueError:
            raise HTTPException(
                status_code=401, detail=api_messages.login_failed
            )


@router.get("/api/auth-check", dependencies=auth_deps)
def auth_check() -> str:
    """A lightweight endpoint that simply returns 'OK' if the user is
    authenticated."""
    return "OK"


# endregion


# region Notes
# Get Note
@router.get(
    "/api/notes/{title}",
    dependencies=auth_deps,
    response_model=Note,
)
def get_note(title: str):
    """Claim a single view atomically before returning plaintext."""
    try:
        with publication_store.connection(write=True) as db:
            ensure_active("plain", title, db)
            note = note_storage.get(title)
            state = expiration_store.get("plain", title, db)
            token = expiration_store.consume("plain", title, db=db, allow_session=True)
            note.expiration = state
            note.view_token = token
            return note
    except ValueError:
        raise HTTPException(
            status_code=400, detail=api_messages.invalid_note_title
        )
    except FileNotFoundError:
        raise HTTPException(404, api_messages.note_not_found)


if global_config.auth_type != AuthType.READ_ONLY:

    # Create Note
    @router.post(
        "/api/notes",
        dependencies=auth_deps,
        response_model=Note,
    )
    def post_note(note: NoteCreate):
        """Create an ordinary note and its expiration policy."""
        policy = selected_expiration(note.expiration)
        created = None
        try:
            with publication_store.connection(write=True) as db:
                created = note_storage.create(note)
                expiration_store.remove("plain", note.title, db)
                if policy != "none":
                    expiration_store.set("plain", note.title, policy, db=db)
                created.expiration = expiration_store.get("plain", note.title, db)
            note_storage._sync_index_with_retry()
            return created
        except Exception:
            if created is not None:
                try:
                    note_storage.delete(created.title)
                except OSError:
                    pass
            raise
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=api_messages.invalid_note_title,
            )
        except FileExistsError:
            raise HTTPException(
                status_code=409, detail=api_messages.note_exists
            )

    # Update Note
    @router.patch(
        "/api/notes/{title}",
        dependencies=auth_deps,
        response_model=Note,
    )
    def patch_note(title: str, data: NoteUpdate):
        try:
            with publication_store.connection(write=True) as db:
                ensure_active("plain", title, db)
                current_publication = publication_store.get_by_title(title, db)
                updated = note_storage.update(title, data)
                if updated.title != title:
                    expiration_store.rename("plain", title, updated.title, db)
                updated.expiration = expiration_store.get("plain", updated.title, db)
                if current_publication:
                    if updated.title != title:
                        publication_store.rename(title, updated.title, db)
                    if data.new_content is not None:
                        publication_store.sync_attachments(
                            current_publication["id"], updated.content or "", db
                        )
                return updated
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=api_messages.invalid_note_title,
            )
        except FileExistsError:
            raise HTTPException(
                status_code=409, detail=api_messages.note_exists
            )
        except FileNotFoundError:
            raise HTTPException(404, api_messages.note_not_found)

    # Delete Note
    @router.delete(
        "/api/notes/{title}",
        dependencies=auth_deps,
        response_model=None,
    )
    def delete_note(title: str):
        try:
            with publication_store.connection(write=True) as db:
                note_storage.delete(title)
                publication_store.remove(title, db)
                expiration_store.remove("plain", title, db)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=api_messages.invalid_note_title,
            )
        except FileNotFoundError:
            raise HTTPException(404, api_messages.note_not_found)



# region Publications

@router.get(
    "/api/notes/{title}/publication",
    dependencies=auth_deps,
    response_model=PublicationInfo | None,
)
def get_publication(title: str):
    if not global_config.sharing_enabled:
        raise HTTPException(404, "Sharing is disabled")
    try:
        ensure_active("plain", title)
        note_storage.get(title)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Note not found")
    return publication_store.get_by_title(title)


if global_config.auth_type != AuthType.READ_ONLY:

    @router.put(
        "/api/notes/{title}/publication",
        dependencies=auth_deps,
        response_model=PublicationInfo,
    )
    def set_publication(title: str, settings: PublicationSettings):
        if not global_config.sharing_enabled:
            raise HTTPException(404, "Sharing is disabled")
        try:
            ensure_active("plain", title)
            note = note_storage.get(title)
        except (ValueError, FileNotFoundError):
            raise HTTPException(404, "Note not found")
        try:
            return publication_store.set(
                title, settings.slug_mode, settings.permission,
                settings.slug, note.content or "",
            )
        except SlugConflictError as error:
            raise HTTPException(409, str(error))
        except ValueError as error:
            raise HTTPException(422, str(error))

    @router.delete(
        "/api/notes/{title}/publication",
        dependencies=auth_deps,
        status_code=204,
    )
    def delete_publication(title: str):
        if not global_config.sharing_enabled:
            raise HTTPException(404, "Sharing is disabled")
        with publication_store.connection(write=True) as db:
            publication_store.remove(title, db)


def public_note_or_404(slug: str):
    if not global_config.sharing_enabled:
        raise HTTPException(404, "Sharing is disabled")
    publication = publication_store.get_by_slug(slug)
    if not publication:
        raise HTTPException(404, "Note not found")
    try:
        ensure_active("plain", publication["note_title"])
        note = note_storage.get(publication["note_title"])
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Note not found")
    return publication, note


@router.get("/api/public/notes/{slug}", response_model=PublicNote)
def read_public_note(slug: str, response: Response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    response.headers["Referrer-Policy"] = "no-referrer"
    with publication_store.connection(write=True) as db:
        publication = publication_store.get_by_slug(slug, db)
        if not global_config.sharing_enabled or not publication:
            raise HTTPException(404, "Published note not found")
        title = publication["note_title"]
        ensure_active("plain", title, db)
        try:
            note = note_storage.get(title)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, "Published note not found")
        state = expiration_store.get("plain", title, db)
        view_token = expiration_store.consume("plain", title, db=db, allow_session=True)
    return PublicNote(
        expiration=state,
        view_token=view_token,
        title=note.title,
        content=note.content or "",
        permission=publication["permission"],
        revision=content_revision(note.content or ""),
    )


@router.patch("/api/public/notes/{slug}", response_model=PublicNote)
def edit_public_note(slug: str, data: PublicNoteUpdate, response: Response):
    if not global_config.sharing_enabled:
        raise HTTPException(404, "Sharing is disabled")
    response.headers["Cache-Control"] = "no-store"
    with publication_store.connection(write=True) as db:
        publication = publication_store.get_by_slug(slug, db)
        if not publication:
            raise HTTPException(404, "Note not found")
        if publication["permission"] != "edit":
            raise HTTPException(403, "Public editing is disabled")
        ensure_active("plain", publication["note_title"], db)
        try:
            note = note_storage.get(publication["note_title"])
        except (ValueError, FileNotFoundError):
            raise HTTPException(404, "Note not found")
        if content_revision(note.content or "") != data.revision:
            raise HTTPException(409, "Note changed since it was loaded")
        note = note_storage.update(
            publication["note_title"],
            NoteUpdate(new_content=data.new_content),
        )
        # Public edits never expand the list of public attachments.
        return PublicNote(
            title=note.title,
            content=note.content or "",
            permission=publication["permission"],
            revision=content_revision(note.content or ""),
        )


@router.get("/api/public/notes/{slug}/attachments/{filename}")
def get_public_attachment(slug: str, filename: str, view_token: str | None = None):
    if not global_config.sharing_enabled:
        raise HTTPException(404, "Sharing is disabled")
    publication = publication_store.get_by_slug(slug)
    if not publication:
        raise HTTPException(404, "Published note not found")
    title = publication["note_title"]
    state = expiration_store.get("plain", title)
    if state["mode"] == "once":
        if not expiration_store.view_session_valid("plain", title, view_token):
            raise HTTPException(410, "Single-view attachment session expired")
    else:
        ensure_active("plain", title)
    if not publication_store.has_attachment(publication["id"], filename):
        raise HTTPException(404, "Attachment not found")
    try:
        result = attachment_storage.get(filename)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Attachment not found")
    result.headers["Cache-Control"] = "no-store"
    result.headers["X-Content-Type-Options"] = "nosniff"
    result.headers["Content-Security-Policy"] = "sandbox"
    extension = filename.lower().rsplit(".", 1)[-1]
    if extension not in {"png", "jpg", "jpeg", "gif", "webp"}:
        result.headers["Content-Disposition"] = "attachment"
    return result


# endregion



# region Encrypted notes
def encrypted_response(note_id: str, ciphertext: bytes, permission: str = ""):
    result = Response(content=ciphertext, media_type="application/octet-stream")
    result.headers["Cache-Control"] = "no-store"
    result.headers["X-Content-Type-Options"] = "nosniff"
    result.headers["X-Revision"] = encrypted_store.revision(note_id)
    result.headers["X-Note-Id"] = note_id
    state = expiration_store.get("encrypted", note_id)
    result.headers["X-Expiration-Mode"] = state["mode"]
    result.headers["X-Expiration-Policy"] = state["policy"]
    if state["expiresAt"] is not None:
        result.headers["X-Expires-At"] = str(state["expiresAt"])
    if permission:
        result.headers["X-Edit-Permission"] = permission
    return result


@router.get("/api/encrypted-notes", dependencies=auth_deps)
def list_encrypted_notes():
    result = []
    for note in encrypted_store.list():
        state = expiration_store.get("encrypted", note["id"])
        if state["status"] == "active":
            result.append({**note, "expiration": state})
    return result


@router.get("/api/encrypted-notes/{note_id}", dependencies=auth_deps)
def get_encrypted_note(note_id: str):
    try:
        ensure_active("encrypted", note_id)
        data = encrypted_store.read(note_id)
        return encrypted_response(note_id, data)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Encrypted note not found")


@router.put("/api/encrypted-notes/{note_id}", dependencies=auth_deps)
async def put_encrypted_note(
    note_id: str, request: Request, x_revision: str = Header(None),
    x_expiration: str | None = Header(None),
    x_view_verifier: str | None = Header(None),
):
    if not global_config.encryption_enabled or global_config.auth_type == AuthType.READ_ONLY:
        raise HTTPException(403, "Encrypted note writes are disabled")
    data = await request.body()
    is_new = x_revision == "*"
    policy = selected_expiration(x_expiration) if is_new else None
    if is_new and policy == "once" and not x_view_verifier:
        raise HTTPException(422, "A browser-generated single-view verifier is required")
    try:
        with publication_store.connection(write=True) as db:
            if not is_new:
                ensure_active("encrypted", note_id, db)
            revision = encrypted_store.save(note_id, data, x_revision)
            if is_new:
                expiration_store.remove("encrypted", note_id, db)
            if is_new and policy != "none":
                try:
                    expiration_store.set("encrypted", note_id, policy, x_view_verifier, db)
                except Exception:
                    encrypted_store.delete(note_id)
                    raise
        return {"id": note_id, "revision": revision}
    except (FileExistsError, FileNotFoundError):
        raise HTTPException(409, "Encrypted note changed or exists")
    except ValueError as error:
        raise HTTPException(422, str(error))


@router.post("/api/encrypted-notes/protect/{title}/{note_id}", dependencies=auth_deps)
async def protect_existing_note(
    title: str,
    note_id: str,
    request: Request,
    x_source_modified: str = Header(None),
    x_view_verifier: str | None = Header(None),
):
    if not global_config.encryption_enabled or global_config.auth_type == AuthType.READ_ONLY:
        raise HTTPException(403, "Encryption is disabled")
    data = await request.body()
    try:
        is_valid_filename(title)
        with publication_store.connection(write=True) as db:
            ensure_active("plain", title, db)
            state = expiration_store.get("plain", title, db)
            if state["mode"] == "once" and not x_view_verifier:
                raise HTTPException(422, "Encrypted single-view conversion requires unlock verifier")
            # Check only the source file's existence. Do not read its content.
            from pathlib import Path
            original_path = Path(note_storage._path_from_title(title))
            if not original_path.is_file():
                raise HTTPException(404, "Note not found")
            if not x_source_modified or str(original_path.stat().st_mtime) != x_source_modified:
                raise HTTPException(409, "The source note changed before encryption")
            revision = encrypted_store.save(note_id, data, "*")
            try:
                expiration_store.transfer("plain", title, "encrypted", note_id, db, x_view_verifier)
                original_path.unlink()
            except OSError:
                encrypted_store.delete(note_id)
                raise
            publication_store.remove(title, db)
        note_storage._sync_index_with_retry()
        return {"id": note_id, "revision": revision}
    except FileExistsError:
        raise HTTPException(409, "Encrypted note already exists")
    except ValueError as error:
        raise HTTPException(422, str(error))


@router.delete("/api/encrypted-notes/{note_id}", dependencies=auth_deps, status_code=204)
def delete_encrypted_note(note_id: str):
    if global_config.auth_type == AuthType.READ_ONLY:
        raise HTTPException(403, "Read-only mode")
    try:
        with publication_store.connection(write=True) as db:
            encrypted_store.delete(note_id)
            encrypted_publications.delete(note_id, db)
            expiration_store.remove("encrypted", note_id, db)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Encrypted note not found")


@router.get("/api/encrypted-notes/{note_id}/publication", dependencies=auth_deps, response_model=PublicationInfo | None)
def get_encrypted_publication(note_id: str):
    if not global_config.sharing_enabled:
        raise HTTPException(404, "Sharing is disabled")
    try:
        encrypted_store.path(note_id).stat()
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Encrypted note not found")
    ensure_active("encrypted", note_id)
    return encrypted_publications.get(note_id=note_id)


@router.put("/api/encrypted-notes/{note_id}/publication", dependencies=auth_deps, response_model=PublicationInfo)
def set_encrypted_publication(note_id: str, settings: PublicationSettings):
    if not global_config.sharing_enabled or global_config.auth_type == AuthType.READ_ONLY:
        raise HTTPException(404, "Sharing is disabled")
    try:
        encrypted_store.path(note_id).stat()
        ensure_active("encrypted", note_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Encrypted note not found")
    try:
        return encrypted_publications.save(note_id, settings.slug_mode, settings.permission, settings.slug)
    except SlugConflictError as error:
        raise HTTPException(409, str(error))
    except ValueError as error:
        raise HTTPException(422, str(error))


@router.delete("/api/encrypted-notes/{note_id}/publication", dependencies=auth_deps, status_code=204)
def delete_encrypted_publication(note_id: str):
    if not global_config.sharing_enabled or global_config.auth_type == AuthType.READ_ONLY:
        raise HTTPException(404, "Sharing is disabled")
    encrypted_publications.delete(note_id)


@router.get("/api/public/encrypted-notes/{slug}")
def read_public_encrypted_note(slug: str):
    if not global_config.sharing_enabled:
        raise HTTPException(404, "Sharing is disabled")
    publication = encrypted_publications.get(slug=slug)
    if not publication:
        raise HTTPException(404, "Published note not found")
    try:
        ensure_active("encrypted", publication["note_id"])
        data = encrypted_store.read(publication["note_id"])
        return encrypted_response(publication["note_id"], data, publication["permission"])
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Published note not found")


@router.put("/api/public/encrypted-notes/{slug}")
async def write_public_encrypted_note(slug: str, request: Request, x_revision: str = Header(None)):
    if not global_config.sharing_enabled or not global_config.encryption_enabled:
        raise HTTPException(404, "Sharing or encryption is disabled")
    data = await request.body()
    try:
        with publication_store.connection(write=True) as db:
            publication = encrypted_publications.get(slug=slug, db=db)
            if not publication:
                raise HTTPException(404, "Published note not found")
            if publication["permission"] != "edit":
                raise HTTPException(403, "Public editing is disabled")
            ensure_active("encrypted", publication["note_id"], db)
            revision = encrypted_store.save(publication["note_id"], data, x_revision)
            return {"revision": revision}
    except (ValueError, FileNotFoundError, FileExistsError):
        raise HTTPException(409, "Note revision mismatch")


# endregion



# region Expiration

@router.get("/api/expiring-notes", dependencies=auth_deps)
def list_expiring_notes():
    """List active expiring notes without exposing encrypted content."""
    return expiration_store.list_active()


@router.get("/api/notes/{title}/expiration", dependencies=auth_deps)
def get_note_expiration(title: str):
    try:
        note_storage._path_from_title(title)
        ensure_active("plain", title)
        note_storage.get(title)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Note not found")
    return expiration_store.get("plain", title)


@router.put("/api/notes/{title}/expiration", dependencies=auth_deps)
def set_note_expiration(title: str, settings: ExpirationSettings):
    require_expiration_writes()
    policy = selected_expiration(settings.policy)
    try:
        with publication_store.connection(write=True) as db:
            ensure_active("plain", title, db)
            note_storage.get(title)
            result = expiration_store.set("plain", title, policy, db=db)
        note_storage._sync_index_with_retry(optimize=True)
        return result
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Note not found")


@router.get("/api/encrypted-notes/{note_id}/expiration", dependencies=auth_deps)
def get_encrypted_expiration(note_id: str):
    try:
        ensure_active("encrypted", note_id)
        encrypted_store.path(note_id).stat()
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Encrypted note not found")
    return expiration_store.get("encrypted", note_id)


@router.put("/api/encrypted-notes/{note_id}/expiration", dependencies=auth_deps)
def set_encrypted_expiration(note_id: str, settings: ExpirationSettings):
    require_expiration_writes()
    policy = selected_expiration(settings.policy)
    try:
        with publication_store.connection(write=True) as db:
            ensure_active("encrypted", note_id, db)
            encrypted_store.path(note_id).stat()
            return expiration_store.set("encrypted", note_id, policy, settings.verifier, db)
    except (ValueError, FileNotFoundError) as error:
        if isinstance(error, ValueError) and "verifier" in str(error):
            raise HTTPException(422, str(error))
        raise HTTPException(404, "Encrypted note not found")


@router.post("/api/encrypted-notes/{note_id}/view", dependencies=auth_deps)
def consume_private_encrypted_view(note_id: str, data: SingleViewProof):
    try:
        with publication_store.connection(write=True) as db:
            ensure_active("encrypted", note_id, db)
            encrypted_store.path(note_id).stat()
            expiration_store.consume("encrypted", note_id, proof=data.proof, db=db)
    except PermissionError:
        raise HTTPException(403, "Invalid browser unlock proof")
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Encrypted note not found")
    return {"consumed": True}


@router.post("/api/public/encrypted-notes/{slug}/view")
def consume_public_encrypted_view(slug: str, data: SingleViewProof):
    if not global_config.sharing_enabled:
        raise HTTPException(404, "Sharing is disabled")
    try:
        with publication_store.connection(write=True) as db:
            published = encrypted_publications.get(slug=slug, db=db)
            if not published:
                raise HTTPException(404, "Published note not found")
            note_id = published["note_id"]
            ensure_active("encrypted", note_id, db)
            encrypted_store.path(note_id).stat()
            expiration_store.consume("encrypted", note_id, proof=data.proof, db=db)
    except PermissionError:
        raise HTTPException(403, "Invalid browser unlock proof")
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Published note not found")
    return {"consumed": True}


# endregion


# region Search
@router.get(
    "/api/search",
    dependencies=auth_deps,
    response_model=List[SearchResult],
)
def search(
    term: str,
    sort: Literal["score", "title", "lastModified"] = "score",
    order: Literal["asc", "desc"] = "desc",
    limit: int = None,
):
    """Perform a full text search on all notes."""
    if sort == "lastModified":
        sort = "last_modified"
    result = note_storage.search(term, sort=sort, order=order, limit=limit)
    return [item for item in result if expiration_store.is_indexable(item.title)]


@router.get(
    "/api/tags",
    dependencies=auth_deps,
    response_model=List[str],
)
def get_tags():
    """Get a list of all indexed tags."""
    return note_storage.get_tags()


# endregion


# region Config
@router.get("/api/config", response_model=GlobalConfigResponseModel)
def get_config():
    """Retrieve server-side config required for the UI."""
    return GlobalConfigResponseModel(
        auth_type=global_config.auth_type,
        encryption_enabled=global_config.encryption_enabled,
        sharing_enabled=global_config.sharing_enabled,
        expiration_enabled=global_config.expiration_enabled,
        expiration_default=global_config.expiration_default,
        encryption_password_min_length=global_config.encryption_password_min_length,
        encryption_password_min_classes=global_config.encryption_password_min_classes,
        quick_access_hide=global_config.quick_access_hide,
        quick_access_title=global_config.quick_access_title,
        quick_access_term=global_config.quick_access_term,
        quick_access_sort=global_config.quick_access_sort,
        quick_access_limit=global_config.quick_access_limit,
        site_title=global_config.site_title,
        logo_url="api/branding/logo" if global_config.logo_path else None,
        favicon_url="api/branding/favicon" if global_config.favicon_path else None,
    )


# endregion


# region Branding

def branding_image(path: str | None) -> FileResponse:
    if path is None:
        raise HTTPException(status_code=404, detail="Branding image not configured")
    return FileResponse(
        path,
        media_type=mimetypes.guess_type(path)[0],
        headers={
            "Cache-Control": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
        },
    )


@router.get("/api/branding/logo", include_in_schema=False)
def get_branding_logo():
    return branding_image(global_config.logo_path)


@router.get("/api/branding/favicon", include_in_schema=False)
def get_branding_favicon():
    return branding_image(global_config.favicon_path)


# endregion


# region Attachments
# Get Attachment
@router.get(
    "/api/attachments/{filename}",
    dependencies=auth_deps,
)
# Include a secondary route used to create relative URLs that can be used
# outside the context of flatnotes (e.g. "/attachments/image.jpg").
@router.get(
    "/attachments/{filename}",
    dependencies=auth_deps,
    include_in_schema=False,
)
def get_attachment(filename: str):
    """Download an attachment."""
    try:
        return attachment_storage.get(filename)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=api_messages.invalid_attachment_filename,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail=api_messages.attachment_not_found
        )


if global_config.auth_type != AuthType.READ_ONLY:

    # Create Attachment
    @router.post(
        "/api/attachments",
        dependencies=auth_deps,
        response_model=AttachmentCreateResponse,
    )
    def post_attachment(file: UploadFile):
        """Upload an attachment."""
        try:
            return attachment_storage.create(file)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=api_messages.invalid_attachment_filename,
            )
        except FileExistsError:
            raise HTTPException(409, api_messages.attachment_exists)


# endregion


# region Healthcheck
@router.get("/health")
def healthcheck() -> str:
    """A lightweight endpoint that simply returns 'OK' to indicate the server
    is running."""
    return "OK"


# endregion

app.include_router(router, prefix=global_config.path_prefix)
app.mount(
    global_config.path_prefix,
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="dist",
)
