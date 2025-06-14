import json
import time
import random
from kafka import KafkaProducer

# 1. Point to our local broker
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

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
            # 2. Send to the 'transactions' topic
            producer.send('transactions', txn)
            print(f"Sent: {txn}")
            producer.flush()        # force sending
            time.sleep(1)           # one message per second
    except KeyboardInterrupt:
        print("Producer stopped.")
    finally:
        producer.close()

"""
KafkaProducer(...)

bootstrap_servers: where your broker lives

value_serializer: turns Python dict → JSON bytes

generate_transaction()

Simulates random fields for a transaction

producer.send(...)

Sends each JSON-encoded record to the transactions topic

producer.flush()

Ensures messages are actually dispatched before sleeping

"""