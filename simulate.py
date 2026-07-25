#!/usr/bin/env python3
"""Replay every send from week 1 through 12 weeks after the due date,
against a throwaway copy of state. Uses the real selection, cadence,
and compose logic — nothing here touches data/state.json or sends
anything anywhere. Run this before you trust the schedule with a
real phone number.

    python simulate.py
"""
import json
from datetime import date, timedelta
from pathlib import Path

import compose
import guide
import nudge
import sms

ROOT = Path(__file__).parent
START_DAYS_OUT = 280   # due date minus 40 weeks: week 1
END_DAYS_PAST = 84     # 12 weeks after the due date: week 52


def build_body(entries, profile, verses, state, wk, dl, day):
    resolved = [{**e,
                 "title": guide.fill(e["t"], profile),
                 "why": guide.fill(e["why"], profile)} for e in entries]
    phrase = guide.time_phrase(profile, day)
    body = compose.compose(resolved, profile, wk, dl, phrase, dry_run=True)
    verse = guide.pick_verse(verses, state)
    body += f"\n\nReply DONE {resolved[0]['no']} to record it."
    body += f"\n{profile.get('url', 'babyfieldguide.app')}"
    body += f'\n\n"{verse["text"]}" - {verse["ref"]}'
    return sms.gsm_safe(body), verse, resolved


def main():
    profile = json.loads((ROOT / "data" / "profile.json").read_text())
    entries = guide.load("entries")
    verses = guide.load("verses")
    state = {"done": [], "log": []}

    due = date.fromisoformat(profile["due_date"])
    day = due - timedelta(days=START_DAYS_OUT)
    end = due + timedelta(days=END_DAYS_PAST)

    sent, total_segs = 0, 0
    while day <= end:
        if nudge.due_to_send(profile, state, day):
            wk, dl = guide.week(profile, day), guide.days_left(profile, day)
            picked = guide.select(entries, profile, state, day)
            if picked:
                body, verse, resolved = build_body(picked, profile, verses, state, wk, dl, day)
                c = sms.cost(body)
                sent += 1
                total_segs += c["segs"]
                print(f"[{sent:>3}] {day.isoformat()} | week {wk:>2} | {dl:>4}d out | "
                      f"{c['chars']:>3} chars | {c['enc']:<5} | {c['segs']} seg | "
                      f"entries {[e['no'] for e in resolved]}")
                if c["offenders"]:
                    print(f"      ! non-GSM characters survived: {c['offenders']}")
                if c["segs"] > 4:
                    print("      ! over 4 segments, trim the copy")
                state["log"].append({
                    "sent_at": day.isoformat(),
                    "week": wk,
                    "entries": [e["no"] for e in resolved],
                    "verse": verse["ref"],
                    "segments": c["segs"],
                })
        day += timedelta(days=1)

    cost_per_seg = 0.0079  # Twilio US long code, per segment
    print(f"\n{sent} sends, {total_segs} segments total, "
          f"${total_segs * cost_per_seg:.2f} at ${cost_per_seg}/segment")

    covered = {no for send in state["log"] for no in send["entries"]}
    missed = [e["no"] for e in entries if e["no"] not in covered]
    if missed:
        print(f"never sent: {missed}")


if __name__ == "__main__":
    main()
