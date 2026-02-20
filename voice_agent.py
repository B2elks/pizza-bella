#!/usr/bin/env python3
"""Pizza ordering voice agent bridging 46elks WebSocket to OpenAI Realtime API.

Customers call in, OpenAI takes the order via voice, then submits it
to the Flask web app via HTTP POST.

Usage:
    python voice_agent.py [port]
"""

import asyncio
import json
import logging
import os
import sys

import requests
import websockets
from dotenv import load_dotenv
from menu import menu_as_text, MENU_BY_NR

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    log.error("OPENAI_API_KEY not set")
    sys.exit(1)

WEB_APP_URL = os.getenv("WEB_APP_URL", "http://127.0.0.1:8104")
CODEC = "pcm_24000"

INSTRUCTIONS = f"""Du är en trevlig receptionist på Pizzeria Bella. Du svarar på svenska.
Du tar emot pizzabeställningar via telefon.

Här är vår meny:
{menu_as_text()}

GLUTENFRI BOTTEN: Alla pizzor kan fås med glutenfri botten för 25 kr extra.
Fråga alltid kunden om de vill ha vanlig eller glutenfri botten.

Så här gör du:
1. Hälsa kunden välkommen till Pizzeria Bella
2. Fråga vad de vill beställa
3. Om kunden säger ett pizzanummer eller namn, bekräfta valet
4. Fråga om de vill ha glutenfri botten (25 kr extra per pizza)
5. Fråga om de vill ha fler pizzor
6. Fråga kundens namn
7. Sammanfatta beställningen med totalpris och anropa submit_order
8. Bekräfta att ordern är lagd och säg att pizzan tar ca 15-20 minuter
9. Säg att de kommer få SMS när pizzan är klar

Om kunden frågar om ingredienser, svara utifrån menyn.
Var trevlig och naturlig, som en riktig pizzeria-receptionist.
Håll svaren korta — det är ett telefonsamtal."""

CHANGE_INSTRUCTIONS = """Du är en trevlig receptionist på Pizzeria Bella. Du svarar på svenska.
Kunden ringer tillbaka för att ändra en befintlig beställning.

Kundens nuvarande beställning (order #{order_id}):
{order_items}
Totalt: {total_price} kr

GLUTENFRI BOTTEN: Alla pizzor kan fås med glutenfri botten för 25 kr extra.

Så här gör du:
1. Hälsa kunden välkommen tillbaka och säg att du ser deras beställning
2. Läs upp vad de har beställt
3. Fråga vad de vill ändra
4. När kunden har bestämt sig, sammanfatta den nya beställningen och anropa update_order
5. Bekräfta ändringen

Var trevlig och naturlig, som en riktig pizzeria-receptionist.
Håll svaren korta — det är ett telefonsamtal."""

PIZZA_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "pizza_nr": {"type": "integer", "description": "Pizzans nummer från menyn (1-71)"},
        "quantity": {"type": "integer", "description": "Antal av denna pizza"},
        "glutenfri": {"type": "boolean", "description": "True om kunden vill ha glutenfri botten (+25 kr)"},
    },
    "required": ["pizza_nr", "quantity"],
}

ORDER_TOOL = {
    "type": "function",
    "name": "submit_order",
    "description": "Lägg en pizzabeställning när kunden har bestämt sig och sagt sitt namn",
    "parameters": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "description": "Lista av pizzor att beställa",
                "items": PIZZA_ITEM_SCHEMA,
            },
            "customer_name": {
                "type": "string",
                "description": "Kundens namn",
            },
        },
        "required": ["items", "customer_name"],
    },
}

UPDATE_ORDER_TOOL = {
    "type": "function",
    "name": "update_order",
    "description": "Uppdatera en befintlig beställning som kunden vill ändra",
    "parameters": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "description": "Den nya listan av pizzor (ersätter hela beställningen)",
                "items": PIZZA_ITEM_SCHEMA,
            },
        },
        "required": ["items"],
    },
}


GLUTENFRI_EXTRA = 25


def build_items(raw_items):
    """Parse order items, apply glutenfri pricing."""
    items = []
    total = 0
    for item in raw_items:
        pizza = MENU_BY_NR.get(item["pizza_nr"])
        if not pizza:
            continue
        qty = item.get("quantity", 1)
        glutenfri = item.get("glutenfri", False)
        price = pizza["price"] + (GLUTENFRI_EXTRA if glutenfri else 0)
        entry = {
            "pizza_nr": pizza["nr"],
            "name": pizza["name"],
            "qty": qty,
            "price": price,
        }
        if glutenfri:
            entry["glutenfri"] = True
        items.append(entry)
        total += price * qty
    return items, total


def process_order(order_data, customer_phone, call_id):
    """Send order to Flask web app."""
    items, total = build_items(order_data["items"])

    payload = {
        "customer_name": order_data["customer_name"],
        "customer_phone": customer_phone,
        "items": items,
        "total_price": total,
        "call_id": call_id,
    }

    try:
        resp = requests.post(f"{WEB_APP_URL}/api/orders", json=payload, timeout=5)
        if resp.ok:
            order = resp.json()
            log.info("Order #%s created: %s", order["id"], items)
            return {"success": True, "order_id": order["id"], "total_price": total}
        else:
            log.error("Failed to create order: %s", resp.text)
            return {"success": False, "error": "Kunde inte lägga ordern"}
    except Exception as e:
        log.error("Error posting order: %s", e)
        return {"success": False, "error": str(e)}


def process_update_order(order_id, order_data):
    """Update an existing order."""
    items, total = build_items(order_data["items"])

    payload = {"items": items, "total_price": total}

    try:
        resp = requests.post(f"{WEB_APP_URL}/api/orders/{order_id}/update", json=payload, timeout=5)
        if resp.ok:
            log.info("Order #%s updated: %s", order_id, items)
            return {"success": True, "order_id": order_id, "total_price": total}
        else:
            log.error("Failed to update order: %s", resp.text)
            return {"success": False, "error": "Kunde inte uppdatera ordern"}
    except Exception as e:
        log.error("Error updating order: %s", e)
        return {"success": False, "error": str(e)}


def check_change_order(caller_phone):
    """Check if caller has a pending 'change' order."""
    try:
        resp = requests.get(
            f"{WEB_APP_URL}/api/orders/by-phone",
            params={"phone": caller_phone, "status": "change"},
            timeout=5,
        )
        if resp.ok:
            orders = resp.json()
            if orders:
                return orders[0]  # Most recent change order
    except Exception as e:
        log.error("Failed to check change orders: %s", e)
    return None


async def handle_call(elks_ws):
    """Handle a single phone call: bridge 46elks ↔ OpenAI Realtime."""
    log.info("New WebSocket connection from %s", elks_ws.remote_address)

    data = json.loads(await elks_ws.recv())
    if data.get("type") != "call_started":
        log.error("Expected call_started, got: %s", data.get("type"))
        return

    call_id = data.get("call_id", "unknown")
    caller = data.get("from", "unknown")
    called = data.get("to", "unknown")
    log.info("Call started: call_id=%s from=%s to=%s", call_id, caller, called)

    # Check if this caller has a pending change order
    change_order = check_change_order(caller)
    if change_order:
        order_items = ", ".join(
            f"{i['qty']}x {i['name']}" + (" (glutenfri)" if i.get("glutenfri") else "")
            for i in change_order["items"]
        )
        instructions = CHANGE_INSTRUCTIONS.format(
            order_id=change_order["id"],
            order_items=order_items,
            total_price=change_order["total_price"],
        )
        tools = [UPDATE_ORDER_TOOL]
        greeting = (
            f"Hälsa kunden välkommen tillbaka. Säg att du ser deras beställning "
            f"(order #{change_order['id']}): {order_items}, totalt {change_order['total_price']} kr. "
            f"Fråga vad de vill ändra."
        )
        log.info("Change order found: #%s for %s", change_order["id"], caller)
    else:
        instructions = INSTRUCTIONS
        tools = [ORDER_TOOL]
        greeting = "Hälsa kunden välkommen till Pizzeria Bella och fråga vad de vill beställa."

    await elks_ws.send(json.dumps({"type": "start_stream", "stream": "agent", "codec": CODEC}))
    await elks_ws.send(json.dumps({"type": "start_stream", "stream": "caller", "codec": CODEC}))

    openai_ws = await websockets.connect(
        "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17",
        additional_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1",
        },
    )
    log.info("Connected to OpenAI Realtime")

    await openai_ws.send(json.dumps({
        "type": "session.update",
        "session": {
            "modalities": ["audio", "text"],
            "instructions": instructions,
            "voice": "alloy",
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {"model": "whisper-1"},
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.7,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 800,
            },
            "tools": tools,
        },
    }))

    await openai_ws.send(json.dumps({
        "type": "response.create",
        "response": {
            "modalities": ["audio", "text"],
            "instructions": greeting,
        },
    }))

    async def elks_to_openai():
        """Caller audio → OpenAI (both 24kHz PCM, base64)."""
        try:
            async for message in elks_ws:
                msg = json.loads(message)
                if msg.get("type") == "audio":
                    await openai_ws.send(json.dumps({
                        "type": "input_audio_buffer.append",
                        "audio": msg["data"],
                    }))
                elif msg.get("type") == "close":
                    log.info("Call closed by 46elks")
                    break
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await openai_ws.close()

    async def openai_to_elks():
        """OpenAI audio → caller + handle function calls."""
        function_call_args = {}

        try:
            async for message in openai_ws:
                msg = json.loads(message)
                event_type = msg.get("type")

                if event_type == "response.audio.delta":
                    await elks_ws.send(json.dumps({"type": "audio", "data": msg["delta"]}))

                elif event_type == "input_audio_buffer.speech_started":
                    log.info("User speaking — cancelling assistant response")
                    await openai_ws.send(json.dumps({"type": "response.cancel"}))
                    await elks_ws.send(json.dumps({"type": "cancel_stream", "stream": "agent"}))
                    await elks_ws.send(json.dumps({"type": "start_stream", "stream": "agent", "codec": CODEC}))

                elif event_type == "response.function_call_arguments.delta":
                    call_item_id = msg.get("call_id", "")
                    if call_item_id not in function_call_args:
                        function_call_args[call_item_id] = ""
                    function_call_args[call_item_id] += msg.get("delta", "")

                elif event_type == "response.function_call_arguments.done":
                    fn_call_id = msg.get("call_id", "")
                    fn_name = msg.get("name", "")
                    fn_args_str = msg.get("arguments", "{}")

                    log.info("Function call: %s(%s)", fn_name, fn_args_str)

                    result = None
                    if fn_name == "submit_order":
                        try:
                            order_data = json.loads(fn_args_str)
                            result = process_order(order_data, caller, call_id)
                        except json.JSONDecodeError:
                            result = {"success": False, "error": "Ogiltiga argument"}
                    elif fn_name == "update_order" and change_order:
                        try:
                            order_data = json.loads(fn_args_str)
                            result = process_update_order(change_order["id"], order_data)
                        except json.JSONDecodeError:
                            result = {"success": False, "error": "Ogiltiga argument"}

                    if result is not None:
                        await openai_ws.send(json.dumps({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": fn_call_id,
                                "output": json.dumps(result),
                            },
                        }))
                        await openai_ws.send(json.dumps({"type": "response.create"}))

                    function_call_args.pop(fn_call_id, None)

                elif event_type == "conversation.item.input_audio_transcription.completed":
                    log.info("Kund: %s", msg.get("transcript", "").strip())

                elif event_type == "response.audio_transcript.done":
                    log.info("Bella: %s", msg.get("transcript", "").strip())

                elif event_type == "error":
                    error = msg.get("error", {})
                    if error.get("code") != "response_cancel_not_active":
                        log.error("OpenAI error: %s", error)

        except websockets.exceptions.ConnectionClosed:
            pass

    await asyncio.gather(elks_to_openai(), openai_to_elks())
    log.info("Call ended: call_id=%s from=%s", call_id, caller)


async def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8103
    log.info("Pizza voice agent starting on port %d", port)

    async with websockets.serve(handle_call, "0.0.0.0", port):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
