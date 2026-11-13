"""Tests for the HTML report."""

from __future__ import annotations

from pathlib import Path

from evo_bench.report import build_report, summarise, write_report


def rows() -> list[dict]:
    return [
        {"task_id": "t1", "variant": "baseline", "score": 1.0, "cost": 0.5, "model": "m", "harness": "tau", "harness_version": "0.4.11", "date": "2026-11-13T10:00:00+00:00"},
        {"task_id": "t2", "variant": "baseline", "score": 0.0, "cost": 0.5, "model": "m", "harness": "tau", "harness_version": "0.4.11", "date": "2026-11-13T10:00:00+00:00"},
        {"task_id": "t1", "variant": "strict", "score": 1.0, "cost": 0.7, "model": "m", "harness": "tau", "harness_version": "0.4.11", "date": "2026-11-13T10:00:00+00:00"},
        {"task_id": "t2", "variant": "strict", "score": 1.0, "cost": 0.7, "model": "m", "harness": "tau", "harness_version": "0.4.11", "date": "2026-11-13T10:00:00+00:00"},
    ]


def test_summarise_counts_passes_and_cost():
    stats = summarise(rows(), baseline="baseline")
    by_name = {item.name: item for item in stats}

    assert by_name["baseline"].passes == 1
    assert by_name["strict"].passes == 2
    assert by_name["baseline"].cost == 1.0
    assert by_name["strict"].cost == 1.4
    assert by_name["strict"].delta == 0.5


def test_baseline_is_first_in_the_table():
    text = build_report(rows(), baseline="baseline")
    assert text.index("baseline</td>") < text.index("strict</td>")


def test_report_is_self_contained():
    text = build_report(rows())

    assert "http://" not in text
    assert "https://" not in text
    assert "<script" not in text
    assert "src=" not in text


def test_report_escapes_untrusted_values():
    hostile = [
        {
            "task_id": "<script>alert(1)</script>",
            "variant": "baseline",
            "score": 1.0,
            "cost": 0.0,
        }
    ]
    text = build_report(hostile)

    assert "<script>alert(1)</script>" not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text


def test_report_includes_rate_interval_and_p_value():
    text = build_report(rows(), baseline="baseline")

    assert "100.0%" in text
    assert "95% CI" in text
    assert "0.500" in text or "0.5000" in text or "p" in text


def test_write_report_creates_parent_directories(tmp_path):
    target = tmp_path / "nested" / "report.html"
    path = write_report(target, rows(), baseline="baseline")

    assert Path(path).exists()
    assert "<!DOCTYPE html>" in Path(path).read_text(encoding="utf-8")


def test_missing_cells_render_as_dash():
    partial = [
        {"task_id": "t1", "variant": "baseline", "score": 1.0, "cost": 0.0},
        {"task_id": "t2", "variant": "baseline", "score": 1.0, "cost": 0.0},
        {"task_id": "t1", "variant": "strict", "score": 1.0, "cost": 0.0},
    ]
    text = build_report(partial, baseline="baseline")

    assert "<td class=\"num\">-</td>" in text
