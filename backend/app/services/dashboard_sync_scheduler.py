"""Background scheduler for incremental dashboard connection sync maintenance."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db_context
from app.models import PatientConnectionSyncEvent, PatientDataConnection
from app.services.provider_sync import get_provider_sync_adapter

logger = logging.getLogger("medmemory.dashboard_sync")


@dataclass
class DashboardSyncRunStats:
    """Telemetry emitted for one scheduler cycle."""

    scanned_connections: int = 0
    synced_connections: int = 0
    failed_connections: int = 0
    refreshed_patients: int = 0


class DashboardSyncScheduler:
    """Polling scheduler that advances due data connections in the background."""

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start background scheduler loop if enabled."""
        if not settings.dashboard_background_sync_enabled:
            logger.info("Dashboard sync scheduler disabled by configuration")
            return
        if self._task and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(
            self._run_loop(),
            name="dashboard-sync-scheduler",
        )
        logger.info(
            "Dashboard sync scheduler started (poll=%ss due_hours=%s batch=%s)",
            settings.dashboard_sync_poll_interval_seconds,
            settings.dashboard_sync_due_hours,
            settings.dashboard_sync_batch_size,
        )

    async def stop(self) -> None:
        """Stop background scheduler loop."""
        self._stop_event.set()
        if self._task is None:
            return
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
        logger.info("Dashboard sync scheduler stopped")

    async def run_once(self) -> DashboardSyncRunStats:
        """Run one scheduler cycle (used by background loop and tests)."""
        if not settings.dashboard_background_sync_enabled:
            return DashboardSyncRunStats()

        from app.api.dashboard import (
            evaluate_metric_alerts_for_patient,
            refresh_patient_metric_daily_summary,
        )

        now = datetime.now(UTC)
        due_cutoff = now - timedelta(hours=settings.dashboard_sync_due_hours)
        stats = DashboardSyncRunStats()
        touched_patients: set[int] = set()

        async with get_db_context() as db:
            result = await db.execute(
                select(PatientDataConnection)
                .where(
                    and_(
                        PatientDataConnection.is_active.is_(True),
                        PatientDataConnection.status != "disconnected",
                        or_(
                            PatientDataConnection.last_synced_at.is_(None),
                            PatientDataConnection.last_synced_at <= due_cutoff,
                        ),
                    )
                )
                .order_by(
                    PatientDataConnection.last_synced_at.asc().nullsfirst(),
                    PatientDataConnection.id.asc(),
                )
                .limit(settings.dashboard_sync_batch_size)
            )
            connections = list(result.scalars().all())
            stats.scanned_connections = len(connections)
            if not connections:
                return stats

            for connection in connections:
                try:
                    await self._sync_connection(db=db, connection=connection, now=now)
                    stats.synced_connections += 1
                    touched_patients.add(connection.patient_id)
                except Exception as exc:
                    stats.failed_connections += 1
                    logger.exception(
                        "Dashboard sync failed for patient=%s provider=%s",
                        connection.patient_id,
                        connection.provider_slug,
                    )
                    status_before = connection.status
                    connection.status = "error"
                    connection.last_error = str(exc)[:500]
                    db.add(
                        PatientConnectionSyncEvent(
                            patient_id=connection.patient_id,
                            connection_id=connection.id,
                            provider_slug=connection.provider_slug,
                            event_type="sync_failed",
                            status_before=status_before,
                            status_after=connection.status,
                            details="Background incremental sync failed",
                            last_error=connection.last_error,
                            triggered_by_user_id=None,
                        )
                    )

            for patient_id in sorted(touched_patients):
                try:
                    await refresh_patient_metric_daily_summary(patient_id=patient_id, db=db)
                    await evaluate_metric_alerts_for_patient(patient_id=patient_id, db=db)
                    stats.refreshed_patients += 1
                except Exception:
                    logger.exception(
                        "Post-sync dashboard refresh failed for patient=%s",
                        patient_id,
                    )
            await db.flush()

        return stats

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            started_at = asyncio.get_event_loop().time()
            try:
                stats = await self.run_once()
                if (
                    stats.scanned_connections
                    or stats.synced_connections
                    or stats.failed_connections
                ):
                    logger.info(
                        "Dashboard sync cycle: scanned=%s synced=%s failed=%s refreshed_patients=%s",
                        stats.scanned_connections,
                        stats.synced_connections,
                        stats.failed_connections,
                        stats.refreshed_patients,
                    )
            except Exception:
                logger.exception("Dashboard sync scheduler cycle failed")

            elapsed = asyncio.get_event_loop().time() - started_at
            sleep_seconds = max(
                1,
                settings.dashboard_sync_poll_interval_seconds - int(elapsed),
            )
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_seconds)
            except TimeoutError:
                continue

    async def _sync_connection(
        self,
        *,
        db: AsyncSession,
        connection: PatientDataConnection,
        now: datetime,
    ) -> None:
        status_before = connection.status
        connection.status = "syncing"
        connection.last_error = None
        db.add(
            PatientConnectionSyncEvent(
                patient_id=connection.patient_id,
                connection_id=connection.id,
                provider_slug=connection.provider_slug,
                event_type="sync_started",
                status_before=status_before,
                status_after=connection.status,
                details="Background incremental sync started",
                last_error=None,
                triggered_by_user_id=None,
            )
        )
        await db.flush()

        adapter = get_provider_sync_adapter(connection.provider_slug)
        sync_result = await adapter.sync(
            db=db,
            connection=connection,
            now=now,
        )
        connection.status = "connected"
        connection.last_synced_at = now
        connection.last_error = None
        connection.source_count = sync_result.source_count_total
        db.add(
            PatientConnectionSyncEvent(
                patient_id=connection.patient_id,
                connection_id=connection.id,
                provider_slug=connection.provider_slug,
                event_type="sync_completed",
                status_before="syncing",
                status_after=connection.status,
                details=f"Background incremental sync completed: {sync_result.details}",
                last_error=None,
                triggered_by_user_id=None,
            )
        )


_scheduler_instance: DashboardSyncScheduler | None = None


def get_dashboard_sync_scheduler() -> DashboardSyncScheduler:
    """Get singleton dashboard sync scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = DashboardSyncScheduler()
    return _scheduler_instance
