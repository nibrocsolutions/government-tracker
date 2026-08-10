"""Extract dollar figures mentioned in story text."""

from __future__ import annotations

import re

# $1,234.56 / $2.5 million / $3M / $400k / $1.2 billion
_DOLLAR_RE = re.compile(
    r"""
    \$\s*
    (?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)
    \s*
    (?P<suffix>trillion|billion|million|thousand|bn|mm|m|b|k)?
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# 2.5 million dollars / 400 thousand dollars
_WORDS_RE = re.compile(
    r"""
    (?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)
    \s*
    (?P<suffix>trillion|billion|million|thousand)
    \s+dollars?\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

_SUFFIX_MULTIPLIER = {
    "k": 1_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "mm": 1_000_000,
    "million": 1_000_000,
    "b": 1_000_000_000,
    "bn": 1_000_000_000,
    "billion": 1_000_000_000,
    "trillion": 1_000_000_000_000,
}


def _parse_amount(num_text: str, suffix: str | None) -> float | None:
    try:
        value = float(num_text.replace(",", ""))
    except ValueError:
        return None
    if suffix:
        value *= _SUFFIX_MULTIPLIER.get(suffix.lower(), 1)
    # Avoid binary float noise from decimal suffixes (e.g. 8.13 * 1e6)
    return round(value, 2)


def _format_amount(value: float) -> str:
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        text = f"${value / 1_000_000_000:.2f}".rstrip("0").rstrip(".") + "B"
    elif abs_value >= 1_000_000:
        text = f"${value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"
    elif abs_value >= 1_000:
        text = f"${value / 1_000:.2f}".rstrip("0").rstrip(".") + "K"
    elif value == int(value):
        text = f"${int(value):,}"
    else:
        text = f"${value:,.2f}"
    return text


def extract_mentioned_money(title: str, summary: str | None = None) -> tuple[str | None, float | None]:
    """Return (display text, largest numeric value) for money figures in the story."""
    text = f"{title or ''} {summary or ''}"
    found: list[tuple[str, float]] = []
    seen_spans: set[tuple[int, int]] = set()

    for pattern in (_DOLLAR_RE, _WORDS_RE):
        for match in pattern.finditer(text):
            span = match.span()
            # Skip overlapping captures from the second pattern
            if any(not (span[1] <= s[0] or span[0] >= s[1]) for s in seen_spans):
                continue
            amount = _parse_amount(match.group("num"), match.group("suffix"))
            if amount is None or amount <= 0:
                continue
            seen_spans.add(span)
            display = match.group(0).strip()
            if display.startswith("$"):
                # Normalize spacing in raw dollar matches
                display = re.sub(r"\$\s+", "$", display)
                display = re.sub(r"\s+", " ", display)
            else:
                display = _format_amount(amount)
            found.append((display, amount))

    if not found:
        return None, None

    # Prefer the largest figure as primary; keep unique display labels in size order
    found.sort(key=lambda item: item[1], reverse=True)
    labels: list[str] = []
    for label, _ in found:
        if label not in labels:
            labels.append(label)
        if len(labels) == 3:
            break
    return ", ".join(labels), found[0][1]
