#!/usr/bin/env python3
"""Build a small train/eval dataset from real MedMemory conversation use cases.

Example:
    cd backend
    uv run python scripts/build_real_usecase_dataset.py \
      --num-examples 120 \
      --output-dir data/qlora_usecases
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_db_context
from app.models.conversation import Conversation, ConversationMessage
from app.models.patient import Patient

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?){2}\d{4}\b")
_LONG_DIGIT_RE = re.compile(r"\b\d{7,}\b")
_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})\b",
    re.IGNORECASE,
)
_WS_RE = re.compile(r"\s+")


@dataclass(slots=True)
class MessageRow:
    conversation_id: str
    patient_id: int
    patient_first_name: str
    patient_last_name: str
    message_id: int
    role: str
    content: str
    feedback_rating: int | None
    created_at: datetime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--num-examples",
        type=int,
        default=120,
        help="Target number of examples. Recommended range: 50-200.",
    )
    parser.add_argument(
        "--allow-small",
        action="store_true",
        help="Allow fewer than 50 examples (useful for smoke tests).",
    )
    parser.add_argument(
        "--eval-ratio",
        type=float,
        default=0.2,
        help="Fraction of selected examples to reserve for evaluation.",
    )
    parser.add_argument(
        "--min-eval-examples",
        type=int,
        default=20,
        help="Minimum number of evaluation examples.",
    )
    parser.add_argument(
        "--min-prompt-chars",
        type=int,
        default=20,
        help="Minimum character length for user prompts.",
    )
    parser.add_argument(
        "--min-answer-chars",
        type=int,
        default=40,
        help="Minimum character length for assistant answers.",
    )
    parser.add_argument(
        "--min-feedback-rating",
        type=int,
        default=None,
        help="If set, keep only pairs whose assistant message rating >= this threshold.",
    )
    parser.add_argument(
        "--require-feedback",
        action="store_true",
        help="If set, keep only assistant messages that have a rating.",
    )
    parser.add_argument(
        "--no-deidentify",
        action="store_true",
        help="Disable simple PHI masking in exported text.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for sampling and split.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/qlora_usecases"),
        help="Output directory for JSONL datasets.",
    )
    return parser.parse_args()


async def load_messages() -> list[MessageRow]:
    """Load all conversation messages with patient metadata."""
    async with get_db_context() as db:
        stmt = (
            select(
                Conversation.id,
                Conversation.patient_id,
                Patient.first_name,
                Patient.last_name,
                ConversationMessage.id,
                ConversationMessage.role,
                ConversationMessage.content,
                ConversationMessage.feedback_rating,
                ConversationMessage.created_at,
            )
            .join(
                ConversationMessage,
                ConversationMessage.conversation_id == Conversation.id,
            )
            .join(Patient, Patient.id == Conversation.patient_id)
            .where(Conversation.is_active.is_(True))
            .order_by(
                Conversation.id.asc(),
                ConversationMessage.created_at.asc(),
                ConversationMessage.id.asc(),
            )
        )
        rows = (await db.execute(stmt)).all()

    items: list[MessageRow] = []
    for row in rows:
        items.append(
            MessageRow(
                conversation_id=str(row[0]),
                patient_id=int(row[1]),
                patient_first_name=row[2] or "",
                patient_last_name=row[3] or "",
                message_id=int(row[4]),
                role=row[5],
                content=row[6] or "",
                feedback_rating=row[7],
                created_at=row[8],
            )
        )
    return items


def deidentify_text(text: str, first_name: str, last_name: str) -> str:
    """Apply lightweight PHI masking for exported local datasets."""
    value = text
    if first_name:
        value = re.sub(
            rf"\b{re.escape(first_name)}\b",
            "[PATIENT_NAME]",
            value,
            flags=re.IGNORECASE,
        )
    if last_name:
        value = re.sub(
            rf"\b{re.escape(last_name)}\b",
            "[PATIENT_NAME]",
            value,
            flags=re.IGNORECASE,
        )
    full_name = f"{first_name} {last_name}".strip()
    if full_name and full_name != " ":
        value = re.sub(
            rf"\b{re.escape(full_name)}\b",
            "[PATIENT_NAME]",
            value,
            flags=re.IGNORECASE,
        )
    value = _EMAIL_RE.sub("[EMAIL]", value)
    value = _PHONE_RE.sub("[PHONE]", value)
    value = _LONG_DIGIT_RE.sub("[ID]", value)
    value = _DATE_RE.sub("[DATE]", value)
    value = _WS_RE.sub(" ", value).strip()
    return value


def pair_user_assistant_messages(
    rows: list[MessageRow],
) -> list[tuple[MessageRow, MessageRow]]:
    """Create user->assistant pairs within each conversation."""
    grouped: dict[str, list[MessageRow]] = {}
    for row in rows:
        grouped.setdefault(row.conversation_id, []).append(row)

    pairs: list[tuple[MessageRow, MessageRow]] = []
    for conversation_rows in grouped.values():
        for idx, current in enumerate(conversation_rows):
            if current.role != "user":
                continue
            assistant_msg: MessageRow | None = None
            lookahead = idx + 1
            while lookahead < len(conversation_rows):
                candidate = conversation_rows[lookahead]
                if candidate.role == "assistant":
                    assistant_msg = candidate
                    break
                if candidate.role == "user":
                    break
                lookahead += 1
            if assistant_msg is not None:
                pairs.append((current, assistant_msg))
    return pairs


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True))
            handle.write("\n")


def build_example(
    user_msg: MessageRow,
    assistant_msg: MessageRow,
    *,
    deidentify: bool,
) -> dict[str, Any]:
    prompt = user_msg.content.strip()
    answer = assistant_msg.content.strip()
    if deidentify:
        prompt = deidentify_text(
            prompt, user_msg.patient_first_name, user_msg.patient_last_name
        )
        answer = deidentify_text(
            answer, user_msg.patient_first_name, user_msg.patient_last_name
        )

    stable_id = hashlib.sha1(
        f"{user_msg.conversation_id}:{user_msg.message_id}:{assistant_msg.message_id}".encode()
    ).hexdigest()[:16]
    return {
        "id": stable_id,
        "prompt": prompt,
        "reference_answer": answer,
        "messages": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ],
        "metadata": {
            "source": "conversation_messages",
            "conversation_id": user_msg.conversation_id,
            "patient_id": user_msg.patient_id,
            "user_message_id": user_msg.message_id,
            "assistant_message_id": assistant_msg.message_id,
            "assistant_feedback_rating": assistant_msg.feedback_rating,
            "assistant_created_at": assistant_msg.created_at.isoformat(),
        },
    }


def validate_args(args: argparse.Namespace) -> None:
    if not args.allow_small and not (50 <= args.num_examples <= 200):
        raise ValueError(
            "--num-examples must be in [50, 200] unless --allow-small is used."
        )
    if not (0.05 <= args.eval_ratio <= 0.5):
        raise ValueError("--eval-ratio must be between 0.05 and 0.5.")


async def main() -> None:
    args = parse_args()
    validate_args(args)

    all_rows = await load_messages()
    if not all_rows:
        raise RuntimeError("No conversation messages found in the database.")

    pairs = pair_user_assistant_messages(all_rows)
    filtered: list[tuple[MessageRow, MessageRow]] = []
    for user_msg, assistant_msg in pairs:
        prompt = user_msg.content.strip()
        answer = assistant_msg.content.strip()
        if len(prompt) < args.min_prompt_chars:
            continue
        if len(answer) < args.min_answer_chars:
            continue
        if args.require_feedback and assistant_msg.feedback_rating is None:
            continue
        if (
            args.min_feedback_rating is not None
            and assistant_msg.feedback_rating is not None
            and assistant_msg.feedback_rating < args.min_feedback_rating
        ):
            continue
        filtered.append((user_msg, assistant_msg))

    if not filtered:
        raise RuntimeError("No user/assistant pairs matched your filters.")

    rng = random.Random(args.seed)
    rng.shuffle(filtered)

    min_required = 1 if args.allow_small else 50
    if len(filtered) < min_required:
        raise RuntimeError(
            f"Only {len(filtered)} pairs found after filtering, fewer than required {min_required}. "
            "Relax filters or generate more real conversations."
        )

    selected_pairs = filtered[: min(args.num_examples, len(filtered))]
    examples = [
        build_example(
            user_msg,
            assistant_msg,
            deidentify=not args.no_deidentify,
        )
        for user_msg, assistant_msg in selected_pairs
    ]
    rng.shuffle(examples)

    eval_size = max(1, int(round(len(examples) * args.eval_ratio)))
    if len(examples) >= args.min_eval_examples * 2:
        eval_size = max(eval_size, args.min_eval_examples)
    eval_size = min(eval_size, max(len(examples) - 1, 1))
    eval_examples = examples[:eval_size]
    train_examples = examples[eval_size:]

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "all_examples.jsonl", examples)
    write_jsonl(output_dir / "eval.jsonl", eval_examples)
    write_jsonl(output_dir / "train.jsonl", train_examples)

    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "num_available_pairs": len(filtered),
        "num_selected_examples": len(examples),
        "num_train_examples": len(train_examples),
        "num_eval_examples": len(eval_examples),
        "filters": {
            "min_prompt_chars": args.min_prompt_chars,
            "min_answer_chars": args.min_answer_chars,
            "require_feedback": args.require_feedback,
            "min_feedback_rating": args.min_feedback_rating,
            "deidentify": not args.no_deidentify,
        },
        "output_dir": str(output_dir),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    print("Dataset build complete.")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
