"""Job history UI routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from policy_extractor.api import get_db
from policy_extractor.api.ui import templates
from policy_extractor.storage.models import BatchJob

job_ui_router = APIRouter()


@job_ui_router.get("/ui/lotes", response_class=HTMLResponse)
def job_history(request: Request, db: Session = Depends(get_db)):
    """List all batch jobs, most recent first (D-09, Copywriting: Job history default sort)."""
    stmt = select(BatchJob).order_by(BatchJob.created_at.desc())
    jobs = list(db.execute(stmt).scalars().all())
    return templates.TemplateResponse(
        request=request,
        name="job_history.html",
        context={"active_page": "jobs", "jobs": jobs},
    )
