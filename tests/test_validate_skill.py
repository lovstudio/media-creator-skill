from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_skill.py"
SPEC = importlib.util.spec_from_file_location("validate_skill", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATE
SPEC.loader.exec_module(VALIDATE)

SKILL_MD = Path(__file__).resolve().parents[1] / "SKILL.md"
PREFLIGHT_ERROR = "dependencies must be a list of {name, check, install} entries"


def frontmatter_errors(dependencies_yaml: str) -> list[str]:
    """Validate the real SKILL.md with its `dependencies:` block swapped for `dependencies_yaml`."""
    text = SKILL_MD.read_text(encoding="utf-8")
    head, rest = text.split("dependencies:\n", 1)
    _, tail = rest.split("metadata:\n", 1)
    patched = head + dependencies_yaml + "metadata:\n" + tail
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "SKILL.md"
        path.write_text(patched, encoding="utf-8")
        errors: list[str] = []
        VALIDATE.validate_skill_file(path, errors)
    return errors


class InstallPreflightTests(unittest.TestCase):
    def test_current_skill_md_passes(self) -> None:
        errors: list[str] = []
        VALIDATE.validate_skill_file(SKILL_MD, errors)
        self.assertEqual(errors, [])

    def test_optional_publisher_entry_is_declared(self) -> None:
        data, _ = VALIDATE.split_frontmatter(SKILL_MD)
        names = [item["name"] for item in data["dependencies"]]
        self.assertTrue(any(name.startswith("lov-media-publisher") for name in names))
        self.assertNotIn("lov-media-publisher", data["depends_on"])

    def test_missing_install_is_rejected(self) -> None:
        errors = frontmatter_errors('dependencies:\n  - name: "x"\n    check: "true"\n')
        self.assertTrue(any(PREFLIGHT_ERROR in e for e in errors))

    def test_unknown_key_is_rejected(self) -> None:
        errors = frontmatter_errors(
            'dependencies:\n  - name: "x"\n    check: "true"\n    install: "true"\n    optional: true\n'
        )
        self.assertTrue(any(PREFLIGHT_ERROR in e for e in errors))

    def test_non_list_is_rejected(self) -> None:
        errors = frontmatter_errors('dependencies: "lov-media-publisher"\n')
        self.assertTrue(any(PREFLIGHT_ERROR in e for e in errors))


if __name__ == "__main__":
    unittest.main()
