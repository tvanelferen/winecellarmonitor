"""
Wine Cellar Monitor - Python Flask Server
Receives sensor readings from the ESP32 and serves the web dashboard.
"""

from flask import Flask, request, jsonify, render_template
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)

# Path to the SQLite database file
DB_PATH = "/data/readings.db"


# ─────────────────────────────────────────────
#  DATABASE SETUP
# ─────────────────────────────────────────────

def init_db():
    """Create the readings table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            temperature REAL    NOT NULL,
            humidity    REAL    NOT NULL,
            recorded_at TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def get_db():
    """Open a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    return conn


# ─────────────────────────────────────────────
#  API ROUTES
# ─────────────────────────────────────────────

@app.route("/api/reading", methods=["POST"])
def receive_reading():
    """
    Called by the ESP32 every minute.
    Expects JSON: { "temperature": 13.5, "humidity": 72.1 }
    """
    data = request.get_json()

    if not data or "temperature" not in data or "humidity" not in data:
        return jsonify({"error": "Missing temperature or humidity"}), 400

    temperature = float(data["temperature"])
    humidity    = float(data["humidity"])
    recorded_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    conn.execute(
        "INSERT INTO readings (temperature, humidity, recorded_at) VALUES (?, ?, ?)",
        (temperature, humidity, recorded_at)
    )
    conn.commit()
    conn.close()

    print(f"[{recorded_at}] Saved → Temp: {temperature}°C  Humidity: {humidity}%")
    return jsonify({"status": "ok"}), 201


@app.route("/api/latest", methods=["GET"])
def latest_reading():
    """Return the most recent reading."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM readings ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "No readings yet"}), 404

    return jsonify({
        "temperature": row["temperature"],
        "humidity":    row["humidity"],
        "recorded_at": row["recorded_at"]
    })


@app.route("/api/history", methods=["GET"])
def history():
    """
    Return the last 7 days of readings (max 10 080 points).
    The dashboard uses this to draw the charts.
    """
    conn = get_db()
    rows = conn.execute("""
        SELECT temperature, humidity, recorded_at
        FROM readings
        WHERE recorded_at >= datetime('now', '-7 days')
        ORDER BY id ASC
    """).fetchall()
    conn.close()

    return jsonify([
        {
            "temperature": r["temperature"],
            "humidity":    r["humidity"],
            "recorded_at": r["recorded_at"]
        }
        for r in rows
    ])


# ─────────────────────────────────────────────
#  DASHBOARD ROUTE
# ─────────────────────────────────────────────

@app.route("/")
def dashboard():
    """Serve the HTML dashboard."""
    return render_template("index.html")


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

# This runs on startup regardless of how the app is launched
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
