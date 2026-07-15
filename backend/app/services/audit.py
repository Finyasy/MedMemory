"""Best-effort audit logging helpers for clinician and patient access paths."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AccessAuditLog
from app.services.observability import ObservabilityRegistry

logger = logging.getLogger("medmemory.audit")


async def record_access_audit(
    db: AsyncSession,
    *,
    actor_user_id: int,
    patient_id: int,
    action: str,
    metadata: dict[str, Any] | None = None,
) -> AccessAuditLog | None:
    """Persist a patient access audit log entry without failing the caller path."""

    entry = AccessAuditLog(
        actor_user_id=actor_user_id,
        patient_id=patient_id,
        action=action,
        metadata_=json.dumps(metadata, separators=(",", ":"), ensure_ascii=True)
        if metadata
        else None,
    )
    db.add(entry)
    try:
        await db.commit()
        await db.refresh(entry)
        ObservabilityRegistry.get_instance().record_access_audit(
            action=action,
            result="success",
        )
        logger.info(
            "AUDIT action=%s actor_user_id=%s patient_id=%s entry_id=%s",
            action,
            actor_user_id,
            patient_id,
            entry.id,
        )
        return entry
    except Exception:
        await db.rollback()
        ObservabilityRegistry.get_instance().record_access_audit(
            action=action,
            result="error",
        )
        logger.exception(
            "AUDIT_WRITE_FAILED action=%s actor_user_id=%s patient_id=%s",
            action,
            actor_user_id,
            patient_id,
        )
        return None
