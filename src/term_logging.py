"""Small terminal logging helpers with optional ANSI colors."""

from __future__ import annotations

import os
import sys


def _supports_color() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    return sys.stdout.isatty()


_USE_COLOR = _supports_color()


def _color(text: str, code: str) -> str:
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def _prefix(tag: str, color_code: str) -> str:
    return _color(f"[{tag}]", color_code)


def section(title: str) -> None:
    line = "=" * 60
    print(f"\n{_color(line, '2')}")
    print(_color(title, "1;36"))
    print(_color(line, "2"))


def info(message: str) -> None:
    print(f"{_prefix('INFO', '36')} {message}")


def success(message: str) -> None:
    print(f"{_prefix(' OK ', '32')} {message}")


def warn(message: str) -> None:
    print(f"{_prefix('WARN', '33')} {message}")


def error(message: str) -> None:
    print(f"{_prefix('ERR ', '31')} {message}")


def step(message: str) -> None:
    print(f"{_prefix('....', '35')} {message}")


def metric_box(title: str, rows: list[tuple[str, str]], color_code: str = "34") -> None:
    """Print a colored box with key/value metrics."""
    if not rows:
        return
    key_width = max(len(key) for key, _ in rows)
    value_width = max(len(value) for _, value in rows)
    inner_width = key_width + 3 + value_width
    top = f"┌{'─' * (inner_width + 2)}┐"
    bottom = f"└{'─' * (inner_width + 2)}┘"
    print(_color(top, color_code))
    print(_color(f"│ {title:<{inner_width}} │", color_code))
    print(_color(f"├{'─' * (inner_width + 2)}┤", color_code))
    for key, value in rows:
        print(_color(f"│ {key:<{key_width}} : {value:<{value_width}} │", color_code))
    print(_color(bottom, color_code))


def table_box(title: str, headers: list[str], rows: list[list[str]], color_code: str = "34") -> None:
    """Print a colored box containing a plain text table."""
    if not headers:
        return

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(cell))

    def _fmt_row(values: list[str]) -> str:
        cells = [f"{values[i]:<{col_widths[i]}}" for i in range(len(col_widths))]
        return " | ".join(cells)

    header_line = _fmt_row(headers)
    separator = "-+-".join("-" * w for w in col_widths)
    data_lines = [_fmt_row(row) for row in rows]

    inner_width = max(len(title), len(header_line), len(separator), *(len(line) for line in data_lines or [""]))
    top = f"┌{'─' * (inner_width + 2)}┐"
    bottom = f"└{'─' * (inner_width + 2)}┘"

    print(_color(top, color_code))
    print(_color(f"│ {title:<{inner_width}} │", color_code))
    print(_color(f"├{'─' * (inner_width + 2)}┤", color_code))
    print(_color(f"│ {header_line:<{inner_width}} │", color_code))
    print(_color(f"│ {separator:<{inner_width}} │", color_code))
    for line in data_lines:
        print(_color(f"│ {line:<{inner_width}} │", color_code))
    print(_color(bottom, color_code))
