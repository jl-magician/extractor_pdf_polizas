"""Pydantic models for the ingestion layer output contract."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PageResult(BaseModel):
    page_num: int
    text: str
    classification: Literal["digital", "scanned"]


class IngestionResult(BaseModel):
    file_hash: str               # SHA-256 hex string (64 chars)
    file_path: str               # absolute path as string
    total_pages: int
    pages: list[PageResult] = Field(default_factory=list)
    file_size_bytes: int
    created_at: datetime
    ocr_applied: bool
    ocr_language: str = "spa"
    from_cache: bool = False
