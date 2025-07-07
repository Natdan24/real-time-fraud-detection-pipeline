# tests/test_consumer.py
import sqlite3
import pytest
from consumer import process_single_transaction  # we’ll refactor a helper

@pytest.fixture
def tmp_db(tmp_path):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    c = conn.cursor()
    # Create tables matching your Postgres schema
    c.execute("CREATE TABLE transactions_raw (id INTEGER PRIMARY KEY, user_id INT, amount REAL, timestamp REAL, country TEXT)")
    c.execute("""
        CREATE TABLE fraud_summary (
            user_id INT PRIMARY KEY,
            transaction_count INT,
            total_amount REAL,
            avg_amount REAL,
            anomaly_score REAL,
            is_fraud BOOL,
            last_scored DATETIME
        )
    """)
    conn.commit()
    yield conn
    conn.close()

def test_process_single_transaction(monkeypatch, tmp_db):
    # 1) Stub Kafka message
    txn = {"user_id": 42, "amount": 100.0, "timestamp": 1_700_000_000, "country": "US"}

    # 2) Stub requests to /predict
    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"anomaly_score": -1.0, "is_fraud": True}
    monkeypatch.setattr("consumer.requests.get", lambda *args, **kwargs: FakeResp())

    # 3) Run helper once
    from consumer import process_single_transaction
    process_single_transaction(txn, tmp_db)

    # 4) Assert raw & summary
    c = tmp_db.cursor()
    c.execute("SELECT COUNT(*), SUM(amount) FROM transactions_raw WHERE user_id=42")
    assert c.fetchone() == (1, 100.0)

    c.execute("SELECT user_id, is_fraud FROM fraud_summary WHERE user_id=42")
    assert c.fetchone() == (42, 1)
