from flask import Flask, jsonify, abort
import os
import redis
import psycopg2
import json
from psycopg2.extras import RealDictCursor

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_TTL  = int(os.getenv("REDIS_TTL", 30))

PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_PORT = int(os.getenv("POSTGRES_PORT", 5432))
PG_DB   = os.getenv("POSTGRES_DB", "calculatordb")
PG_USER = os.getenv("POSTGRES_USER", "calcuser")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "calcpass")

app = Flask(__name__)

## Cliente do Redis
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def get_pg_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS
    )

def ensure_table():
    conn = get_pg_conn()
    cur = conn.cursor()
    with open("init_db.sql", "r") as f:
        cur.execute(f.read())
    conn.commit()
    cur.close()
    conn.close()

ensure_table()

def db_lookup(op, a, b):
    conn = get_pg_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT result, created_at FROM operations WHERE op=%s AND a=%s AND b=%s LIMIT 1", (op, a, b))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def db_insert(op, a, b, result):
    conn = get_pg_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO operations (op, a, b, result) VALUES (%s, %s, %s, %s) ON CONFLICT (op, a, b) DO UPDATE SET result = EXCLUDED.result RETURNING id",
        (op, a, b, result)
    )
    conn.commit()
    cur.close()
    conn.close()

def compute(op, a, b):
    if op == "add":
        return a + b
    if op == "sub" or op == "subtract":
        return a - b
    if op == "mul" or op == "multiply":
        return a * b
    if op == "div" or op == "divide":
        if b == 0:
            raise ZeroDivisionError("division by zero")
        return a / b
    raise ValueError("unsupported operation")

@app.route("/health")
def health():
    return jsonify({"status":"ok"})

@app.route("/calculator/<op>/<a>/<b>")
def calculator(op, a, b):
    ## Parsing
    try:
        a_v = float(a)
        b_v = float(b)
    except ValueError:
        return jsonify({"error":"invalid numbers"}), 400

    key = f"calc:{op}:{a_v}:{b_v}"

    ## Testa consulta primeiro no Redis
    cached = r.get(key)
    if cached:
        payload = json.loads(cached)
        return jsonify({"result": payload["result"], "source": "cache"})

    ## Testa consulta no Database
    row = db_lookup(op, a_v, b_v)
    if row:
        result = float(row["result"])
        #- Adiciona no Cache se for consultado do Database
        r.set(key, json.dumps({"result": result}), ex=REDIS_TTL)
        return jsonify({"result": result, "source": "added"})

    ## Calcula o resultado e envia para o cache e para o Database
    try:
        result = compute(op, a_v, b_v)
    except ZeroDivisionError as e:
        return jsonify({"error": str(e)}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    db_insert(op, a_v, b_v, result)
    r.set(key, json.dumps({"result": result}), ex=REDIS_TTL)
    return jsonify({"result": result, "source": "calculated"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

