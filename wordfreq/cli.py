"""Command-line entry point and word frequency helpers for wordfreq."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")


def count_words(
    text: str,
    *,
    min_len: int = 1,
    ignore_case: bool = True,
    top: int | None = None,
) -> list[tuple[str, int]]:
    """Count word occurrences in *text* and return `(word, count)` pairs."""
    if min_len < 1:
        msg = "min_len must be >= 1"
        raise ValueError(msg)
    if top is not None and top < 0:
        msg = "top must be >= 0"
        raise ValueError(msg)

    tokens = _TOKEN_PATTERN.findall(text)
    if ignore_case:
        tokens = [token.lower() for token in tokens]
    counts = Counter(token for token in tokens if len(token) >= min_len)
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    if top is not None:
        return ranked[:top]
    return ranked


def format_table(rows: Sequence[tuple[str, int]]) -> str:
    """Format `(word, count)` pairs as tab-separated lines."""
    return "\n".join(f"{word}\t{count}" for word, count in rows)


def _bounded_int(minimum: int, label: str) -> Callable[[str], int]:
    """Build an argparse type that accepts integers no smaller than *minimum*."""

    def parse(raw: str) -> int:
        try:
            value = int(raw)
        except ValueError:
            msg = f"invalid integer value: {raw!r}"
            raise argparse.ArgumentTypeError(msg) from None
        if value < minimum:
            msg = f"{label} must be >= {minimum}"
            raise argparse.ArgumentTypeError(msg)
        return value

    return parse


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wordfreq",
        description="Deterministically count and rank words in text.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="-",
        help="UTF-8 text file to read; '-' or omitted reads from stdin",
    )
    parser.add_argument(
        "--top",
        type=_bounded_int(0, "top"),
        default=None,
        help="show only the N most frequent words (default: all)",
    )
    parser.add_argument(
        "--min-len",
        type=_bounded_int(1, "min_len"),
        default=1,
        help="ignore words shorter than M characters (default: 1)",
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="count words without lowercasing them",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit a JSON array of {word, count} objects",
    )
    return parser


def _read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the wordfreq CLI and return the process exit code."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse has already written usage or error text to stderr; convert
        # its exit into a return code so callers always receive an int.
        return int(exc.code or 0)

    try:
        text = _read_text(args.path)
    except (OSError, UnicodeDecodeError) as exc:
        reason = getattr(exc, "strerror", None) or exc
        print(f"wordfreq: error: cannot read {args.path!r}: {reason}", file=sys.stderr)
        return 2

    rows = count_words(
        text,
        min_len=args.min_len,
        ignore_case=not args.case_sensitive,
        top=args.top,
    )

    if args.json:
        payload = [{"word": word, "count": count} for word, count in rows]
        print(json.dumps(payload))
    elif rows:
        print(format_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
