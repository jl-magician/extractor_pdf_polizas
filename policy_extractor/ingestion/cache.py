"""SHA-256-based ingestion cache backed by SQLite."""
import hashlib
from datetime import datetime
from pathlib import Path

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from policy_extractor.schemas.ingestion import IngestionResult, PageResult
from policy_extractor.storage.models import IngestionCache


def compute_file_hash(file_path: Path) -> str:
    """Return SHA-256 hex digest of file content bytes."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def lookup_cache(session: Session, file_hash: str) -> IngestionResult | None:
    """Look up cached ingestion result by file hash.

    Returns IngestionResult with from_cache=True if found, None otherwise.
    """
    row = session.execute(
        select(IngestionCache).where(IngestionCache.file_hash == file_hash)
    ).scalar_one_or_none()

    if row is None:
        return None

    pages = [
        PageResult(
            page_num=p["page_num"],
            text=p["text"],
            classification=p["classification"],
        )
        for p in (row.page_results or [])
    ]

    return IngestionResult(
        file_hash=row.file_hash,
        file_path=row.file_path,
        total_pages=row.total_pages,
        pages=pages,
        file_size_bytes=row.file_size_bytes,
        created_at=row.created_at,
        ocr_applied=any(p.classification == "scanned" for p in pages),
        ocr_language=row.ocr_language,
        from_cache=True,
    )


def save_cache(session: Session, result: IngestionResult) -> None:
    """Persist an IngestionResult to the cache table.

    Uses file_hash as unique key. If already exists, does nothing (cache is immutable).
    """
    existing = session.execute(
        select(IngestionCache).where(IngestionCache.file_hash == result.file_hash)
    ).scalar_one_or_none()

    if existing is not None:
        logger.debug(f"Cache entry already exists for {result.file_hash[:12]}...")
        return

    entry = IngestionCache(
        file_hash=result.file_hash,
        file_path=result.file_path,
        total_pages=result.total_pages,
        page_results=[p.model_dump() for p in result.pages],
        file_size_bytes=result.file_size_bytes,
        created_at=datetime.utcnow(),
        ocr_language=result.ocr_language,
    )
    session.add(entry)
    session.commit()
    logger.info(f"Cached ingestion result for {result.file_hash[:12]}...")
