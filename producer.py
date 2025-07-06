# producer.py
import time
import random
import psycopg2
import avro.schema
from confluent_kafka.avro import AvroProducer

# ─── 0. Parse your local Avro schema ───────────────────────────────────────────
schema_path = "/app/schemas/transactions.avsc"  # adjust if needed
with open(schema_path, "r") as f:
    schema_str = f.read()
value_schema = avro.schema.parse(schema_str)

# ─── 1. Point to Kafka broker with AvroProducer ───────────────────────────────
producer = AvroProducer(
    {
        "bootstrap.servers": "kafka:9092",
        "schema.registry.url": "http://schema-registry:8081"
    },
    default_value_schema=value_schema
)

# ─── 2. Postgres connection (writes to transactions_raw) ───────────────────────
db_conn = psycopg2.connect(
    dbname="fraud_db",
    user="postgres",
    password="password",
    host="postgres",    # Docker Compose service name
    port=5432
)
db_conn.autocommit = True
db_cur = db_conn.cursor()

def generate_transaction():
    """Simulate a fake transaction record."""
    return {
        "transaction_id": random.randint(100000, 999999),
        "user_id":       random.choice([101, 102, 103, 104]),
        "amount":        round(random.uniform(10.0, 5000.0), 2),
        "timestamp":     int(time.time()),
        "country":       random.choice(["US", "NG", "GB", "IN", "DE"])
    }

if __name__ == "__main__":
    print("🚀 Starting Avro producer…")
    try:
        while True:
            txn = generate_transaction()

            # a) Send to Kafka with Avro; on first run, the schema is auto-registered
            producer.produce(topic="transactions", value=txn)
            producer.flush()

            # b) Also write raw to Postgres
            db_cur.execute(
                """
                INSERT INTO transactions_raw
                  (id, user_id, amount, timestamp, country)
                VALUES (%s, %s, %s, to_timestamp(%s), %s)
                """,
                (
                    txn["transaction_id"],
                    txn["user_id"],
                    txn["amount"],
                    txn["timestamp"],
                    txn["country"]
                )
            )

            print(f"✅ Sent & stored: {txn}")
            time.sleep(1)

    except KeyboardInterrupt:
        print("🛑 Producer stopped by user.")

    finally:
        db_cur.close()
        db_conn.close()
