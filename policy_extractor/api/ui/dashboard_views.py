"""Dashboard UI routes with aggregate stats queries."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from policy_extractor.api import get_db
from policy_extractor.api.ui import templates
from policy_extractor.config import settings
from policy_extractor.storage.models import Poliza

dashboard_router = APIRouter()


def _get_stats(db: Session, since: date | None = None, until: date | None = None) -> dict:
    """Compute dashboard aggregate stats. Uses DB-level COUNT/AVG, not Python loops."""
    base = select(
        func.count(Poliza.id).label("total"),
        func.avg(Poliza.evaluation_score).label("avg_score"),
    )
    if since:
        base = base.where(Poliza.extracted_at >= datetime.combine(since, datetime.min.time()))
    if until:
        base = base.where(Poliza.extracted_at <= datetime.combine(until, datetime.max.time()))
    row = db.execute(base).one()

    warning_stmt = select(func.count(Poliza.id)).where(
        Poliza.validation_warnings.is_not(None)
    )
    if since:
        warning_stmt = warning_stmt.where(
            Poliza.extracted_at >= datetime.combine(since, datetime.min.time())
        )
    if until:
        warning_stmt = warning_stmt.where(
            Poliza.extracted_at <= datetime.combine(until, datetime.max.time())
        )
    total_warnings = db.scalar(warning_stmt) or 0

    return {
        "total": row.total or 0,
        "avg_score": round(float(row.avg_score or 0), 2),
        "total_warnings": total_warnings,
    }


def _get_needs_review(
    db: Session,
    since: date | None = None,
    until: date | None = None,
    limit: int = 10,
) -> list:
    """Get polizas needing review: score < threshold OR any validation_warnings (D-18)."""
    stmt = select(Poliza).where(
        or_(
            Poliza.evaluation_score < settings.REVIEW_SCORE_THRESHOLD,
            Poliza.validation_warnings.is_not(None),
        )
    )
    if since:
        stmt = stmt.where(
            Poliza.extracted_at >= datetime.combine(since, datetime.min.time())
        )
    if until:
        stmt = stmt.where(
            Poliza.extracted_at <= datetime.combine(until, datetime.max.time())
        )
    stmt = stmt.order_by(Poliza.extracted_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


@dashboard_router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    periodo: Optional[str] = Query(None),
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
):
    """Render the dashboard landing page with aggregate stats and review table."""
    # Determine "since" and "until" dates from periodo or custom range (D-17)
    since = None
    until = None
    if periodo == "7d":
        since = date.today() - timedelta(days=7)
    elif periodo == "30d":
        since = date.today() - timedelta(days=30)
    elif desde or hasta:
        since = desde
        until = hasta

    stats = _get_stats(db, since, until)
    needs_review = _get_needs_review(db, since, until)

    # If HTMX request (date range change), return only stats partial
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request,
            name="partials/dashboard_stats.html",
            context={
                "stats": stats,
                "needs_review": needs_review,
                "periodo": periodo or "all",
            },
        )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "active_page": "dashboard",
            "stats": stats,
            "needs_review": needs_review,
            "periodo": periodo or "all",
            "desde": desde or "",
            "hasta": hasta or "",
        },
    )
