"""The deterministic half. Nothing here calls a model.

Entry selection, week math, and pronouns are all rules. The only
thing the API is allowed to do is rewrite the wording, which is
what keeps it from inventing a deadline that isn't real.
"""
import json
from datetime import date, datetime
from pathlib import Path

DATA = Path(__file__).parent / "data"

PRONOUNS = {
    "boy":      {"he": "he",   "He": "He",   "him": "him",  "his": "his"},
    "girl":     {"he": "she",  "He": "She",  "him": "her",  "his": "her"},
    "surprise": {"he": "they", "He": "They", "him": "them", "his": "their"},
}


def load(name):
    return json.loads((DATA / f"{name}.json").read_text())


def fill(text: str, profile: dict) -> str:
    """Resolve {Pn} {P} {he} {He} {him} {his}. Must run before the
    text reaches the API — a model that sees a raw token will either
    echo it into your SMS or invent its own pronoun."""
    p = PRONOUNS.get(profile.get("sex", "boy"), PRONOUNS["boy"])
    name = profile.get("partner") or "your partner"
    text = text.replace("{Pn}", name).replace("{P}", f"{name}'s")
    for token, word in p.items():
        text = text.replace("{" + token + "}", word)
    return text


def days_left(profile, today=None) -> int:
    today = today or date.today()
    due = datetime.strptime(profile["due_date"], "%Y-%m-%d").date()
    return (due - today).days


def week(profile, today=None) -> int:
    return max(1, min(52, 40 - days_left(profile, today) // 7))


def status(entry, wk, done) -> str:
    if entry["id"] in done:
        return "recorded"
    if wk < entry["w"][0]:
        return "later"
    if wk > entry["w"][1]:
        return "overdue"
    return "in_season"


def select(entries, profile, state, today=None, limit=3, cooldown_days=9,
           soft_nag_cap=3, hard_nag_cap=6, overdue_slots=1):
    """Overdue first, then hard deadlines, then whatever closes soonest.

    An entry nudged within the cooldown drops out — unless it has gone
    overdue, at which point it earns the right to nag again.

    Two guards learned from replaying the whole pregnancy:
      - Entries retire on a sliding scale. Soft ones after 3 nags: if
        he has ignored the baby shower three times, he has decided.
        Hard ones after 6, or once 8 weeks past their window, because
        nagging about daycare research the week after the birth is
        noise. Entries flagged `legal` never retire at all — the
        insurance and FSA windows have consequences that do not expire
        just because he stopped reading.
      - Overdue items take at most `overdue_slots` of the three, so
        stale reminders can never crowd out what just came in season.
    """
    wk = week(profile, today)
    done = set(state.get("done", []))
    today = today or date.today()

    recent, nag_count = set(), {}
    for send in state.get("log", []):
        sent = datetime.strptime(send["sent_at"][:10], "%Y-%m-%d").date()
        for no in send["entries"]:
            nag_count[no] = nag_count.get(no, 0) + 1
        if (today - sent).days < cooldown_days:
            recent.update(send["entries"])

    overdue, in_season = [], []
    for e in entries:
        st = status(e, wk, done)
        if st == "overdue":
            nags, stale = nag_count.get(e["no"], 0), wk - e["w"][1]
            if e.get("legal"):
                pass                          # regulatory. never retires.
            elif e.get("hard"):
                if nags >= hard_nag_cap or stale > 8:
                    continue                  # the moment has passed
            elif nags >= soft_nag_cap:
                continue                      # he has decided. let it go.
            overdue.append(e)
        elif st == "in_season" and e["no"] not in recent:
            in_season.append(e)

    close_soonest = lambda e: (0 if e.get("hard") else 1, e["w"][1])
    # Overdue entries share one slot, so tie-break on fewest nags first —
    # otherwise whichever entry's window closed earliest (021, FMLA notice)
    # wins that slot forever and starves every legal entry behind it.
    overdue.sort(key=lambda e: (0 if e.get("hard") else 1, nag_count.get(e["no"], 0), e["w"][1]))
    in_season.sort(key=close_soonest)

    picked = overdue[:overdue_slots]
    picked += in_season[:limit - len(picked)]
    if len(picked) < limit:                   # nothing new? let overdue fill
        picked += [e for e in overdue[overdue_slots:]][:limit - len(picked)]
    return picked


def pick_verse(verses, state):
    """Rotate by send number. Random picking eventually hands you the
    same verse twice in one week."""
    return verses[len(state.get("log", [])) % len(verses)]


def cadence_days(profile, today=None) -> int:
    """Every 3 days is right for most of the pregnancy and wrong at the
    end. Tighten as the due date closes, then back off after."""
    dl = days_left(profile, today)
    if dl < 0:
        return 7      # post-birth: only the hard deadlines matter
    if dl <= 21:
        return 1
    if dl <= 60:
        return 2
    return 3


def time_phrase(profile, today=None) -> str:
    """"-21 days out" is not a sentence anyone should receive."""
    dl = days_left(profile, today)
    if dl >= 0:
        return f"Week {week(profile, today)}. {dl} days out."
    return f"Day {abs(dl)}."
