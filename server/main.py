from typing import List, Literal
from pathlib import Path
from html import escape
import mimetypes
from threading import Event, Thread

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from flatnotes import api_messages
from flatnotes.auth.models import Login, Token
from flatnotes.global_config import AuthType, GlobalConfigResponseModel
from flatnotes.helpers import replace_base_href
from flatnotes.notes.models import SearchResult
from flatnotes.expiration import ExpirationError
from flatnotes.context import (
    global_config, auth, auth_deps, note_storage, attachment_storage,
    publication_store, encrypted_store, encrypted_publications, expiration_store,
)
from flatnotes.api_notes import router as notes_router
from flatnotes.api_publications import router as publications_router
from flatnotes.api_encrypted import router as encrypted_router
from flatnotes.api_attachments import router as attachments_router

cleanup_stopped = Event()


def cleanup_expired_notes():
    while not cleanup_stopped.wait(60):
        try:
            expiration_store.cleanup(note_storage, encrypted_store)
        except Exception:
            from flatnotes.logger import logger
            logger.exception("Expiration cleanup failed; retrying")


router = APIRouter()
app = FastAPI(
    docs_url=global_config.path_prefix + "/docs",
    openapi_url=global_config.path_prefix + "/openapi.json",
)
FRONTEND_DIR = Path(__file__).resolve().parent / "web" / "dist"


@app.exception_handler(ExpirationError)
async def expired_publication_handler(request: Request, error: ExpirationError):
    return JSONResponse({"detail": str(error)}, status_code=410)


@app.on_event("startup")
def start_cleanup():
    cleanup_stopped.clear()
    Thread(target=cleanup_expired_notes, daemon=True, name="flatnotes-expiration").start()


@app.on_event("shutdown")
def stop_cleanup():
    cleanup_stopped.set()


# region UI
@router.get("/", include_in_schema=False)
@router.get("/login", include_in_schema=False)
@router.get("/search", include_in_schema=False)
@router.get("/new", include_in_schema=False)
@router.get("/encrypted", include_in_schema=False)
@router.get("/note/{title}", include_in_schema=False)
@router.get("/n/{title}", include_in_schema=False)
@router.get("/e/{id}", include_in_schema=False)
@router.get("/p/{slug}", include_in_schema=False)
def root(request: Request, title: str = ""):
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    html = replace_base_href(html, global_config.path_prefix)
    html = html.replace("<title>flatnotes</title>", f"<title>{escape(global_config.site_title)}</title>")
    is_public = request.url.path.startswith(global_config.path_prefix + "/p/")
    is_encrypted = request.url.path.startswith(global_config.path_prefix + "/e/")
    if is_public:
        slug = request.url.path.rsplit("/", 1)[-1]
        is_encrypted = encrypted_publications.get(slug=slug) is not None
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
    return note_storage.search(term, sort=sort, order=order, limit=limit)


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


# region Healthcheck
@router.get("/health")
def healthcheck() -> str:
    """A lightweight endpoint that simply returns 'OK' to indicate the server
    is running."""
    return "OK"


# endregion

app.include_router(router, prefix=global_config.path_prefix)
app.include_router(notes_router, prefix=global_config.path_prefix)
app.include_router(publications_router, prefix=global_config.path_prefix)
app.include_router(encrypted_router, prefix=global_config.path_prefix)
app.include_router(attachments_router, prefix=global_config.path_prefix)
app.mount(
    global_config.path_prefix,
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="dist",
)
