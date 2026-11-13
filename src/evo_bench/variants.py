"""Variants: the things the search loop is allowed to change.

A variant is a named, reviewable difference from the baseline. Keeping it to
prompt text, model choice, turn budget and tool selection is deliberate: those
are cheap, reversible, and expressible as a diff. Anything that requires editing
the loop itself belongs upstream, not in a campaign.

Layout for one variant::

    benchmarks/variants/strict/
        variant.toml     name, model, max_turns, tools, notes
        system.md        text appended to the baseline system prompt

Both files are optional. A variant with neither is an exact copy of the
baseline, which is a useful control.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TOOLS = ("read", "write", "edit", "bash")


@dataclass(frozen=True, slots=True)
class Variant:
    """One candidate configuration."""

    name: str
    system_addendum: str = ""
    model: str | None = None
    max_turns: int | None = None
    tools: tuple[str, ...] = DEFAULT_TOOLS
    notes: str = ""
    path: Path | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("variant name must not be empty")
        unknown = set(self.tools) - set(DEFAULT_TOOLS)
        if unknown:
            raise ValueError(f"unknown tools in variant {self.name}: {sorted(unknown)}")


def load_variant(path: str | Path) -> Variant:
    """Load one variant directory."""
    directory = Path(path).resolve()
    if not directory.is_dir():
        raise FileNotFoundError(f"no variant at {directory}")

    data: dict = {}
    config = directory / "variant.toml"
    if config.is_file():
        data = tomllib.loads(config.read_text(encoding="utf-8"))

    addendum = ""
    system_file = directory / "system.md"
    if system_file.is_file():
        addendum = system_file.read_text(encoding="utf-8").strip()

    return Variant(
        # The directory name is the identity. A second name inside the file
        # would be a second source of truth, and they drift.
        name=directory.name,
        system_addendum=addendum,
        model=data.get("model"),
        max_turns=data.get("max_turns"),
        tools=tuple(data.get("tools") or DEFAULT_TOOLS),
        notes=str(data.get("notes") or ""),
        path=directory,
    )


def load_variants(directory: str | Path) -> dict[str, Variant]:
    """Load every variant directory under one parent, sorted by name."""
    parent = Path(directory).resolve()
    if not parent.is_dir():
        return {}
    variants = {}
    for child in sorted(parent.iterdir()):
        if child.is_dir():
            variant = load_variant(child)
            variants[variant.name] = variant
    return variants


def compose_system(base: str, variant: Variant) -> str:
    """Append a variant's instructions to the base system prompt."""
    if not variant.system_addendum:
        return base
    return f"{base.rstrip()}\n\n{variant.system_addendum}\n"


def select_tools(variant: Variant, available: list) -> list:
    """Filter a tool list to the ones the variant is allowed to use."""
    allowed = set(variant.tools)
    return [tool for tool in available if tool.name in allowed]
