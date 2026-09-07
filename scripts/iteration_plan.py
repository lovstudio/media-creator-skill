#!/usr/bin/env python3
"""Plan incremental media work and record stage timings.

The planner keeps cheap review iterations separate from locked/final production.
It uses revision tokens supplied by the project; it never hashes large media files.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "lovstudio/media-iteration/v1"
TIMING_SCHEMA = "lovstudio/media-timings/v1"
PHASES = {"draft": 0, "locked": 1, "approved": 2}
DOMAINS = (
    "source",
    "edit",
    "subtitles",
    "layout",
    "audio",
    "bgm",
    "platform",
    "cover",
)


@dataclass(frozen=True)
class Stage:
    id: str
    triggers: frozenset[str]
    cache_scope: str
    min_phase: str = "draft"


STAGES = (
    Stage("source-index", frozenset({"source"}), "source"),
    Stage("transcript", frozenset({"source"}), "source"),
    Stage("source-proxies", frozenset({"source"}), "source"),
    Stage(
        "draft-preview",
        frozenset({"source", "edit", "subtitles", "layout", "audio", "bgm"}),
        "presentation",
    ),
    Stage("subtitle-qc", frozenset({"edit", "subtitles"}), "timeline"),
    Stage("seam-canary", frozenset({"edit", "audio"}), "timeline"),
    Stage("visual-canary", frozenset({"edit", "layout"}), "presentation"),
    Stage("audio-canary", frozenset({"edit", "audio", "bgm"}), "audio"),
    Stage("final-mezzanine", frozenset({"source", "edit"}), "timeline", "locked"),
    Stage("final-mix", frozenset({"source", "edit", "audio", "bgm"}), "audio", "locked"),
    Stage(
        "final-render",
        frozenset({"source", "edit", "subtitles", "layout", "audio", "bgm", "platform"}),
        "platform",
        "approved",
    ),
    Stage(
        "full-qc",
        frozenset({"source", "edit", "subtitles", "layout", "audio", "bgm", "platform"}),
        "delivery",
        "approved",
    ),
    Stage("cover", frozenset({"cover", "platform"}), "creative"),
)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return value


def validate_state(state: dict[str, Any], label: str) -> None:
    if state.get("schema") != SCHEMA:
        raise ValueError(f"{label}: schema must be {SCHEMA}")
    phase = state.get("phase")
    if phase not in PHASES:
        raise ValueError(f"{label}: phase must be draft, locked, or approved")
    revisions = state.get("revisions")
    if not isinstance(revisions, dict):
        raise ValueError(f"{label}: revisions must be an object")
    unknown = sorted(set(revisions) - set(DOMAINS))
    if unknown:
        raise ValueError(f"{label}: unknown revision domains: {', '.join(unknown)}")
    invalid = sorted(key for key, value in revisions.items() if not isinstance(value, str))
    if invalid:
        raise ValueError(f"{label}: revision tokens must be strings: {', '.join(invalid)}")


def changed_domains(
    previous: dict[str, Any] | None, current: dict[str, Any]
) -> set[str]:
    current_revisions = current.get("revisions", {})
    if previous is None:
        populated = {key for key in DOMAINS if current_revisions.get(key)}
        return populated or set(DOMAINS)
    previous_revisions = previous.get("revisions", {})
    return {
        key
        for key in DOMAINS
        if previous_revisions.get(key, "") != current_revisions.get(key, "")
    }


def make_plan(
    previous: dict[str, Any] | None, current: dict[str, Any]
) -> dict[str, Any]:
    validate_state(current, "current")
    if previous is not None:
        validate_state(previous, "previous")
        if PHASES[current["phase"]] < PHASES[previous["phase"]]:
            raise ValueError(
                f"phase must not regress: {previous['phase']} -> {current['phase']}"
            )

    phase = current["phase"]
    previous_phase = previous["phase"] if previous else None
    changed = changed_domains(previous, current)
    promoted_to_locked = previous is not None and PHASES[previous_phase] < 1 <= PHASES[phase]
    promoted_to_approved = previous is not None and PHASES[previous_phase] < 2 <= PHASES[phase]
    initial = previous is None
    rows: list[dict[str, Any]] = []

    for stage in STAGES:
        triggered = bool(changed & stage.triggers)
        if stage.id in {"final-mezzanine", "final-mix"} and promoted_to_locked:
            triggered = True
        if stage.id in {"final-render", "full-qc"} and promoted_to_approved:
            triggered = True

        if PHASES[phase] < PHASES[stage.min_phase]:
            status = "blocked" if triggered or initial else "skip"
            reason = f"requires phase {stage.min_phase}; current phase is {phase}"
        elif triggered:
            status = "run"
            matched = sorted(changed & stage.triggers)
            if not matched:
                matched = [f"phase:{previous_phase}->{phase}"]
            reason = "invalidated by " + ", ".join(matched)
        else:
            status = "skip"
            reason = f"cache reusable ({stage.cache_scope})"

        rows.append(
            {
                "id": stage.id,
                "status": status,
                "reason": reason,
                "cache_scope": stage.cache_scope,
                "min_phase": stage.min_phase,
            }
        )

    summary = {
        status: sum(1 for row in rows if row["status"] == status)
        for status in ("run", "skip", "blocked")
    }
    return {
        "schema": SCHEMA,
        "phase": phase,
        "previous_phase": previous_phase,
        "changed": sorted(changed),
        "revisions": {key: current.get("revisions", {}).get(key, "") for key in DOMAINS},
        "stages": rows,
        "summary": summary,
        "rule": "run only invalidated stages; blocked stages wait for their phase gate",
    }


def parse_time(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include a timezone: {value}")
    return parsed


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def record_timing(args: argparse.Namespace) -> dict[str, Any]:
    stage_ids = {stage.id for stage in STAGES}
    if args.stage not in stage_ids:
        raise ValueError(f"unknown stage: {args.stage}")
    started = parse_time(args.started_at)
    finished = parse_time(args.finished_at)
    elapsed = (finished - started).total_seconds()
    if elapsed < 0:
        raise ValueError("finished-at must not be earlier than started-at")
    report = (
        read_json(args.report)
        if args.report.exists()
        else {"schema": TIMING_SCHEMA, "runs": []}
    )
    if report.get("schema") != TIMING_SCHEMA or not isinstance(report.get("runs"), list):
        raise ValueError(f"{args.report}: expected {TIMING_SCHEMA} with a runs array")
    entry = {
        "stage": args.stage,
        "status": args.status,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "elapsed_seconds": elapsed,
    }
    if args.detail:
        entry["detail"] = args.detail
    report["runs"].append(entry)
    report["updated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_write_json(args.report, report)
    return entry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="compare two iteration state files")
    plan_parser.add_argument("--current", required=True, type=Path)
    plan_parser.add_argument("--previous", type=Path)
    plan_parser.add_argument("--output", type=Path)

    record_parser = subparsers.add_parser("record", help="append one stage timing")
    record_parser.add_argument("--report", required=True, type=Path)
    record_parser.add_argument("--stage", required=True)
    record_parser.add_argument("--started-at", required=True)
    record_parser.add_argument("--finished-at", required=True)
    record_parser.add_argument(
        "--status", choices=("passed", "failed", "cancelled"), default="passed"
    )
    record_parser.add_argument("--detail")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "plan":
            current = read_json(args.current)
            previous = read_json(args.previous) if args.previous else None
            result = make_plan(previous, current)
            if args.output:
                atomic_write_json(args.output, result)
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            result = record_timing(args)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
