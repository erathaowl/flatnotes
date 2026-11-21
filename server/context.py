"""Shared storage and authentication instances for API routers."""

from fastapi import Depends

from flatnotes.auth.base import BaseAuth
from flatnotes.global_config import GlobalConfig
from flatnotes.publications import PublicationStore
from flatnotes.encrypted_storage import EncryptedNoteStore, EncryptedPublicationStore
from flatnotes.expiration import ExpirationStore

global_config = GlobalConfig()
auth: BaseAuth = global_config.load_auth()
note_storage = global_config.load_note_storage()
attachment_storage = global_config.load_attachment_storage()
publication_store = PublicationStore(note_storage.storage_path)
encrypted_store = EncryptedNoteStore(note_storage.storage_path)
encrypted_publications = EncryptedPublicationStore(publication_store)
expiration_store = ExpirationStore(publication_store)

note_storage._sync_index_with_retry()
expiration_store.cleanup(note_storage, encrypted_store)
auth_deps = [Depends(auth.authenticate)] if auth else []
