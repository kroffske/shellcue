from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "src" / "shellcue"


def test_source_has_no_private_package_or_lab_imports() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in SOURCE.rglob("*.py")
    ).lower()

    forbidden = (
        "smart" + "_bash",
        "kaggle",
        "huggingface_hub",
        "src.data",
        "src.eval",
    )
    assert not any(name in source for name in forbidden)
    assert not re.search(r"(?:from|import)\s+shellcue\.(?:data|eval|training|integrations)", source)


def test_runtime_tree_contains_only_public_owners() -> None:
    top_level = {path.name for path in SOURCE.iterdir() if path.name != "__pycache__"}

    assert top_level == {"__init__.py", "cli.py", "core", "models", "runtime"}
    forbidden_directories = {"data", "eval", "training", "notebooks", "scripts"}
    assert not any((ROOT / name).exists() for name in forbidden_directories)
    assert not any(path.name in forbidden_directories for path in SOURCE.rglob("*"))
