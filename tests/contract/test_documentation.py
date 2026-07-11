"""Repository documentation layout and relative-link checks."""

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).parents[2]
MARKDOWN_LINK = re.compile(r"!?\[[^]]*]\(([^)]+)\)")
GENERATED_DIRECTORIES = {
    ".codex",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "build",
    "dist",
}


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if GENERATED_DIRECTORIES.isdisjoint(path.relative_to(ROOT).parts)
        and not any(part.endswith(".egg-info") for part in path.relative_to(ROOT).parts)
    )


def test_user_facing_markdown_lives_under_docs() -> None:
    allowed_outside_docs = {
        ROOT / "CHANGELOG.md",
        ROOT / "README.md",
        ROOT / "tests" / "contract" / "README.md",
        ROOT / "tests" / "integration" / "demo" / "README.md",
    }
    misplaced = [
        path
        for path in markdown_files()
        if path not in allowed_outside_docs
        and ROOT / "docs" not in path.parents
        and ROOT / "openspec" not in path.parents
    ]
    assert misplaced == []


def test_relative_markdown_links_resolve() -> None:
    broken: list[str] = []
    for source in markdown_files():
        for raw_target in MARKDOWN_LINK.findall(source.read_text()):
            target = raw_target.strip().strip("<>").split(maxsplit=1)[0]
            if target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            relative = unquote(target.split("#", 1)[0])
            if relative and not (source.parent / relative).resolve().exists():
                broken.append(f"{source.relative_to(ROOT)} -> {target}")
    assert broken == []
