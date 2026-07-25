#!/usr/bin/env python3
"""The Baby Field Guide — every-few-days nudge.

    python nudge.py --dry-run          preview, sends nothing
    python nudge.py --dry-run --week 34   preview a future week
    python nudge.py                    live send

Run by GitHub Actions on a cron. State lives in data/state.json and
gets committed back after every send, which also keeps the repo active
so GitHub does not disable the schedule after 60 days of quiet.
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import guide
import compose
import deliver
import sms

ROOT = Path(__file__).parent
STATE = ROOT / "data" / "state.json"
CENTRAL = timezone(timedelta(hours=-5))  # CDT; -6 in winter


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"done": [], "log": []}


def save_state(state):
    STATE.write_text(json.dumps(state, indent=1))


def within_quiet_hours(now=None):
    now = now or datetime.now(CENTRAL)
    return 9 <= now.hour < 19


def due_to_send(profile, state, today):
    if not state.get("log"):
        return True
    last = datetime.strptime(state["log"][-1]["sent_at"][:10], "%Y-%m-%d").date()
    return (today - last).days >= guide.cadence_days(profile, today)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--week", type=int, help="pretend it is this week")
    ap.add_argument("--force", action="store_true", help="ignore cadence and quiet hours")
    args = ap.parse_args()

    profile = json.loads((ROOT / "data" / "profile.json").read_text())
    entries = guide.load("entries")
    verses = guide.load("verses")
    state = load_state()

    today = date.today()
    if args.week:
        due = datetime.strptime(profile["due_date"], "%Y-%m-%d").date()
        today = due - timedelta(days=(40 - args.week) * 7)

    if not args.force and not args.dry_run:
        if not within_quiet_hours():
            print("outside 9a-7p Central, skipping")
            return 0
        if not due_to_send(profile, state, today):
            print(f"not due yet (cadence is {guide.cadence_days(profile, today)}d)")
            return 0

    wk, dl = guide.week(profile, today), guide.days_left(profile, today)
    picked = guide.select(entries, profile, state, today)

    if not picked:
        print("nothing in season, skipping")
        return 0

    # resolve pronouns and the partner's name BEFORE the model sees anything
    resolved = [{**e,
                 "title": guide.fill(e["t"], profile),
                 "why": guide.fill(e["why"], profile)} for e in picked]

    phrase = guide.time_phrase(profile, today)
    body = compose.compose(resolved, profile, wk, dl, phrase, dry_run=args.dry_run)
    verse = guide.pick_verse(verses, state)

    body += f"\n\nReply DONE {resolved[0]['no']} to record it."
    body += f"\n{profile.get('url', 'babyfieldguide.app')}"
    body += f'\n\n"{verse["text"]}" - {verse["ref"]}'
    body = sms.gsm_safe(body)

    c = sms.cost(body)
    print(f"week {wk} | {dl}d out | {c['chars']} chars | {c['enc']} | {c['segs']} segment(s)")
    if c["offenders"]:
        print(f"! non-GSM characters survived: {c['offenders']}")
    if c["segs"] > 4:
        print("! over 4 segments, trim the copy")

    if args.dry_run:
        print("\n" + "-" * 52 + "\n" + body + "\n" + "-" * 52)
        return 0

    ref = deliver.send(body)
    state.setdefault("log", []).append({
        "sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "week": wk,
        "entries": [e["no"] for e in resolved],
        "verse": verse["ref"],
        "segments": c["segs"],
        "ref": ref,
    })
    save_state(state)
    print(f"sent {ref}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
