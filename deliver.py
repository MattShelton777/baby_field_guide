"""console / telegram / twilio, one interface.

send(body) -> ref string, or raises. Channel picked by the BFG_CHANNEL
env var so switching from Telegram to Twilio once 10DLC clears is a
one-variable change, nothing else in nudge.py touches this.
"""
import os
import urllib.request
import urllib.parse
import json


def _console(body: str) -> str:
    print(body)
    return "console"


def _telegram(body: str) -> str:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": body}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get("ok"):
        raise RuntimeError(f"telegram send failed: {payload}")
    return f"telegram:{payload['result']['message_id']}"


def _twilio(body: str) -> str:
    from twilio.rest import Client

    sid = os.environ["TWILIO_ACCOUNT_SID"]
    token = os.environ["TWILIO_AUTH_TOKEN"]
    from_ = os.environ["TWILIO_FROM"]
    to = os.environ["TWILIO_TO"]
    client = Client(sid, token)
    msg = client.messages.create(body=body, from_=from_, to=to)
    return f"twilio:{msg.sid}"


CHANNELS = {"console": _console, "telegram": _telegram, "twilio": _twilio}


def send(body: str) -> str:
    channel = os.environ.get("BFG_CHANNEL", "console")
    if channel not in CHANNELS:
        raise ValueError(f"unknown BFG_CHANNEL {channel!r}, expected one of {list(CHANNELS)}")
    return CHANNELS[channel](body)
