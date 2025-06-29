# producer.py
import json
import time
import random
import psycopg2
from kafka import KafkaProducer

# 1. Point to our local broker
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# 2. Postgres connection (writes to transactions_raw)
db_conn = psycopg2.connect(
    dbname="fraud_db",
    user="postgres",
    password="password",
    host="localhost",
    port=5432
)
db_conn.autocommit = True
db_cur = db_conn.cursor()


def generate_transaction():
    """Simulate a fake transaction record."""
    return {
        'transaction_id': random.randint(100000, 999999),
        'user_id': random.choice([101, 102, 103, 104]),
        'amount': round(random.uniform(10.0, 5000.0), 2),
        'timestamp': int(time.time()),
        'country': random.choice(['US', 'NG', 'GB', 'IN', 'DE'])
    }


if __name__ == '__main__':
    print("Starting to send transactions to Kafka…")
    try:
        while True:
            txn = generate_transaction()

            # a) send to Kafka
            producer.send('transactions', txn)
            producer.flush()

            # b) also write raw to Postgres
            db_cur.execute(
                """
                INSERT INTO transactions_raw
                  (id, user_id, amount, timestamp, country)
                VALUES (%s, %s, %s, to_timestamp(%s), %s)
                """,
                (
                    txn['transaction_id'],
                    txn['user_id'],
                    txn['amount'],
                    txn['timestamp'],
                    txn['country']
                )
            )

            print(f"Sent & stored: {txn}")
            time.sleep(1)  # one message per second

    except KeyboardInterrupt:
        print("Producer stopped.")

    finally:
        db_cur.close()
        db_conn.close()
        producer.close()
