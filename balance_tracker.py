#!/usr/bin/env python3
"""OpenAI Realtime API balance tracker with SMS alerts.

Tracks spending per call, persists cumulative totals to data/balance.json,
and sends SMS alerts via 46elks when remaining balance drops below thresholds.
"""

import json
import logging
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
BALANCE_FILE = DATA_DIR / "balance.json"

# 46elks credentials (same as voice_agent)
ELKS_API_USER = os.getenv("ELKS_API_USER")
ELKS_API_PASS = os.getenv("ELKS_API_PASS")
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "")

# OpenAI budget settings
STARTING_BALANCE = float(os.getenv("OPENAI_STARTING_BALANCE", "50.0"))
BALANCE_THRESHOLD = float(os.getenv("OPENAI_BALANCE_THRESHOLD", "20.0"))

# OpenAI Realtime API pricing (USD per 1M tokens)
# gpt-4o-realtime-preview-2024-12-17
PRICING = {
    "text_input": 5.00,
    "text_output": 20.00,
    "audio_input": 100.00,
    "audio_output": 200.00,
    "cached_text_input": 2.50,
    "cached_audio_input": 20.00,
}

# Alert levels (fractions of threshold)
ALERT_LEVELS = [
    ("threshold", lambda t: t),
    ("half", lambda t: t / 2),
    ("ten", lambda _: 10.0),
    ("five", lambda _: 5.0),
]


def _load_state():
    """Load balance state from disk."""
    if BALANCE_FILE.exists():
        try:
            return json.loads(BALANCE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            log.warning("Corrupt balance file, resetting")
    return {
        "starting_balance": STARTING_BALANCE,
        "total_spent": 0.0,
        "total_calls": 0,
        "alerts_sent": [],
        "calls": [],
    }


def _save_state(state):
    """Persist balance state to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BALANCE_FILE.write_text(json.dumps(state, indent=2))


def _send_alert_sms(message):
    """Send SMS alert to admin phone."""
    if not ADMIN_PHONE or not ELKS_API_USER or not ELKS_API_PASS:
        log.warning("Cannot send alert SMS: missing ADMIN_PHONE or 46elks credentials")
        return False
    try:
        resp = requests.post(
            "https://api.46elks.com/a1/sms",
            auth=(ELKS_API_USER, ELKS_API_PASS),
            data={"from": "OpenAI", "to": ADMIN_PHONE, "message": message},
            timeout=10,
        )
        log.info("Alert SMS sent to %s (status=%s)", ADMIN_PHONE, resp.status_code)
        return resp.ok
    except Exception as e:
        log.error("Failed to send alert SMS: %s", e)
        return False


def calculate_cost(usage):
    """Calculate USD cost from a response.done usage object.

    Expected format:
    {
        "total_tokens": int,
        "input_tokens": int,
        "output_tokens": int,
        "input_token_details": {
            "cached_tokens": int,
            "text_tokens": int,
            "audio_tokens": int
        },
        "output_token_details": {
            "text_tokens": int,
            "audio_tokens": int
        }
    }
    """
    if not usage:
        return 0.0

    input_details = usage.get("input_token_details", {})
    output_details = usage.get("output_token_details", {})

    cached_text = input_details.get("cached_tokens", 0)
    cached_audio = 0  # Realtime API doesn't always separate cached audio
    text_input = input_details.get("text_tokens", 0)
    audio_input = input_details.get("audio_tokens", 0)
    text_output = output_details.get("text_tokens", 0)
    audio_output = output_details.get("audio_tokens", 0)

    cost = (
        (text_input / 1_000_000) * PRICING["text_input"]
        + (audio_input / 1_000_000) * PRICING["audio_input"]
        + (text_output / 1_000_000) * PRICING["text_output"]
        + (audio_output / 1_000_000) * PRICING["audio_output"]
        + (cached_text / 1_000_000) * PRICING["cached_text_input"]
        + (cached_audio / 1_000_000) * PRICING["cached_audio_input"]
    )

    return round(cost, 6)


def record_usage(call_id, caller, usage_list):
    """Record usage from one or more response.done events for a call.

    Args:
        call_id: The 46elks call ID
        caller: The caller phone number
        usage_list: List of usage dicts from response.done events
    """
    call_cost = sum(calculate_cost(u) for u in usage_list)

    state = _load_state()
    state["starting_balance"] = STARTING_BALANCE
    state["total_spent"] += call_cost
    state["total_calls"] += 1

    # Keep last 100 calls for reference
    state["calls"] = state.get("calls", [])
    state["calls"].append({
        "call_id": call_id,
        "caller": caller,
        "cost": call_cost,
        "responses": len(usage_list),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    state["calls"] = state["calls"][-100:]

    remaining = STARTING_BALANCE - state["total_spent"]

    log.info(
        "Call %s cost: $%.4f | Total spent: $%.2f | Remaining: $%.2f",
        call_id, call_cost, state["total_spent"], remaining,
    )

    # Check alert levels
    alerts_sent = set(state.get("alerts_sent", []))
    for level_name, level_fn in ALERT_LEVELS:
        level_value = level_fn(BALANCE_THRESHOLD)
        if remaining <= level_value and level_name not in alerts_sent:
            msg = (
                f"OpenAI Saldolarm ({level_name})\n"
                f"Kvarvarande: ${remaining:.2f}\n"
                f"Totalt spenderat: ${state['total_spent']:.2f}\n"
                f"Antal samtal: {state['total_calls']}\n"
                f"Senaste samtal: ${call_cost:.4f}"
            )
            if _send_alert_sms(msg):
                alerts_sent.add(level_name)
                log.warning("Alert sent for level '%s': $%.2f remaining", level_name, remaining)

    state["alerts_sent"] = list(alerts_sent)
    _save_state(state)

    return {
        "call_cost": call_cost,
        "total_spent": state["total_spent"],
        "remaining": remaining,
    }
