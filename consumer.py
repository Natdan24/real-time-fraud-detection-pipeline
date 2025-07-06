# consumer.py
import time
import requests
import psycopg2
from confluent_kafka.avro import AvroConsumer, CachedSchemaRegistryClient
from confluent_kafka import KafkaException

# ─── 0. Schema Registry + Kafka config ────────────────────────────────────────
schema_registry_conf = {
    "schema.registry.url": "http://schema-registry:8081"
}

consumer_conf = {
    "bootstrap.servers": "kafka:9092",
    "group.id": "fraud-consumer-avro",
    "auto.offset.reset": "earliest",
    **schema_registry_conf
}

# ─── 1. Build AvroConsumer ────────────────────────────────────────────────────
consumer = AvroConsumer(consumer_conf)
consumer.subscribe(["transactions"])

# ─── 2. Postgres helper ──────────────────────────────────────────────────────
def get_pg_conn():
    conn = psycopg2.connect(
        dbname="fraud_db",
        user="postgres",
        password="password",
        host="postgres",
        port=5432
    )
    conn.autocommit = False
    return conn

# ─── 3. Main loop ─────────────────────────────────────────────────────────────
print("💡 Avro consumer running—press Ctrl+C to stop.")

try:
    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            time.sleep(0.1)
            continue

        if msg.error():
            raise KafkaException(msg.error())

        # ✅ msg.value() is already a dict thanks to AvroConsumer
        txn = msg.value()
        user = txn["user_id"]
        amt  = txn["amount"]
        ts   = txn["timestamp"]
        country = txn["country"]

        # Process this transaction
        conn = get_pg_conn()
        cur = conn.cursor()
        try:
            # a) Insert raw if not already in (you can add ON CONFLICT if desired)
            cur.execute(
                """
                INSERT INTO transactions_raw
                  (user_id, amount, timestamp, country)
                VALUES (%s, %s, to_timestamp(%s), %s)
                """,
                (user, amt, ts, country)
            )

            # b) Recompute summary
            cur.execute(
                "SELECT COUNT(*), SUM(amount) FROM transactions_raw WHERE user_id = %s",
                (user,)
            )
            count, total_amount = cur.fetchone()
            avg_amount = total_amount / count

            # c) Call your FastAPI /predict
            resp = requests.get(
                "http://api:8000/predict",  # note: inside container, service is "api"
                params={"user_id": user},
                timeout=5
            )
            resp.raise_for_status()
            result = resp.json()
            anomaly_score = result["anomaly_score"]
            is_fraud      = result["is_fraud"]

            # d) Upsert into fraud_summary
            cur.execute(
                """
                INSERT INTO fraud_summary
                  (user_id, transaction_count, total_amount, avg_amount, anomaly_score, is_fraud)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                  transaction_count = EXCLUDED.transaction_count,
                  total_amount       = EXCLUDED.total_amount,
                  avg_amount         = EXCLUDED.avg_amount,
                  anomaly_score      = EXCLUDED.anomaly_score,
                  is_fraud           = EXCLUDED.is_fraud,
                  last_scored        = NOW();
                """,
                (
                    user,
                    count,
                    float(total_amount),
                    float(avg_amount),
                    float(anomaly_score),
                    is_fraud
                )
            )

            conn.commit()
            print(f"Processed user={user} cnt={count} avg={avg_amount:.2f} fraud={is_fraud}")

        except Exception as e:
            conn.rollback()
            print("Error processing txn:", txn, e)
        finally:
            cur.close()
            conn.close()

except KeyboardInterrupt:
    print("🛑 Avro consumer stopped by user.")
finally:
    consumer.close()
