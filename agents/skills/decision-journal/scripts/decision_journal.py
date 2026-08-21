#!/usr/bin/env python3
"""Create, validate, and append events to a local decision journal."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from copy import deepcopy
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = 1
QUALITY_VALUES = {"good", "mixed", "poor", "uncertain"}
CAUSE_VALUES = {"judgment", "execution", "external", "luck", "insufficient_evidence"}
RULE_ACTIONS = {"keep", "modify", "retire", "none"}
EVENT_TYPES = {"decision", "review", "correction"}
IMMUTABLE_FIELDS = {
    "schema_version",
    "event_type",
    "event_id",
    "decision_id",
    "recorded_at",
}


class JournalError(ValueError):
    """Raised when an event or ledger violates the journal contract."""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_decision_id() -> str:
    return f"D-{date.today().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"


def new_event_id() -> str:
    return f"E-{uuid.uuid4().hex}"


def git_common_dir() -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def default_ledger_path() -> Path:
    common = git_common_dir()
    if common is not None:
        return common / "agent-work" / "decision-journal" / "decision-ledger.jsonl"
    return Path.cwd() / ".agent-work" / "decision-journal" / "decision-ledger.jsonl"


def ledger_path(value: str | None) -> Path:
    return Path(value).expanduser().resolve() if value else default_ledger_path()


def decision_template(decision_id: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "event_type": "decision",
        "event_id": new_event_id(),
        "decision_id": decision_id or new_decision_id(),
        "recorded_at": now_iso(),
        "title": "",
        "context": "",
        "chosen_action": "",
        "evidence": [{"fact": "", "source": ""}],
        "assumptions": [],
        "alternatives": [{"option": "", "reason_not_chosen": ""}],
        "expected_outcomes": [{"signal": "", "target": "", "by": ""}],
        "confidence": 0.5,
        "invalidate_if": [""],
        "review_on": "",
    }


def review_template(decision_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "event_type": "review",
        "event_id": new_event_id(),
        "decision_id": decision_id,
        "recorded_at": now_iso(),
        "observed_outcomes": [{"signal": "", "observed": "", "source": ""}],
        "decision_quality": "uncertain",
        "outcome_quality": "uncertain",
        "causes": ["insufficient_evidence"],
        "lesson": "",
        "rule_update": {"action": "none", "rule": "", "rationale": ""},
        "next_review_on": None,
    }


def correction_template(decision_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "event_type": "correction",
        "event_id": new_event_id(),
        "decision_id": decision_id,
        "recorded_at": now_iso(),
        "corrects_event_id": "",
        "field": "",
        "replacement": None,
        "reason": "",
    }


def require_string(event: dict[str, Any], key: str) -> str:
    value = event.get(key)
    if not isinstance(value, str) or not value.strip():
        raise JournalError(f"{key} must be a non-empty string")
    return value


def require_iso_datetime(value: str, key: str) -> None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise JournalError(f"{key} must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise JournalError(f"{key} must include a timezone")


def require_iso_date(value: Any, key: str, allow_none: bool = False) -> None:
    if value is None and allow_none:
        return
    if not isinstance(value, str):
        raise JournalError(f"{key} must be YYYY-MM-DD")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise JournalError(f"{key} must be YYYY-MM-DD") from exc


def require_string_list(event: dict[str, Any], key: str) -> list[str]:
    value = event.get(key)
    if not isinstance(value, list) or not value:
        raise JournalError(f"{key} must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise JournalError(f"{key} entries must be non-empty strings")
    return value


def require_object_list(
    event: dict[str, Any], key: str, fields: tuple[str, ...], allow_empty: bool = False
) -> list[dict[str, Any]]:
    value = event.get(key)
    if not isinstance(value, list) or (not allow_empty and not value):
        qualifier = "a list" if allow_empty else "a non-empty list"
        raise JournalError(f"{key} must be {qualifier}")
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise JournalError(f"{key}[{index}] must be an object")
        for field in fields:
            field_value = item.get(field)
            if field == "confidence":
                if not isinstance(field_value, (int, float)) or isinstance(field_value, bool):
                    raise JournalError(f"{key}[{index}].confidence must be numeric")
                if not 0.0 <= float(field_value) <= 1.0:
                    raise JournalError(f"{key}[{index}].confidence must be between 0 and 1")
            elif not isinstance(field_value, str) or not field_value.strip():
                raise JournalError(f"{key}[{index}].{field} must be a non-empty string")
    return value


def validate_event(event: Any) -> None:
    if not isinstance(event, dict):
        raise JournalError("event must be a JSON object")
    if event.get("schema_version") != SCHEMA_VERSION:
        raise JournalError(f"schema_version must be {SCHEMA_VERSION}")
    event_type = require_string(event, "event_type")
    if event_type not in EVENT_TYPES:
        raise JournalError(f"event_type must be one of {sorted(EVENT_TYPES)}")
    require_string(event, "event_id")
    require_string(event, "decision_id")
    recorded_at = require_string(event, "recorded_at")
    require_iso_datetime(recorded_at, "recorded_at")

    if event_type == "decision":
        require_string(event, "title")
        require_string(event, "context")
        require_string(event, "chosen_action")
        require_object_list(event, "evidence", ("fact", "source"))
        require_object_list(
            event, "assumptions", ("assumption", "confidence", "test"), allow_empty=True
        )
        require_object_list(event, "alternatives", ("option", "reason_not_chosen"))
        outcomes = require_object_list(
            event, "expected_outcomes", ("signal", "target", "by")
        )
        for index, outcome in enumerate(outcomes):
            require_iso_date(outcome["by"], f"expected_outcomes[{index}].by")
        confidence = event.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            raise JournalError("confidence must be numeric")
        if not 0.0 <= float(confidence) <= 1.0:
            raise JournalError("confidence must be between 0 and 1")
        require_string_list(event, "invalidate_if")
        require_iso_date(event.get("review_on"), "review_on")
        return

    if event_type == "review":
        require_object_list(event, "observed_outcomes", ("signal", "observed", "source"))
        for key in ("decision_quality", "outcome_quality"):
            value = require_string(event, key)
            if value not in QUALITY_VALUES:
                raise JournalError(f"{key} must be one of {sorted(QUALITY_VALUES)}")
        causes = require_string_list(event, "causes")
        invalid_causes = set(causes) - CAUSE_VALUES
        if invalid_causes:
            raise JournalError(f"invalid causes: {sorted(invalid_causes)}")
        require_string(event, "lesson")
        rule_update = event.get("rule_update")
        if not isinstance(rule_update, dict):
            raise JournalError("rule_update must be an object")
        action = rule_update.get("action")
        if action not in RULE_ACTIONS:
            raise JournalError(f"rule_update.action must be one of {sorted(RULE_ACTIONS)}")
        if action != "none" and (
            not isinstance(rule_update.get("rule"), str) or not rule_update["rule"].strip()
        ):
            raise JournalError("rule_update.rule is required unless action is none")
        rationale = rule_update.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise JournalError("rule_update.rationale must be a non-empty string")
        require_iso_date(event.get("next_review_on"), "next_review_on", allow_none=True)
        return

    require_string(event, "corrects_event_id")
    field = require_string(event, "field")
    if field in IMMUTABLE_FIELDS:
        raise JournalError(f"correction cannot change immutable field {field!r}")
    if "replacement" not in event:
        raise JournalError("correction requires replacement")
    require_string(event, "reason")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise JournalError(f"{path} is not strict UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise JournalError(f"{path} is invalid JSON: {exc}") from exc


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise JournalError(f"{path} is not strict UTF-8") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            raise JournalError(f"blank line at ledger line {line_number}")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise JournalError(f"invalid JSON at ledger line {line_number}: {exc}") from exc
        try:
            validate_event(event)
        except JournalError as exc:
            raise JournalError(f"ledger line {line_number}: {exc}") from exc
        events.append(event)
    validate_sequence(events)
    return events


def validate_sequence(events: list[dict[str, Any]]) -> None:
    event_ids: set[str] = set()
    events_by_id: dict[str, dict[str, Any]] = {}
    decisions: dict[str, str] = {}
    for index, event in enumerate(events, 1):
        event_id = event["event_id"]
        decision_id = event["decision_id"]
        if event_id in event_ids:
            raise JournalError(f"duplicate event_id {event_id!r} at event {index}")
        event_ids.add(event_id)
        events_by_id[event_id] = event
        if event["event_type"] == "decision":
            if decision_id in decisions:
                raise JournalError(f"duplicate decision event for {decision_id!r}")
            decisions[decision_id] = event_id
        elif decision_id not in decisions:
            raise JournalError(f"{event['event_type']} precedes decision {decision_id!r}")
        if event["event_type"] == "correction":
            corrected_id = event["corrects_event_id"]
            if corrected_id not in event_ids:
                raise JournalError(f"correction references unknown or later event {corrected_id!r}")
            corrected = events_by_id[corrected_id]
            if corrected["event_type"] == "correction":
                raise JournalError("a correction cannot target another correction")
            if corrected["decision_id"] != decision_id:
                raise JournalError("correction decision_id does not match its target")


def apply_corrections(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return decision/review events with validated top-level corrections applied."""
    effective: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for event in events:
        if event["event_type"] != "correction":
            copied = deepcopy(event)
            effective.append(copied)
            by_id[copied["event_id"]] = copied
            continue
        target = by_id[event["corrects_event_id"]]
        target[event["field"]] = deepcopy(event["replacement"])
        try:
            validate_event(target)
        except JournalError as exc:
            raise JournalError(
                f"correction {event['event_id']!r} makes target invalid: {exc}"
            ) from exc
    return effective


@contextmanager
def exclusive_lock(path: Path, timeout_seconds: float = 10.0) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = path.open("a+b")
    lock_file.seek(0, os.SEEK_END)
    if lock_file.tell() == 0:
        lock_file.write(b"0")
        lock_file.flush()
    deadline = time.monotonic() + timeout_seconds
    acquired = False
    try:
        while not acquired:
            try:
                lock_file.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                if time.monotonic() >= deadline:
                    raise JournalError(f"timed out waiting for ledger lock {path}")
                time.sleep(0.05)
        yield
    finally:
        if acquired:
            lock_file.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


def read_locked(path: Path) -> list[dict[str, Any]]:
    with exclusive_lock(path.with_suffix(path.suffix + ".lock")):
        return load_events(path)


def write_template(event: dict[str, Any], output: str | None, force: bool) -> None:
    payload = json.dumps(event, ensure_ascii=False, indent=2) + "\n"
    if output is None:
        sys.stdout.write(payload)
        return
    path = Path(output).resolve()
    if path.exists() and not force:
        raise JournalError(f"refusing to overwrite existing draft {path}; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    print(path)


def command_template(args: argparse.Namespace) -> None:
    if args.type == "decision":
        event = decision_template(args.decision_id)
    else:
        if not args.decision_id:
            raise JournalError(f"--decision-id is required for {args.type}")
        event = (
            review_template(args.decision_id)
            if args.type == "review"
            else correction_template(args.decision_id)
        )
    write_template(event, args.output, args.force)


def command_check_event(args: argparse.Namespace) -> None:
    event = load_json(Path(args.event).resolve())
    validate_event(event)
    print(f"OK {event['event_type']} {event['event_id']}")


def command_append(args: argparse.Namespace) -> None:
    path = ledger_path(args.ledger)
    event = load_json(Path(args.event).resolve())
    validate_event(event)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with exclusive_lock(lock_path):
        events = load_events(path)
        validate_sequence(events + [event])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    print(f"APPENDED {event['event_id']} decision={event['decision_id']} ledger={path}")


def command_validate(args: argparse.Namespace) -> None:
    path = ledger_path(args.ledger)
    events = read_locked(path)
    print(f"OK {len(events)} events ledger={path}")


def due_items(events: list[dict[str, Any]], as_of: date) -> list[dict[str, str]]:
    decisions: dict[str, dict[str, Any]] = {}
    next_review: dict[str, str | None] = {}
    for event in events:
        decision_id = event["decision_id"]
        if event["event_type"] == "decision":
            decisions[decision_id] = event
            next_review[decision_id] = event["review_on"]
        elif event["event_type"] == "review":
            next_review[decision_id] = event["next_review_on"]
    due: list[dict[str, str]] = []
    for decision_id, review_on in next_review.items():
        if review_on is not None and date.fromisoformat(review_on) <= as_of:
            due.append(
                {
                    "decision_id": decision_id,
                    "title": decisions[decision_id]["title"],
                    "review_on": review_on,
                }
            )
    return sorted(due, key=lambda item: (item["review_on"], item["decision_id"]))


def command_due(args: argparse.Namespace) -> None:
    path = ledger_path(args.ledger)
    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    for item in due_items(apply_corrections(read_locked(path)), as_of):
        print(json.dumps(item, ensure_ascii=False, sort_keys=True))


def command_summary(args: argparse.Namespace) -> None:
    path = ledger_path(args.ledger)
    events = apply_corrections(read_locked(path))
    decisions = [event for event in events if event["event_type"] == "decision"]
    reviews = [event for event in events if event["event_type"] == "review"]
    reviewed_ids = {event["decision_id"] for event in reviews}
    rule_updates = [
        event["rule_update"]
        for event in reviews
        if event["rule_update"]["action"] != "none"
    ]
    quality_matrix: dict[str, int] = {}
    for event in reviews:
        key = f"{event['decision_quality']}|{event['outcome_quality']}"
        quality_matrix[key] = quality_matrix.get(key, 0) + 1
    summary = {
        "ledger": str(path),
        "decisions": len(decisions),
        "review_events": len(reviews),
        "reviewed_decisions": len(reviewed_ids),
        "open_decisions": len(decisions) - len(reviewed_ids),
        "due_today": len(due_items(events, date.today())),
        "quality_matrix": dict(sorted(quality_matrix.items())),
        "candidate_rule_updates": rule_updates,
        "pattern_claims_allowed": len(reviewed_ids) >= 5,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    template = subparsers.add_parser("template", help="create an event draft")
    template.add_argument("--type", choices=sorted(EVENT_TYPES), required=True)
    template.add_argument("--decision-id")
    template.add_argument("--output")
    template.add_argument("--force", action="store_true")
    template.set_defaults(func=command_template)

    check_event = subparsers.add_parser("check-event", help="validate one event draft")
    check_event.add_argument("--event", required=True)
    check_event.set_defaults(func=command_check_event)

    append = subparsers.add_parser("append", help="validate and append one event")
    append.add_argument("--event", required=True)
    append.add_argument("--ledger")
    append.set_defaults(func=command_append)

    validate = subparsers.add_parser("validate", help="validate the full ledger")
    validate.add_argument("--ledger")
    validate.set_defaults(func=command_validate)

    due = subparsers.add_parser("due", help="list decisions due for review")
    due.add_argument("--ledger")
    due.add_argument("--as-of", help="YYYY-MM-DD; defaults to today")
    due.set_defaults(func=command_due)

    summary = subparsers.add_parser("summary", help="summarize journal state")
    summary.add_argument("--ledger")
    summary.set_defaults(func=command_summary)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.func(args)
        return 0
    except (JournalError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
