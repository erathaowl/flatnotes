"""API models for note expiration policies."""

from pydantic import Field

from flatnotes.helpers import CustomBaseModel


class ExpirationSettings(CustomBaseModel):
    policy: str = Field(default="none", max_length=16)
    verifier: str | None = Field(default=None, max_length=64)


class SingleViewProof(CustomBaseModel):
    proof: str = Field(min_length=64, max_length=64)
