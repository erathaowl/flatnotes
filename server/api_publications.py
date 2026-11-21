"""Markdown publication, anonymous editing, and shared attachments."""

from fastapi import APIRouter, HTTPException, Response

from flatnotes.global_config import AuthType
from flatnotes.notes.models import NoteUpdate
from flatnotes.publications import SlugConflictError, content_revision
from flatnotes.expiration import ExpirationError, ensure_active as ensure_public_active
from flatnotes.publication_models import PublicationSettings, PublicationInfo, PublicNote, PublicNoteUpdate
from flatnotes.context import (
    global_config, auth_deps, note_storage, attachment_storage,
    publication_store, expiration_store,
)

router = APIRouter()

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
            note = note_storage.get(title)
        except (ValueError, FileNotFoundError):
            raise HTTPException(404, "Note not found")
        try:
            return publication_store.set(
                title, settings.slug_mode, settings.permission,
                settings.slug, note.content or "",
                settings.expiration, settings.auto_delete_note, settings.view_verifier,
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
        ensure_public_active(publication)
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
        try:
            ensure_public_active(publication)
            note = note_storage.get(title)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, "Published note not found")
        state = {
            "mode": "once" if publication["expiration"] == "once"
            else "time" if publication["expiration"] != "none" else "none",
            "policy": publication["expiration"],
            "expiresAt": publication["expires_at"],
        }
        view_token = expiration_store.consume(publication, db=db, allow_session=True)
    return PublicNote(
        expiration=state,
        view_token=view_token,
        title=note.title,
        content=note.content or "",
        permission="read" if global_config.auth_type == AuthType.READ_ONLY else publication["permission"],
        revision=content_revision(note.content or ""),
    )


@router.patch("/api/public/notes/{slug}", response_model=PublicNote)
def edit_public_note(slug: str, data: PublicNoteUpdate, response: Response):
    if not global_config.sharing_enabled:
        raise HTTPException(404, "Sharing is disabled")
    if global_config.auth_type == AuthType.READ_ONLY:
        raise HTTPException(403, "Read-only mode")
    response.headers["Cache-Control"] = "no-store"
    with publication_store.connection(write=True) as db:
        publication = publication_store.get_by_slug(slug, db)
        if not publication:
            raise HTTPException(404, "Note not found")
        if publication["permission"] != "edit":
            raise HTTPException(403, "Public editing is disabled")
        try:
            ensure_public_active(publication)
        except ExpirationError:
            raise HTTPException(410, "Public link expired")
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
    if publication["expiration"] == "once":
        if not expiration_store.view_session_valid(slug, view_token):
            raise HTTPException(410, "Single-view attachment session expired")
    else:
        try:
            ensure_public_active(publication)
        except ExpirationError:
            raise HTTPException(410, "Public link expired")
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



