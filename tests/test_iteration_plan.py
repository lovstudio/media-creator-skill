from __future__ import annotations

import json
import importlib.util
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "iteration_plan.py"
SPEC = importlib.util.spec_from_file_location("iteration_plan", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
ITERATION_PLAN = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ITERATION_PLAN
SPEC.loader.exec_module(ITERATION_PLAN)

SCHEMA = ITERATION_PLAN.SCHEMA
make_plan = ITERATION_PLAN.make_plan
record_timing = ITERATION_PLAN.record_timing


def state(phase: str, **revisions: str) -> dict:
    return {"schema": SCHEMA, "phase": phase, "revisions": revisions}


def status(plan: dict, stage_id: str) -> str:
    return next(row["status"] for row in plan["stages"] if row["id"] == stage_id)


class IterationPlanTests(unittest.TestCase):
    def test_initial_draft_builds_source_cache_but_blocks_final_work(self) -> None:
        plan = make_plan(None, state("draft", source="source-a", edit="edit-a"))
        self.assertEqual(status(plan, "source-proxies"), "run")
        self.assertEqual(status(plan, "draft-preview"), "run")
        self.assertEqual(status(plan, "final-mezzanine"), "blocked")
        self.assertEqual(status(plan, "final-render"), "blocked")

    def test_subtitle_only_change_reuses_source_media(self) -> None:
        previous = state("draft", source="s1", edit="e1", subtitles="sub1")
        current = state("draft", source="s1", edit="e1", subtitles="sub2")
        plan = make_plan(previous, current)
        self.assertEqual(plan["changed"], ["subtitles"])
        self.assertEqual(status(plan, "source-proxies"), "skip")
        self.assertEqual(status(plan, "draft-preview"), "run")
        self.assertEqual(status(plan, "subtitle-qc"), "run")

    def test_layout_change_does_not_rebuild_mezzanine_or_mix(self) -> None:
        previous = state("approved", source="s1", edit="e1", layout="l1")
        current = state("approved", source="s1", edit="e1", layout="l2")
        plan = make_plan(previous, current)
        self.assertEqual(status(plan, "visual-canary"), "run")
        self.assertEqual(status(plan, "final-mezzanine"), "skip")
        self.assertEqual(status(plan, "final-mix"), "skip")
        self.assertEqual(status(plan, "final-render"), "run")

    def test_edit_change_at_lock_runs_canaries_and_mezzanines_not_final(self) -> None:
        previous = state("draft", source="s1", edit="e1", audio="a1")
        current = state("locked", source="s1", edit="e2", audio="a1")
        plan = make_plan(previous, current)
        self.assertEqual(status(plan, "seam-canary"), "run")
        self.assertEqual(status(plan, "final-mezzanine"), "run")
        self.assertEqual(status(plan, "final-mix"), "run")
        self.assertEqual(status(plan, "final-render"), "blocked")

    def test_approval_promotion_runs_final_without_fake_revision_change(self) -> None:
        previous = state("locked", source="s1", edit="e1", layout="l1")
        current = state("approved", source="s1", edit="e1", layout="l1")
        plan = make_plan(previous, current)
        self.assertEqual(plan["changed"], [])
        self.assertEqual(status(plan, "final-render"), "run")
        self.assertEqual(status(plan, "full-qc"), "run")

    def test_phase_cannot_regress(self) -> None:
        with self.assertRaisesRegex(ValueError, "phase must not regress"):
            make_plan(
                state("approved", source="s1", edit="e1"),
                state("draft", source="s1", edit="e1"),
            )

    def test_timing_record_is_appended(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "timings.json"
            args = Namespace(
                report=report,
                stage="draft-preview",
                started_at="2026-09-01T10:00:00+08:00",
                finished_at="2026-09-01T10:00:03.500+08:00",
                status="passed",
                detail="subtitle-only",
            )
            record_timing(args)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["runs"][0]["elapsed_seconds"], 3.5)
            self.assertEqual(payload["runs"][0]["detail"], "subtitle-only")


if __name__ == "__main__":
    unittest.main()
