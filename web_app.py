#!/usr/bin/env python3
"""Pizza order dashboard and API.

Serves the dashboard, accepts orders from the voice agent,
manages order lifecycle, and sends SMS notifications via 46elks.

Usage:
    python web_app.py [port]
"""

import hashlib
import json
import os
import sqlite3
import sys
import threading
from datetime import datetime

import requests
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, send_from_directory

load_dotenv()

app = Flask(__name__, static_folder="static")

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "data", "orders.db"))
ELKS_API_USER = os.getenv("ELKS_API_USER")
ELKS_API_PASS = os.getenv("ELKS_API_PASS")
PIZZA_PHONE = os.getenv("PIZZA_PHONE", "+46766867485")
BASE_URL = os.getenv("BASE_URL", "https://pizza.skyttberg.nu")

# Token secret for generating phone-based tracking tokens
TOKEN_SECRET = os.getenv("TOKEN_SECRET", "bellaPizza2026!")


def phone_to_token(phone):
    """Generate a stable URL token from a phone number."""
    return hashlib.sha256(f"{TOKEN_SECRET}:{phone}".encode()).hexdigest()[:16]


def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


ORDER_EXPIRE_SECONDS = 15 * 60  # Orders auto-expire after 15 minutes


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            customer_phone TEXT,
            items TEXT,
            total_price INTEGER,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            call_id TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS unavailable (
            pizza_nr INTEGER PRIMARY KEY,
            reason TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS unavailable_ingredients (
            ingredient TEXT PRIMARY KEY
        )
    """)
    # Add token column if it doesn't exist
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN token TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.commit()
    conn.close()


def expire_old_orders():
    """Move orders older than 15 minutes to 'done' status."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """UPDATE orders SET status = 'done'
           WHERE status NOT IN ('done', 'cancelled')
           AND created_at < datetime('now', ?)""",
        (f"-{ORDER_EXPIRE_SECONDS} seconds",),
    )
    conn.commit()
    conn.close()


def start_expire_timer():
    """Run expire check every 30 seconds."""
    def _loop():
        while True:
            try:
                expire_old_orders()
            except Exception as e:
                app.logger.error("Expire error: %s", e)
            import time
            time.sleep(30)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()


def send_sms(to, message):
    if not ELKS_API_USER or not ELKS_API_PASS:
        app.logger.warning("46elks credentials not set, skipping SMS to %s: %s", to, message)
        return False
    try:
        resp = requests.post(
            "https://api.46elks.com/a1/sms",
            auth=(ELKS_API_USER, ELKS_API_PASS),
            data={"from": PIZZA_PHONE, "to": to, "message": message},
            timeout=10,
        )
        app.logger.info("SMS sent to %s: %s (status=%s)", to, message[:50], resp.status_code)
        return resp.ok
    except Exception as e:
        app.logger.error("SMS failed to %s: %s", to, e)
        return False


def schedule_feedback_sms(order_id):
    """Send feedback SMS 1 hour after pickup."""
    def _send():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if row and row["customer_phone"]:
            send_sms(
                row["customer_phone"],
                f"Hej {row['customer_name']}! Tack för besöket på Pizzeria Elken. "
                f"Hur var maten? Svara 1-5 stjärnor!",
            )
            conn.execute("UPDATE orders SET status = 'done' WHERE id = ?", (order_id,))
            conn.commit()
        conn.close()

    timer = threading.Timer(3600, _send)
    timer.daemon = True
    timer.start()
    app.logger.info("Feedback SMS scheduled for order #%s in 1 hour", order_id)


def order_to_dict(row):
    return {
        "id": row["id"],
        "customer_name": row["customer_name"],
        "customer_phone": row["customer_phone"],
        "items": json.loads(row["items"]),
        "total_price": row["total_price"],
        "status": row["status"],
        "created_at": row["created_at"],
        "call_id": row["call_id"] if "call_id" in row.keys() else "",
        "token": row["token"] if "token" in row.keys() else "",
    }


# --- Dashboard routes ---

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/llms.txt")
def llms_txt():
    content = """# pizzanummer.se

> pizzanummer.se är en live-demo av AI-driven telefonbeställning, byggd med 46elks röst-API. Besökare kan ringa ett svenskt telefonnummer och beställa pizza genom att prata med en AI-agent som förstår naturligt tal, tar emot beställningen och skickar orderbekräftelse via SMS.

## Huvudsida

- [Startsida](https://pizzanummer.se/): Pizzeria Elken — beställ pizza via AI-telefon. Meny med 46 älgpizzor och tillbehör.

## Vad är pizzanummer.se?

pizzanummer.se är en teknisk demonstration av 46elks AI-telefoni. Den visar hur ett företag kan ta emot beställningar helt automatiskt via telefon med hjälp av artificiell intelligens. Kunden ringer, pratar med en AI-agent, och får sin order bekräftad via SMS med en spårningslänk.

## Kärnfakta

- AI-röstbeställning via telefon med naturligt svenskt tal
- 46 älgpizzor på menyn, från 46 kr
- Automatisk orderbekräftelse via SMS
- Realtids-orderspårning via personlig länk
- Byggt med 46elks Voice API och Flask (Python)
- Live-demo av teknologin bakom aitelefon.se och aitelefonnummer.se

## Relaterade tjänster

- [aitelefon.se](https://aitelefon.se): AI-telefon för företag — intelligent telefonväxel med naturligt tal
- [aitelefonnummer.se](https://aitelefonnummer.se): AI-telefonnummer — automatiserad receptionist dygnet runt
- [smsnummer.se](https://smsnummer.se): Dedikerade SMS-nummer för företag med tvåvägs-SMS och AI-svar
- [46elks.com](https://46elks.com/se): SMS, MMS och telefoni-API för utvecklare

## Teknisk information

- API-dokumentation: https://46elks.com/docs
- Registrering: https://46elks.com/register/pizzanummer
- Backend: Python Flask + 46elks Voice API
- Röst: Neural text-till-tal (TTS) på svenska
- Beställning: Realtids-taligenkänning (ASR) + LLM-tolkning
"""
    return app.response_class(content, mimetype="text/plain")


@app.route("/robots.txt")
def robots_txt():
    content = "User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /t/\nSitemap: https://pizzanummer.se/sitemap.xml\n"
    return app.response_class(content, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += '  <url>\n'
    xml += '    <loc>https://pizzanummer.se/</loc>\n'
    xml += '    <changefreq>weekly</changefreq>\n'
    xml += '    <priority>1.0</priority>\n'
    xml += '  </url>\n'
    xml += '</urlset>\n'
    return app.response_class(xml, mimetype="application/xml")


# --- Customer tracking page ---

@app.route("/t/<token>")
def tracking_page(token):
    return send_from_directory("static", "track.html")


@app.route("/api/track/<token>")
def track_order(token):
    """Get the latest active order for this tracking token."""
    db = get_db()
    # Find order by token
    row = db.execute(
        """SELECT * FROM orders WHERE token = ?
           AND status NOT IN ('done', 'cancelled')
           ORDER BY created_at DESC LIMIT 1""",
        (token,),
    ).fetchone()
    if not row:
        # Also try finding by checking all phone numbers (for old orders without token)
        rows = db.execute(
            "SELECT * FROM orders WHERE status NOT IN ('done', 'cancelled') ORDER BY created_at DESC"
        ).fetchall()
        for r in rows:
            if r["customer_phone"] and phone_to_token(r["customer_phone"]) == token:
                row = r
                break
    if not row:
        return jsonify({"error": "no_order"}), 404

    order = order_to_dict(row)
    # Check if order can still be modified
    order["can_modify"] = row["status"] in ("new", "change")
    return jsonify(order)


@app.route("/api/track/<token>/add-extra", methods=["POST"])
def add_extra(token):
    """Customer adds an extra item to their order."""
    from menu import EXTRAS_BY_ID

    data = request.get_json()
    extra_id = data.get("extra_id", "") if data else ""
    if extra_id not in EXTRAS_BY_ID:
        return jsonify({"error": "Unknown extra"}), 400

    db = get_db()
    row = db.execute(
        """SELECT * FROM orders WHERE token = ?
           AND status IN ('new', 'change')
           ORDER BY created_at DESC LIMIT 1""",
        (token,),
    ).fetchone()
    if not row:
        return jsonify({"error": "Order cannot be modified"}), 403

    extra = EXTRAS_BY_ID[extra_id]
    items = json.loads(row["items"])
    items.append({"name": extra["name"], "price": extra["price"], "type": "extra"})
    new_total = sum(i.get("price", 0) for i in items)

    db.execute(
        "UPDATE orders SET items = ?, total_price = ? WHERE id = ?",
        (json.dumps(items), new_total, row["id"]),
    )
    db.commit()
    app.logger.info("Extra '%s' added to order #%s by customer", extra["name"], row["id"])
    return jsonify({"ok": True, "new_total": new_total})


@app.route("/api/track/<token>/remove-item", methods=["POST"])
def remove_item(token):
    """Customer removes an item from their order."""
    data = request.get_json()
    item_index = data.get("index", -1) if data else -1

    db = get_db()
    row = db.execute(
        """SELECT * FROM orders WHERE token = ?
           AND status IN ('new', 'change')
           ORDER BY created_at DESC LIMIT 1""",
        (token,),
    ).fetchone()
    if not row:
        return jsonify({"error": "Order cannot be modified"}), 403

    items = json.loads(row["items"])
    if item_index < 0 or item_index >= len(items):
        return jsonify({"error": "Invalid index"}), 400

    # Don't allow removing the last pizza
    pizzas = [i for i in items if i.get("type") != "extra"]
    if items[item_index].get("type") != "extra" and len(pizzas) <= 1:
        return jsonify({"error": "Minst en pizza krävs"}), 400

    items.pop(item_index)
    new_total = sum(i.get("price", 0) for i in items)

    db.execute(
        "UPDATE orders SET items = ?, total_price = ? WHERE id = ?",
        (json.dumps(items), new_total, row["id"]),
    )
    db.commit()
    return jsonify({"ok": True, "new_total": new_total})


@app.route("/api/extras")
def list_extras():
    from menu import EXTRAS
    return jsonify(EXTRAS)


@app.route("/api/unavailable", methods=["GET"])
def list_unavailable():
    """List unavailable pizzas."""
    db = get_db()
    try:
        rows = db.execute("SELECT pizza_nr, reason FROM unavailable").fetchall()
        return jsonify([{"pizza_nr": r["pizza_nr"], "reason": r["reason"]} for r in rows])
    except sqlite3.OperationalError:
        return jsonify([])


@app.route("/api/unavailable/<int:pizza_nr>", methods=["POST"])
def set_unavailable(pizza_nr):
    """Mark a pizza as unavailable."""
    data = request.get_json()
    reason = data.get("reason", "Slut") if data else "Slut"
    db = get_db()
    db.execute("CREATE TABLE IF NOT EXISTS unavailable (pizza_nr INTEGER PRIMARY KEY, reason TEXT)")
    db.execute("INSERT OR REPLACE INTO unavailable (pizza_nr, reason) VALUES (?, ?)", (pizza_nr, reason))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/unavailable/<int:pizza_nr>", methods=["DELETE"])
def set_available(pizza_nr):
    """Mark a pizza as available again."""
    db = get_db()
    try:
        db.execute("DELETE FROM unavailable WHERE pizza_nr = ?", (pizza_nr,))
        db.commit()
    except sqlite3.OperationalError:
        pass
    return jsonify({"ok": True})


# --- Ingredient-based unavailability ---

@app.route("/api/ingredients", methods=["GET"])
def list_ingredients():
    """List all unique ingredients with pizza count and availability."""
    from menu import MENU

    # Collect all unique ingredients from pizza descriptions
    ingredient_counts = {}
    for p in MENU:
        for part in p["desc"].split(", "):
            part = part.strip()
            if not part or part.startswith("Inbakad"):
                continue  # Skip "Inbakad" prefix
            # Normalize: capitalize first letter to avoid duplicates
            part = part[0].upper() + part[1:]
            ingredient_counts[part] = ingredient_counts.get(part, 0) + 1

    # Get unavailable ingredients from DB
    db = get_db()
    try:
        rows = db.execute("SELECT ingredient FROM unavailable_ingredients").fetchall()
        unavailable_set = {r["ingredient"] for r in rows}
    except sqlite3.OperationalError:
        unavailable_set = set()

    result = []
    for name, count in sorted(ingredient_counts.items()):
        result.append({
            "name": name,
            "pizza_count": count,
            "available": name not in unavailable_set,
        })

    return jsonify(result)


@app.route("/api/ingredients/unavailable", methods=["POST"])
def set_ingredient_unavailable():
    """Mark an ingredient as unavailable — cascades to all pizzas with it."""
    from menu import MENU

    data = request.get_json()
    ingredient = data.get("ingredient", "") if data else ""
    if not ingredient:
        return jsonify({"error": "Missing ingredient"}), 400

    db = get_db()
    db.execute("CREATE TABLE IF NOT EXISTS unavailable_ingredients (ingredient TEXT PRIMARY KEY)")
    db.execute("INSERT OR IGNORE INTO unavailable_ingredients (ingredient) VALUES (?)", (ingredient,))

    # Cascade: mark all pizzas containing this ingredient as unavailable
    db.execute("CREATE TABLE IF NOT EXISTS unavailable (pizza_nr INTEGER PRIMARY KEY, reason TEXT)")
    for p in MENU:
        ingredients = [part.strip()[0].upper() + part.strip()[1:] for part in p["desc"].split(", ") if part.strip()]
        if ingredient in ingredients:
            db.execute(
                "INSERT OR REPLACE INTO unavailable (pizza_nr, reason) VALUES (?, ?)",
                (p["nr"], f"Slut på {ingredient}"),
            )

    db.commit()
    app.logger.info("Ingredient '%s' marked unavailable", ingredient)
    return jsonify({"ok": True})


@app.route("/api/ingredients/unavailable", methods=["DELETE"])
def set_ingredient_available():
    """Mark an ingredient as available again — removes cascade."""
    from menu import MENU

    data = request.get_json()
    ingredient = data.get("ingredient", "") if data else ""
    if not ingredient:
        return jsonify({"error": "Missing ingredient"}), 400

    db = get_db()
    try:
        db.execute("DELETE FROM unavailable_ingredients WHERE ingredient = ?", (ingredient,))
    except sqlite3.OperationalError:
        pass

    # Get remaining unavailable ingredients
    try:
        rows = db.execute("SELECT ingredient FROM unavailable_ingredients").fetchall()
        still_unavailable = {r["ingredient"] for r in rows}
    except sqlite3.OperationalError:
        still_unavailable = set()

    # Remove unavailability for pizzas that no longer have any unavailable ingredient
    for p in MENU:
        ingredients = [part.strip()[0].upper() + part.strip()[1:] for part in p["desc"].split(", ") if part.strip()]
        has_other_unavailable = any(ing in still_unavailable for ing in ingredients)
        if not has_other_unavailable:
            try:
                db.execute("DELETE FROM unavailable WHERE pizza_nr = ?", (p["nr"],))
            except sqlite3.OperationalError:
                pass

    db.commit()
    app.logger.info("Ingredient '%s' marked available", ingredient)
    return jsonify({"ok": True})


# --- Order management API ---

@app.route("/api/orders", methods=["GET"])
def list_orders():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM orders WHERE status NOT IN ('done', 'cancelled', 'picked') ORDER BY created_at DESC"
    ).fetchall()
    return jsonify([order_to_dict(row) for row in rows])


@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    phone = data.get("customer_phone", "")
    token = phone_to_token(phone) if phone else ""

    db = get_db()
    cursor = db.execute(
        """INSERT INTO orders (customer_name, customer_phone, items, total_price, call_id, token)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            data.get("customer_name", "Okänd"),
            phone,
            json.dumps(data.get("items", [])),
            data.get("total_price", 0),
            data.get("call_id", ""),
            token,
        ),
    )
    db.commit()
    order_id = cursor.lastrowid
    app.logger.info("Order #%s created: %s", order_id, data.get("items"))

    # Send tracking SMS
    if phone and token:
        tracking_url = f"{BASE_URL}/t/{token}"
        items = data.get("items", [])
        item_names = ", ".join(i.get("name", "?") for i in items)
        send_sms(
            phone,
            f"Tack för din beställning! {item_names}. "
            f"Följ din order här: {tracking_url} /Pizzeria Elken",
        )

    return jsonify({"id": order_id, "status": "new", "token": token}), 201


@app.route("/api/orders/<int:order_id>/oven", methods=["POST"])
def order_in_oven(order_id):
    db = get_db()
    row = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not row:
        return jsonify({"error": "Order not found"}), 404

    db.execute("UPDATE orders SET status = 'oven' WHERE id = ?", (order_id,))
    db.commit()

    if row["customer_phone"]:
        send_sms(
            row["customer_phone"],
            f"Hej {row['customer_name']}! Din pizza tillagas nu. "
            f"Beräknad tid: ca 15 min. /Pizzeria Elken",
        )

    return jsonify({"status": "oven"})


@app.route("/api/orders/<int:order_id>/ready", methods=["POST"])
def order_ready(order_id):
    db = get_db()
    row = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not row:
        return jsonify({"error": "Order not found"}), 404

    db.execute("UPDATE orders SET status = 'ready' WHERE id = ?", (order_id,))
    db.commit()

    if row["customer_phone"]:
        send_sms(
            row["customer_phone"],
            f"Hej {row['customer_name']}! Din beställning är klar för avhämtning! "
            f"Välkommen in. /Pizzeria Elken",
        )

    return jsonify({"status": "ready"})


@app.route("/api/orders/<int:order_id>/picked", methods=["POST"])
def order_picked(order_id):
    db = get_db()
    row = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not row:
        return jsonify({"error": "Order not found"}), 404

    db.execute("UPDATE orders SET status = 'picked' WHERE id = ?", (order_id,))
    db.commit()

    schedule_feedback_sms(order_id)

    return jsonify({"status": "picked"})


@app.route("/api/orders/<int:order_id>/cancel", methods=["POST"])
def order_cancel(order_id):
    db = get_db()
    row = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not row:
        return jsonify({"error": "Order not found"}), 404

    db.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
    db.commit()

    if row["customer_phone"]:
        send_sms(
            row["customer_phone"],
            f"Hej {row['customer_name']}! Tyvärr kan vi inte ta emot din beställning just nu. "
            f"Vi beklagar! Ring oss gärna om du har frågor. /Pizzeria Elken",
        )

    return jsonify({"status": "cancelled"})


@app.route("/api/orders/by-phone", methods=["GET"])
def orders_by_phone():
    phone = request.args.get("phone", "")
    status = request.args.get("status", "")
    if not phone:
        return jsonify([])
    db = get_db()
    if status:
        rows = db.execute(
            "SELECT * FROM orders WHERE customer_phone = ? AND status = ? ORDER BY created_at DESC",
            (phone, status),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM orders WHERE customer_phone = ? ORDER BY created_at DESC",
            (phone,),
        ).fetchall()
    return jsonify([order_to_dict(row) for row in rows])


@app.route("/api/orders/<int:order_id>/update", methods=["POST"])
def update_order(order_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    db = get_db()
    row = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not row:
        return jsonify({"error": "Order not found"}), 404

    db.execute(
        "UPDATE orders SET items = ?, total_price = ?, status = 'new' WHERE id = ?",
        (json.dumps(data.get("items", [])), data.get("total_price", 0), order_id),
    )
    db.commit()
    app.logger.info("Order #%s updated: %s", order_id, data.get("items"))
    return jsonify({"id": order_id, "status": "new"})


@app.route("/api/orders/<int:order_id>/change", methods=["POST"])
def order_change(order_id):
    db = get_db()
    row = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not row:
        return jsonify({"error": "Order not found"}), 404

    db.execute("UPDATE orders SET status = 'change' WHERE id = ?", (order_id,))
    db.commit()

    if row["customer_phone"]:
        send_sms(
            row["customer_phone"],
            f"Hej {row['customer_name']}! Vi behöver ändra något i din beställning. "
            f"Ring oss på 076-686 74 85 så löser vi det! /Pizzeria Elken",
        )

    return jsonify({"status": "change"})


if __name__ == "__main__":
    init_db()
    expire_old_orders()  # Clean up any stale orders from before restart
    start_expire_timer()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8096
    app.run(host="127.0.0.1", port=port, debug=False)
