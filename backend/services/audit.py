"""Audit-trail service (Phase 13).

Records who did what, when — automated decisions and human overrides — for
accountability and transparency.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db_models import AuditLog


def record(db: Session, user: str, action: str, entity: str | None = None,
           detail: str | None = None, reason: str | None = None) -> None:
    db.add(AuditLog(user=user, action=action, entity=entity, detail=detail, reason=reason))
    db.commit()


def recent(db: Session, limit: int = 50) -> list[dict]:
    rows = db.scalars(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)).all()
    return [{"id": r.id, "timestamp": r.timestamp.isoformat() if r.timestamp else None,
             "user": r.user, "action": r.action, "entity": r.entity,
             "detail": r.detail, "reason": r.reason} for r in rows]


def activity(db: Session) -> list[dict]:
    """Counts by action type (for the activity chart)."""
    rows = db.execute(select(AuditLog.action, func.count()).group_by(AuditLog.action)).all()
    return [{"action": a, "count": int(c)} for a, c in rows]
