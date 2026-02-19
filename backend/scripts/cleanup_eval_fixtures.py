#!/usr/bin/env python3
"""One-time cleanup for stale MedGemma chat eval fixtures."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from sqlalchemy import delete, func, or_, select

from app.database import async_session_maker
from app.models import ConversationMessage, MemoryChunk, Record

EVAL_CONTENT_PATTERNS = (
    "%[EVAL:%",
    "%EVAL_FIXTURE%",
)


@dataclass
class CleanupResult:
    memory_chunks: int
    records: int
    conversation_messages: int


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Delete stale eval fixtures from memory chunks, records, and optionally "
            "conversation messages."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply deletion. Without this flag, runs in dry-run mode.",
    )
    parser.add_argument(
        "--skip-conversation-messages",
        action="store_true",
        help="Do not scan/delete conversation messages.",
    )
    return parser.parse_args()


def _memory_predicate():
    return or_(
        MemoryChunk.chunk_type == "eval_fixture",
        MemoryChunk.content.ilike(EVAL_CONTENT_PATTERNS[0]),
        MemoryChunk.content.ilike(EVAL_CONTENT_PATTERNS[1]),
    )


def _record_predicate():
    return or_(
        Record.title.ilike("[EVAL:%"),
        Record.content.ilike(EVAL_CONTENT_PATTERNS[0]),
        Record.content.ilike(EVAL_CONTENT_PATTERNS[1]),
    )


def _message_predicate():
    return or_(
        ConversationMessage.content.ilike(EVAL_CONTENT_PATTERNS[0]),
        ConversationMessage.content.ilike(EVAL_CONTENT_PATTERNS[1]),
    )


async def _count_rows(session, model, predicate) -> int:
    result = await session.execute(
        select(func.count()).select_from(model).where(predicate)
    )
    return int(result.scalar_one() or 0)


async def _delete_rows(session, model, predicate) -> int:
    result = await session.execute(delete(model).where(predicate))
    return int(result.rowcount or 0)


async def _run_cleanup(*, apply: bool, include_messages: bool) -> CleanupResult:
    async with async_session_maker() as session:
        memory_predicate = _memory_predicate()
        record_predicate = _record_predicate()
        message_predicate = _message_predicate()

        if apply:
            memory_deleted = await _delete_rows(session, MemoryChunk, memory_predicate)
            record_deleted = await _delete_rows(session, Record, record_predicate)
            message_deleted = 0
            if include_messages:
                message_deleted = await _delete_rows(
                    session, ConversationMessage, message_predicate
                )
            await session.commit()
            return CleanupResult(
                memory_chunks=memory_deleted,
                records=record_deleted,
                conversation_messages=message_deleted,
            )

        memory_candidates = await _count_rows(session, MemoryChunk, memory_predicate)
        record_candidates = await _count_rows(session, Record, record_predicate)
        message_candidates = 0
        if include_messages:
            message_candidates = await _count_rows(
                session, ConversationMessage, message_predicate
            )
        await session.rollback()
        return CleanupResult(
            memory_chunks=memory_candidates,
            records=record_candidates,
            conversation_messages=message_candidates,
        )


async def _main_async() -> int:
    args = _parse_args()
    include_messages = not args.skip_conversation_messages
    result = await _run_cleanup(
        apply=args.apply,
        include_messages=include_messages,
    )

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] stale eval fixture summary")
    print(f"  memory_chunks: {result.memory_chunks}")
    print(f"  records: {result.records}")
    if include_messages:
        print(f"  conversation_messages: {result.conversation_messages}")
    else:
        print("  conversation_messages: skipped")

    if not args.apply:
        print("Re-run with --apply to execute deletion.")
    return 0


def main() -> int:
    return asyncio.run(_main_async())


if __name__ == "__main__":
    raise SystemExit(main())
