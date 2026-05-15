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
from menu import menu_as_text, MENU_BY_NR, EXTRAS_BY_ID, EXTRA_TOPPING_PRICE
from balance_tracker import record_usage

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    log.error("OPENAI_API_KEY not set")
    sys.exit(1)

WEB_APP_URL = os.getenv("WEB_APP_URL", "http://127.0.0.1:8104")
CODEC = "pcm_24000"

INSTRUCTIONS = f"""Du är en trevlig receptionist på Pizzeria Elken. Du svarar på svenska.
Du tar emot pizzabeställningar via telefon.

Här är vår meny:
{menu_as_text()}

GLUTENFRI BOTTEN: Alla pizzor kan fås med glutenfri botten för 25 kr extra.
ÄNDRINGAR: Kunden kan lägga till extra pålägg (+10 kr/st) eller ta bort ingredienser (gratis).
Exempel: "En Älguvio med extra kantareller utan ost" = Älguvio + extra kantareller (10 kr) - ost.
DRYCKER & TILLBEHÖR: Vi har Tjärncola/Tjärnapelsin/Tjärncitron (26 kr), Källvatten (16 kr), Älgörtssaft (46 kr), Skogsbärsdricka (36 kr), Björksav (36 kr), Lingondricka (26 kr), sallader och såser.

Så här gör du:
1. Hälsa kunden välkommen till Pizzeria Elken
2. Fråga vad de vill beställa
3. Om kunden säger ett pizzanummer eller namn, bekräfta valet
4. Om kunden vill ändra något på pizzan (extra pålägg eller ta bort ingredienser), notera det
5. Fråga om de vill ha glutenfri botten (25 kr extra per pizza)
6. Fråga om de vill ha något att dricka eller andra tillbehör
7. Fråga om de vill ha fler pizzor
8. Fråga kundens namn
9. Sammanfatta beställningen med totalpris och anropa submit_order
10. Bekräfta att ordern är lagd och säg att pizzan är klar om en kvart (femton minuter)
11. Säg att de kommer få SMS när pizzan är klar

Om kunden frågar om ingredienser, svara utifrån menyn.
Var trevlig och naturlig, som en riktig pizzeria-receptionist.
Håll svaren korta — det är ett telefonsamtal."""

CHANGE_INSTRUCTIONS = """Du är en trevlig receptionist på Pizzeria Elken. Du svarar på svenska.
Kunden ringer tillbaka för att ändra en befintlig beställning.

Kundens nuvarande beställning (order #{order_id}):
{order_items}
Totalt: {total_price} kr

GLUTENFRI BOTTEN: Alla pizzor kan fås med glutenfri botten för 25 kr extra.
ÄNDRINGAR: Kunden kan lägga till extra pålägg (+10 kr/st) eller ta bort ingredienser (gratis).
DRYCKER & TILLBEHÖR: Vi har Tjärncola/Tjärnapelsin/Tjärncitron (26 kr), Källvatten (16 kr), Älgörtssaft (46 kr), Skogsbärsdricka/Björksav (36 kr), Lingondricka (26 kr), sallader och såser.

Så här gör du:
1. Hälsa kunden välkommen tillbaka och säg att du ser deras beställning
2. Läs upp vad de har beställt
3. Fråga vad de vill ändra (byta pizza, ändra pålägg, lägga till dricka, etc.)
4. När kunden har bestämt sig, sammanfatta den nya beställningen och anropa update_order
5. Bekräfta ändringen

Var trevlig och naturlig, som en riktig pizzeria-receptionist.
Håll svaren korta — det är ett telefonsamtal."""

PIZZA_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "pizza_nr": {"type": "integer", "description": "Pizzans nummer från menyn (1-46)"},
        "quantity": {"type": "integer", "description": "Antal av denna pizza"},
        "glutenfri": {"type": "boolean", "description": "True om kunden vill ha glutenfri botten (+25 kr)"},
        "extra_toppings": {
            "type": "array",
            "description": "Extra pålägg som kunden vill ha (t.ex. 'bearnaisesås', 'bacon', 'champinjoner'). 10 kr styck.",
            "items": {"type": "string"},
        },
        "without": {
            "type": "array",
            "description": "Ingredienser kunden vill ta bort (t.ex. 'ost', 'lök', 'tomatsås'). Gratis.",
            "items": {"type": "string"},
        },
    },
    "required": ["pizza_nr", "quantity"],
}

EXTRA_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "extra_id": {
            "type": "string",
            "description": "ID för tillbehöret: drink_coca_cola, drink_fanta, drink_sprite, drink_water, salad_house, salad_caesar, candy_daim, candy_kexchoklad, candy_ahlgrens, dip_garlic, dip_bearnaise",
        },
        "quantity": {"type": "integer", "description": "Antal"},
    },
    "required": ["extra_id", "quantity"],
}

ORDER_TOOL = {
    "type": "function",
    "name": "submit_order",
    "description": "Lägg en beställning när kunden har bestämt sig och sagt sitt namn",
    "parameters": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "description": "Lista av pizzor att beställa",
                "items": PIZZA_ITEM_SCHEMA,
            },
            "extras": {
                "type": "array",
                "description": "Lista av drycker, sallader, godis och tillbehör",
                "items": EXTRA_ITEM_SCHEMA,
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
            "extras": {
                "type": "array",
                "description": "Den nya listan av drycker, sallader, godis och tillbehör",
                "items": EXTRA_ITEM_SCHEMA,
            },
        },
        "required": ["items"],
    },
}


GLUTENFRI_EXTRA = 25


def build_items(raw_items):
    """Parse order items, apply glutenfri/topping/removal pricing."""
    items = []
    total = 0
    for item in raw_items:
        pizza = MENU_BY_NR.get(item["pizza_nr"])
        if not pizza:
            continue
        qty = item.get("quantity", 1)
        glutenfri = item.get("glutenfri", False)
        extra_toppings = item.get("extra_toppings", [])
        without = item.get("without", [])

        price = pizza["price"]
        if glutenfri:
            price += GLUTENFRI_EXTRA
        price += len(extra_toppings) * EXTRA_TOPPING_PRICE

        # Bygg visningsnamn med modifieringar
        name = pizza["name"]
        mods = []
        if glutenfri:
            mods.append("glutenfri")
        for t in extra_toppings:
            mods.append(f"+{t}")
        for w in without:
            mods.append(f"utan {w}")
        if mods:
            name = f"{name} ({', '.join(mods)})"

        entry = {
            "pizza_nr": pizza["nr"],
            "name": name,
            "qty": qty,
            "price": price,
        }
        if glutenfri:
            entry["glutenfri"] = True
        if extra_toppings:
            entry["extra_toppings"] = extra_toppings
        if without:
            entry["without"] = without
        items.append(entry)
        total += price * qty
    return items, total


def build_extras(raw_extras):
    """Parse extras (drinks, salads, etc.)."""
    items = []
    total = 0
    for item in raw_extras:
        extra = EXTRAS_BY_ID.get(item.get("extra_id", ""))
        if not extra:
            continue
        qty = item.get("quantity", 1)
        items.append({
            "name": extra["name"],
            "price": extra["price"],
            "qty": qty,
            "type": "extra",
        })
        total += extra["price"] * qty
    return items, total


def process_order(order_data, customer_phone, call_id):
    """Send order to Flask web app."""
    pizza_items, pizza_total = build_items(order_data["items"])
    extra_items, extra_total = build_extras(order_data.get("extras", []))
    all_items = pizza_items + extra_items
    total = pizza_total + extra_total

    payload = {
        "customer_name": order_data["customer_name"],
        "customer_phone": customer_phone,
        "items": all_items,
        "total_price": total,
        "call_id": call_id,
    }

    try:
        resp = requests.post(f"{WEB_APP_URL}/api/orders", json=payload, timeout=5)
        if resp.ok:
            order = resp.json()
            log.info("Order #%s created: %s", order["id"], all_items)
            return {"success": True, "order_id": order["id"], "total_price": total}
        else:
            log.error("Failed to create order: %s", resp.text)
            return {"success": False, "error": "Kunde inte lägga ordern"}
    except Exception as e:
        log.error("Error posting order: %s", e)
        return {"success": False, "error": str(e)}


def process_update_order(order_id, order_data):
    """Update an existing order."""
    pizza_items, pizza_total = build_items(order_data["items"])
    extra_items, extra_total = build_extras(order_data.get("extras", []))
    all_items = pizza_items + extra_items
    total = pizza_total + extra_total

    payload = {"items": all_items, "total_price": total}

    try:
        resp = requests.post(f"{WEB_APP_URL}/api/orders/{order_id}/update", json=payload, timeout=5)
        if resp.ok:
            log.info("Order #%s updated: %s", order_id, all_items)
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
        greeting = "Hälsa kunden välkommen till Pizzeria Elken och fråga vad de vill beställa."

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

    call_usage = []  # Accumulate usage from response.done events

    async def openai_to_elks():
        """OpenAI audio → caller + handle function calls."""
        function_call_args = {}
        order_submitted = False

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
                            if result.get("success"):
                                order_submitted = True
                        except json.JSONDecodeError:
                            result = {"success": False, "error": "Ogiltiga argument"}
                    elif fn_name == "update_order" and change_order:
                        try:
                            order_data = json.loads(fn_args_str)
                            result = process_update_order(change_order["id"], order_data)
                            if result.get("success"):
                                order_submitted = True
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

                elif event_type == "response.done":
                    usage = msg.get("response", {}).get("usage")
                    if usage:
                        call_usage.append(usage)

                    # Hang up after the confirmation response following a successful order
                    if order_submitted:
                        log.info("Order confirmed — hanging up in 1s")
                        await asyncio.sleep(1)
                        try:
                            await elks_ws.send(json.dumps({"type": "hangup"}))
                            log.info("Hangup sent to 46elks")
                        except Exception as e:
                            log.warning("Failed to send hangup: %s", e)
                        break

                elif event_type == "error":
                    error = msg.get("error", {})
                    if error.get("code") != "response_cancel_not_active":
                        log.error("OpenAI error: %s", error)

        except websockets.exceptions.ConnectionClosed:
            pass

    await asyncio.gather(elks_to_openai(), openai_to_elks())

    # Record OpenAI usage and check balance
    if call_usage:
        try:
            result = record_usage(call_id, caller, call_usage)
            log.info(
                "Usage recorded: call=$%.4f total=$%.2f remaining=$%.2f",
                result["call_cost"], result["total_spent"], result["remaining"],
            )
        except Exception as e:
            log.error("Failed to record usage: %s", e)

    log.info("Call ended: call_id=%s from=%s", call_id, caller)


async def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8103
    log.info("Pizza voice agent starting on port %d", port)

    async with websockets.serve(handle_call, "0.0.0.0", port):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
