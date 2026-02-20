#!/usr/bin/env python3
"""Pizza order dashboard and API.

Serves the dashboard, accepts orders from the voice agent,
manages order lifecycle, and sends SMS notifications via 46elks.

Usage:
    python web_app.py [port]
"""

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
    conn.commit()
    conn.close()


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
                f"Hej {row['customer_name']}! Tack för besöket på Pizzeria Bella. "
                f"Hur var maten? Svara 1-5 stjärnor!",
            )
            conn.execute("UPDATE orders SET status = 'done' WHERE id = ?", (order_id,))
            conn.commit()
        conn.close()

    timer = threading.Timer(3600, _send)
    timer.daemon = True
    timer.start()
    app.logger.info("Feedback SMS scheduled for order #%s in 1 hour", order_id)


# --- Routes ---

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/orders", methods=["GET"])
def list_orders():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM orders WHERE status NOT IN ('done', 'cancelled', 'picked') ORDER BY created_at DESC"
    ).fetchall()
    orders = []
    for row in rows:
        orders.append({
            "id": row["id"],
            "customer_name": row["customer_name"],
            "customer_phone": row["customer_phone"],
            "items": json.loads(row["items"]),
            "total_price": row["total_price"],
            "status": row["status"],
            "created_at": row["created_at"],
            "call_id": row["call_id"],
        })
    return jsonify(orders)


@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    db = get_db()
    cursor = db.execute(
        """INSERT INTO orders (customer_name, customer_phone, items, total_price, call_id)
           VALUES (?, ?, ?, ?, ?)""",
        (
            data.get("customer_name", "Okänd"),
            data.get("customer_phone", ""),
            json.dumps(data.get("items", [])),
            data.get("total_price", 0),
            data.get("call_id", ""),
        ),
    )
    db.commit()
    order_id = cursor.lastrowid
    app.logger.info("Order #%s created: %s", order_id, data.get("items"))
    return jsonify({"id": order_id, "status": "new"}), 201


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
            f"Hej {row['customer_name']}! Din beställning tillagas nu. "
            f"Beräknad tid: ca 15 min. /Pizzeria Bella",
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
            f"Välkommen in. /Pizzeria Bella",
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
            f"Vi beklagar! Ring oss gärna om du har frågor. /Pizzeria Bella",
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
    orders = []
    for row in rows:
        orders.append({
            "id": row["id"],
            "customer_name": row["customer_name"],
            "customer_phone": row["customer_phone"],
            "items": json.loads(row["items"]),
            "total_price": row["total_price"],
            "status": row["status"],
            "created_at": row["created_at"],
        })
    return jsonify(orders)


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
            f"Ring oss på 076-686 74 85 så löser vi det! /Pizzeria Bella",
        )

    return jsonify({"status": "change"})


if __name__ == "__main__":
    init_db()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8096
    app.run(host="127.0.0.1", port=port, debug=False)
