"""Private Markdown note endpoints."""

from fastapi import APIRouter, HTTPException

from flatnotes import api_messages
from flatnotes.global_config import AuthType
from flatnotes.notes.models import Note, NoteCreate, NoteUpdate
from flatnotes.context import global_config, auth_deps, note_storage, publication_store

router = APIRouter()

# region Notes
# Get Note
@router.get(
    "/api/notes/{title}",
    dependencies=auth_deps,
    response_model=Note,
)
def get_note(title: str):
    """Return a private note; public-link expiration never affects owner access."""
    try:
        return note_storage.get(title)
    except ValueError:
        raise HTTPException(400, api_messages.invalid_note_title)
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
        """Create an ordinary Markdown note without an expiration policy."""
        try:
            return note_storage.create(note)
        except ValueError:
            raise HTTPException(400, api_messages.invalid_note_title)
        except FileExistsError:
            raise HTTPException(409, api_messages.note_exists)

    # Update Note
    @router.patch(
        "/api/notes/{title}",
        dependencies=auth_deps,
        response_model=Note,
    )
    def patch_note(title: str, data: NoteUpdate):
        try:
            with publication_store.connection(write=True) as db:
                current_publication = publication_store.get_by_title(title, db)
                updated = note_storage.update(title, data)
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
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=api_messages.invalid_note_title,
            )
        except FileNotFoundError:
            raise HTTPException(404, api_messages.note_not_found)



