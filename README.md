# The Baby Field Guide

Forty-two numbered entries, each with the weeks you'd actually encounter it.
A web guide you check things off in, and a script that texts you every few
days about whatever is in season — with a verse on the end.

```
web/index.html      the guide. open it in a browser, no build step.
data/entries.json   the 42 entries. single source of truth.
data/verses.json    16 verses, KJV (public domain — NIV and ESV are not).
data/profile.json   due date, sex, partner's name, your notes.
data/state.json     what's recorded + the send log. committed by CI.
guide.py            week math, selection, pronouns. all deterministic.
compose.py          the only file that calls a model.
deliver.py          console / telegram / twilio, one interface.
sms.py              GSM-7 and segment math.
nudge.py            the entry point.
simulate.py         replays all 65 sends before you send any of them.
```

## Try it in 30 seconds

```bash
pip install -r requirements.txt
python nudge.py --dry-run              # today
python nudge.py --dry-run --week 34    # any week you like
python simulate.py                     # the whole run at once
```

No keys needed. Without `ANTHROPIC_API_KEY` it falls back to a plain
template, which is also what happens in production if the API call fails.

## Setup, in the order that matters

**1. Start the Twilio A2P 10DLC registration today.** Not because you need
it today — because it is the only step that costs calendar time instead of
work time. A US long code will not reliably deliver until your brand and
campaign are approved, and unregistered traffic gets silently filtered:
Twilio reports success, nothing arrives. Sole proprietor registration takes
days to a couple of weeks. Do it first, then ignore it.

**2. Ship on Telegram while you wait.** `@BotFather` → `/newbot` → token.
Message your bot, then hit
`api.telegram.org/bot<TOKEN>/getUpdates` for your chat ID. Ten minutes,
zero registration, and it proves the whole loop end to end.

**3. Fill in `data/profile.json`.** The `notes` field goes into the prompt
verbatim — it is the difference between a generic nudge and one that sounds
like it knows you.

**4. Push, then set secrets.** Settings → Secrets and variables → Actions:
`ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. Set the
`BFG_CHANNEL` *variable* to `telegram`. Run the workflow manually with
dry-run checked before you let the cron have it.

**5. When 10DLC clears,** add the Twilio secrets and flip `BFG_CHANNEL` to
`twilio`. Nothing else changes.

## Design decisions worth not undoing

**Selection is code, generation is copy.** `guide.select()` chooses the
entries. The model only rewrites the wording, and `compose.py` checks the
entry numbers survived before it will send. A model allowed to choose what
to remind you about will eventually invent a deadline that isn't real.

**The verse is never generated.** It rotates by send number through
`verses.json` so all 16 come around before any repeat. Ask a model for
scripture and it will eventually hand you a reference that doesn't say what
it claims.

**Entries retire on a sliding scale.** Soft ones after 3 nags. Hard ones
after 6, or once 8 weeks past their window. Entries flagged `legal` — the
insurance and FSA windows, FMLA notice, the first pediatrician visit —
never retire, because those consequences don't expire just because you
stopped reading. Overdue items also take at most one of the three slots, so
stale reminders can't crowd out what just came in season.

**Cadence tightens as you go.** 3 days early, 2 inside 60, daily inside 3
weeks, weekly after the birth. A constant interval is wrong at both ends.

**Everything is GSM-7.** One curly quote or em dash flips the whole message
to UCS-2 and cuts a segment from 153 characters to 67. `sms.gsm_safe()`
runs on every body; the dry run prints the encoding and segment count so
you can see what a copy change costs. Whole nine months: about $1.62.

**The state commit is load-bearing.** GitHub disables scheduled workflows
after 60 days of repo inactivity, and this project runs for nine months.
Committing `state.json` after each send keeps the schedule alive.

## Not built yet

- Two-way replies. `DONE 014` needs a webhook, which needs a real endpoint
  — the cron alone can't receive. Cheapest path is a Cloudflare Worker.
- Daycare search. Places Text Search for candidates, Place Details for
  hours and ratings, Distance Matrix from home *and* work. Rank on drive
  time, rating floored at 20 reviews, waitlist vs. your start date, and
  closing time against your real pickup. Let the API supply the facts and
  the model only write the summary.
- Shared state. `web/index.html` uses browser storage; swap the `Store`
  object at the top for a Supabase client and you and Alannah see the same
  checkboxes.
- Escalation. When a `legal` entry goes overdue it should text you both,
  not just repeat.
