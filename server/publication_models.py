from typing import Literal, Optional

from pydantic import Field

from helpers import CustomBaseModel


class PublicationSettings(CustomBaseModel):
    slug_mode: Literal["random", "title", "custom"] = "random"
    permission: Literal["read", "edit"] = "read"
    slug: Optional[str] = None


class PublicationInfo(CustomBaseModel):
    slug: str
    slug_mode: Literal["random", "title", "custom"]
    permission: Literal["read", "edit"]


class PublicNote(CustomBaseModel):
    title: str
    content: str
    permission: Literal["read", "edit"]
    revision: str


class PublicNoteUpdate(CustomBaseModel):
    new_content: str = Field(max_length=1_000_000)
    revision: str = Field(min_length=64, max_length=64)
