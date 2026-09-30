import os
import socket
from contextlib import contextmanager

import psycopg2
from flask import Flask, jsonify, request

app = Flask(__name__)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432"),
    "dbname": os.environ.get("DB_NAME", "appdb"),
    "user": os.environ.get("DB_USER", "appuser"),
    "password": os.environ.get("DB_PASSWORD", "supersecret"),
}

schema_ready = False


@contextmanager
def db_cursor():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            yield cur
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_schema():
    global schema_ready
    if schema_ready:
        return
    with db_cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS visits (
                id SERIAL PRIMARY KEY,
                hostname TEXT NOT NULL,
                path TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
    schema_ready = True


@app.get("/")
def index():
    ensure_schema()
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO visits (hostname, path) VALUES (%s, %s)",
            (socket.gethostname(), "/"),
        )
    return jsonify(
        message="Hello from backend-k8s",
        served_by=socket.gethostname(),
        database=DB_CONFIG["host"],
    )


@app.get("/health")
def health():
    try:
        with db_cursor() as cur:
            cur.execute("SELECT 1")
        return jsonify(status="ok", database="up")
    except Exception as exc:
        return jsonify(status="degraded", database=str(exc)), 503


@app.get("/visits")
def list_visits():
    ensure_schema()
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, hostname, path, created_at FROM visits ORDER BY id DESC LIMIT 50"
        )
        rows = cur.fetchall()
    return jsonify(
        [
            {
                "id": row[0],
                "hostname": row[1],
                "path": row[2],
                "created_at": row[3].isoformat(),
            }
            for row in rows
        ]
    )


@app.post("/visits")
def add_visit():
    ensure_schema()
    body = request.get_json(silent=True) or {}
    path = str(body.get("path", "/manual"))
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO visits (hostname, path) VALUES (%s, %s)",
            (socket.gethostname(), path),
        )
    return jsonify(message="recorded", served_by=socket.gethostname()), 201


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
