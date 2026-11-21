"""Private and public encrypted-note endpoints."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response, Header

from flatnotes.global_config import AuthType
from flatnotes.helpers import is_valid_filename
from flatnotes.publications import SlugConflictError
from flatnotes.expiration import ExpirationError, ensure_active as ensure_public_active
from flatnotes.publication_models import PublicationSettings, PublicationInfo, SingleViewProof
from flatnotes.context import (
    global_config, auth_deps, note_storage, publication_store, encrypted_store,
    encrypted_publications, expiration_store,
)

router = APIRouter()

# region Encrypted notes
def encrypted_response(note_id: str, ciphertext: bytes, permission: str = "", publication=None):
    result = Response(content=ciphertext, media_type="application/octet-stream")
    result.headers["Cache-Control"] = "no-store"
    result.headers["X-Content-Type-Options"] = "nosniff"
    result.headers["X-Revision"] = encrypted_store.revision(note_id)
    result.headers["X-Note-Id"] = note_id
    if publication:
        policy = publication["expiration"]
        result.headers["X-Expiration-Mode"] = (
            "once" if policy == "once" else "time" if policy != "none" else "none"
        )
        result.headers["X-Expiration-Policy"] = policy
        if publication["expires_at"] is not None:
            result.headers["X-Expires-At"] = str(publication["expires_at"])
    if permission:
        result.headers["X-Edit-Permission"] = permission
    return result


@router.get("/api/encrypted-notes", dependencies=auth_deps)
def list_encrypted_notes():
    return encrypted_store.list()


@router.get("/api/encrypted-notes/{note_id}", dependencies=auth_deps)
def get_encrypted_note(note_id: str):
    try:
        data = encrypted_store.read(note_id)
        return encrypted_response(note_id, data)
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Encrypted note not found")


@router.put("/api/encrypted-notes/{note_id}", dependencies=auth_deps)
async def put_encrypted_note(
    note_id: str, request: Request, x_revision: str = Header(None),
):
    if not global_config.encryption_enabled or global_config.auth_type == AuthType.READ_ONLY:
        raise HTTPException(403, "Encrypted note writes are disabled")
    data = await request.body()
    try:
        with publication_store.connection(write=True):
            revision = encrypted_store.save(note_id, data, x_revision)
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
):
    if not global_config.encryption_enabled or global_config.auth_type == AuthType.READ_ONLY:
        raise HTTPException(403, "Encryption is disabled")
    data = await request.body()
    try:
        is_valid_filename(title)
        with publication_store.connection(write=True) as db:
            # Check only the source file's existence. Do not read its content.
            from pathlib import Path
            original_path = Path(note_storage._path_from_title(title))
            if not original_path.is_file():
                raise HTTPException(404, "Note not found")
            if not x_source_modified or str(original_path.stat().st_mtime) != x_source_modified:
                raise HTTPException(409, "The source note changed before encryption")
            revision = encrypted_store.save(note_id, data, "*")
            try:
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
    return encrypted_publications.get(note_id=note_id)


@router.put("/api/encrypted-notes/{note_id}/publication", dependencies=auth_deps, response_model=PublicationInfo)
def set_encrypted_publication(note_id: str, settings: PublicationSettings):
    if not global_config.sharing_enabled or global_config.auth_type == AuthType.READ_ONLY:
        raise HTTPException(404, "Sharing is disabled")
    try:
        encrypted_store.path(note_id).stat()
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Encrypted note not found")
    try:
        return encrypted_publications.save(
            note_id, settings.slug_mode, settings.permission, settings.slug,
            settings.expiration, settings.auto_delete_note, settings.view_verifier,
        )
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
        try:
            ensure_public_active(publication)
        except ExpirationError:
            raise HTTPException(410, "Public link expired")
        data = encrypted_store.read(publication["note_id"])
        return encrypted_response(
            publication["note_id"], data, "read", publication,
        )
    except (ValueError, FileNotFoundError):
        raise HTTPException(404, "Published note not found")


# endregion



# region Public single-view claims

@router.post("/api/public/encrypted-notes/{slug}/view")
def consume_public_encrypted_view(slug: str, data: SingleViewProof):
    if not global_config.sharing_enabled:
        raise HTTPException(404, "Sharing is disabled")
    with publication_store.connection(write=True) as db:
        publication = encrypted_publications.get(slug=slug, db=db)
        if not publication:
            raise HTTPException(404, "Published note not found")
        try:
            ensure_public_active(publication)
            encrypted_store.path(publication["note_id"]).stat()
            expiration_store.consume(publication, proof=data.proof, db=db)
        except ExpirationError:
            raise HTTPException(410, "Public link expired or viewed")
        except PermissionError:
            raise HTTPException(403, "Invalid browser unlock proof")
        except (ValueError, FileNotFoundError):
            raise HTTPException(404, "Published note not found")
    return {"consumed": True}


# endregion


