"""GSM-7 encoding and segment math.

Twilio bills per segment. Any character outside the GSM-7 alphabet
flips the *entire* message to UCS-2, which cuts a segment from 153
characters down to 67. Mirrors the JS in web/index.html exactly so
the dry-run preview and the live send never disagree about cost.
"""

GSM7 = (
    "@£$¥èéùìòÇ\nØø\r"
    "ÅåΔ_ΦΓΛΩΠΨΣΘ"
    "ΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿ "
    "abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7EXT = "^{}\\[~]|€"

_REPLACEMENTS = (
    ("‘", "'"), ("’", "'"),
    ("“", '"'), ("”", '"'),
    ("–", "-"), ("—", "-"),
    ("←", "<-"),
    ("·", "-"),
    ("…", "..."),
)


def gsm_safe(text: str) -> str:
    """Strip the common typographic characters that would flip the
    message to UCS-2 (curly quotes, em/en dash, ellipsis, middle dot,
    left arrow). Run on every body before it is measured or sent."""
    for bad, good in _REPLACEMENTS:
        text = text.replace(bad, good)
    return text


def cost(text: str) -> dict:
    """Character count, encoding, segment count, and any offending
    characters that survived gsm_safe() (e.g. from a model-generated
    body that wasn't run through it)."""
    chars = list(text)
    n = 0
    offenders = []
    for c in chars:
        if c in GSM7:
            n += 1
        elif c in GSM7EXT:
            n += 2
        else:
            offenders.append(c)

    if offenders:
        length = len(chars)
        segs = 1 if length <= 70 else -(-length // 67)
        return {"chars": length, "enc": "UCS-2", "segs": segs,
                "offenders": sorted(set(offenders))}

    segs = 1 if n <= 160 else -(-n // 153)
    return {"chars": n, "enc": "GSM-7", "segs": segs, "offenders": []}
