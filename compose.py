"""The only file that calls a model.

guide.select() has already decided which entries appear and guide.fill()
has already resolved every pronoun and the partner's name. All the model
is allowed to do is rewrite the wording into one text message. It cannot
add an entry, drop one, or touch the verse — and compose() checks the
entry numbers survived before it will hand the body back.

Falls back to a plain template if ANTHROPIC_API_KEY is unset, the
`anthropic` package isn't installed, or the API call fails for any
reason — same fallback path in a dry run and in production.
"""
from __future__ import annotations

import os

import sms

SYSTEM = """You write one SMS for an expecting father, from a project called \
The Baby Field Guide. You are a copywriter, not a planner: the entries \
below are fixed and already in the right order. Rewrite their wording \
into a single warm, direct, lightly wry text in the voice of a friend \
who has done this before — never chirpy, never corporate.

Rules, no exceptions:
- Keep every entry number exactly as given (e.g. "021") at the start of \
its line, followed by " - " and the rewritten line.
- Do not add, remove, reorder, or merge entries.
- Do not invent dates, deadlines, prices, or facts not in the entry.
- Do not include a verse, sign-off, link, or reply instructions — those \
are appended after you.
- Plain ASCII punctuation only: straight quotes, hyphens, no em dashes, \
no curly quotes, no emoji.
- Open with the one-line time phrase given, then the entries, one per line.
- Keep the whole thing well under 600 characters.
"""


def _template(entries, phrase) -> str:
    lines = [phrase, ""]
    for e in entries:
        tag = " (hard deadline)" if e.get("hard") else ""
        lines.append(f"{e['no']} - {e['title']}{tag}")
    return "\n".join(lines)


def _notes_block(profile) -> str:
    notes = (profile.get("notes") or "").strip()
    if not notes:
        return ""
    return f"\nWhat the writer should know about this reader: {notes}\n"


def _call_model(entries, profile, wk, dl, phrase) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    entry_block = "\n".join(
        f"{e['no']} - {e['title']}{' (hard deadline)' if e.get('hard') else ''}"
        f"\n    why: {e['why']}"
        for e in entries
    )
    user = (
        f"Time phrase: {phrase}\n\n"
        f"Entries for this send:\n{entry_block}\n"
        f"{_notes_block(profile)}"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=400,
            system=SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(
            block.text for block in resp.content if block.type == "text"
        ).strip()
        return text or None
    except Exception:
        return None


def _entry_numbers_survived(body: str, entries) -> bool:
    return all(e["no"] in body for e in entries)


def compose(entries, profile, wk, dl, phrase, dry_run=False) -> str:
    # dry_run still calls the model when a key is present, so the preview
    # shows what production would actually send.
    body = _call_model(entries, profile, wk, dl, phrase)
    body = sms.gsm_safe(body) if body else None

    if not body or not _entry_numbers_survived(body, entries):
        return _template(entries, phrase)

    return body
