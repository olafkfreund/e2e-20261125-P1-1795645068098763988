"""Unit and CLI tests for the wordfreq package."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wordfreq.cli import count_words, format_table, main

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_module(*args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "wordfreq", *args],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )


# --- count_words -----------------------------------------------------------


def test_count_words_basic_ranking() -> None:
    text = "Apple banana apple, cherry! Banana apple."
    assert count_words(text) == [("apple", 3), ("banana", 2), ("cherry", 1)]


def test_count_words_tie_breaks_alphabetically() -> None:
    assert count_words("zeta beta gamma alpha beta gamma") == [
        ("beta", 2),
        ("gamma", 2),
        ("alpha", 1),
        ("zeta", 1),
    ]


def test_count_words_tokens_are_alphanumeric_runs() -> None:
    # Apostrophes, hyphens, and underscores split tokens; digits are kept.
    assert count_words("don't re-use v2 v2_x") == [
        ("v2", 2),
        ("don", 1),
        ("re", 1),
        ("t", 1),
        ("use", 1),
        ("x", 1),
    ]


def test_count_words_lowercases_by_default() -> None:
    assert count_words("Hello HELLO hello") == [("hello", 3)]


def test_count_words_case_sensitive_keeps_case() -> None:
    assert count_words("Apple apple APPLE apple", ignore_case=False) == [
        ("apple", 2),
        ("APPLE", 1),
        ("Apple", 1),
    ]


def test_count_words_min_len_filters_short_tokens() -> None:
    assert count_words("a bb ccc bb a", min_len=2) == [("bb", 2), ("ccc", 1)]


def test_count_words_top_slices_after_sorting() -> None:
    assert count_words("b a c a b a", top=2) == [("a", 3), ("b", 2)]


def test_count_words_top_zero_returns_empty() -> None:
    assert count_words("a b c", top=0) == []


def test_count_words_empty_text() -> None:
    assert count_words("") == []


def test_count_words_rejects_min_len_below_one() -> None:
    with pytest.raises(ValueError, match=r"^min_len must be >= 1$"):
        count_words("a", min_len=0)


def test_count_words_rejects_negative_top() -> None:
    with pytest.raises(ValueError, match=r"^top must be >= 0$"):
        count_words("a", top=-1)


# --- format_table ----------------------------------------------------------


def test_format_table_tsv() -> None:
    assert format_table([("apple", 3), ("banana", 2)]) == "apple\t3\nbanana\t2"


def test_format_table_empty_returns_empty_string() -> None:
    assert format_table([]) == ""


# --- main: stdin default and argument handling -----------------------------


def test_main_reads_stdin_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("to be or not to be"))
    assert main([]) == 0
    assert capsys.readouterr().out == "be\t2\nto\t2\nnot\t1\nor\t1\n"


def test_main_dash_path_reads_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("x y x"))
    assert main(["-"]) == 0
    assert capsys.readouterr().out == "x\t2\ny\t1\n"


def test_main_case_sensitive_flag_preserves_case(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("Apple apple"))
    assert main(["--case-sensitive"]) == 0
    assert capsys.readouterr().out == "Apple\t1\napple\t1\n"


def test_main_default_lowercases_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("Apple apple"))
    assert main([]) == 0
    assert capsys.readouterr().out == "apple\t2\n"


def test_main_tie_breaking_via_cli(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("b a"))
    assert main([]) == 0
    assert capsys.readouterr().out == "a\t1\nb\t1\n"


def test_main_rejects_min_len_below_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--min-len", "0"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err != ""


def test_main_rejects_negative_top(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--top", "-1"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err != ""


def test_main_rejects_non_integer_top(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--top", "many"]) == 2
    assert capsys.readouterr().err != ""


def test_main_invalid_args_do_not_read_stdin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class _Unreadable:
        def read(self) -> str:
            msg = "stdin should not be read when arguments are invalid"
            raise AssertionError(msg)

    monkeypatch.setattr(sys, "stdin", _Unreadable())
    assert main(["--min-len", "0"]) == 2
    assert capsys.readouterr().err != ""


def test_main_missing_file_returns_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "does-not-exist.txt"
    assert main([str(missing)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err != ""


# --- main: output framing --------------------------------------------------


def test_main_tsv_output_ends_with_single_newline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("one two two", encoding="utf-8")
    assert main([str(sample)]) == 0
    assert capsys.readouterr().out == "two\t2\none\t1\n"


def test_main_tsv_empty_output_prints_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = tmp_path / "empty.txt"
    sample.write_text("", encoding="utf-8")
    assert main([str(sample)]) == 0
    assert capsys.readouterr().out == ""


def test_main_top_zero_prints_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("a b c"))
    assert main(["--top", "0"]) == 0
    assert capsys.readouterr().out == ""


def test_main_json_output_is_array_with_trailing_newline(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("b a b"))
    assert main(["--json"]) == 0
    out = capsys.readouterr().out
    assert out.endswith("\n")
    assert not out.endswith("\n\n")
    assert json.loads(out) == [
        {"word": "b", "count": 2},
        {"word": "a", "count": 1},
    ]


def test_main_json_empty_output_is_empty_array(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert main(["--json"]) == 0
    assert capsys.readouterr().out == "[]\n"


def test_main_top_and_min_len(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("to be or not to be that is the question", encoding="utf-8")
    rc = main([str(sample), "--min-len", "3", "--top", "2"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.strip().splitlines() == ["not\t1", "question\t1"]


# --- python -m wordfreq ----------------------------------------------------


def test_module_entry_point_reads_stdin() -> None:
    result = _run_module(stdin="b a b")
    assert result.returncode == 0
    assert result.stdout == "b\t2\na\t1\n"


def test_module_entry_point_json_trailing_newline() -> None:
    result = _run_module("--json", stdin="hi")
    assert result.returncode == 0
    assert result.stdout.endswith("\n")
    assert json.loads(result.stdout) == [{"word": "hi", "count": 1}]


def test_module_entry_point_missing_file_exit_code_2(tmp_path: Path) -> None:
    result = _run_module(str(tmp_path / "missing.txt"))
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr != ""


def test_module_entry_point_invalid_argument_exit_code_2() -> None:
    result = _run_module("--min-len", "0", stdin="a")
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr != ""
