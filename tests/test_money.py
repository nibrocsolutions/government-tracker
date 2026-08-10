from app.money import extract_mentioned_money


def test_extract_plain_dollar_amount():
    label, value = extract_mentioned_money(
        "County adopts $468,912,088 budget",
        "Property tax remains flat.",
    )
    assert label == "$468,912,088"
    assert value == 468_912_088


def test_extract_million_suffix():
    label, value = extract_mentioned_money("Schools seek $8.13 million in operating support")
    assert "8.13" in label.lower() or "$8.13M" in label or "million" in label.lower()
    assert value == 8_130_000


def test_extract_multiple_keeps_largest_first():
    label, value = extract_mentioned_money(
        "Plan includes $2M for parks and $250,000 for trails",
        None,
    )
    assert value == 2_000_000
    assert "$2M" in label or "$2 m" in label.lower() or "2M" in label.replace(" ", "")
    assert label is not None


def test_extract_no_money():
    label, value = extract_mentioned_money("Board seeking committee applicants", "Applications due soon.")
    assert label is None
    assert value is None
