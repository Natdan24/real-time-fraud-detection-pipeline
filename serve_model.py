# serve_model.py

import os
import requests
from joblib import load
import redis
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# ─── 1. LOAD YOUR TRAINED MODEL ───────────────────────────────────────────────
MODEL_PATH = os.getenv("MODEL_PATH", "fraud_isolation_forest.joblib")
model = load(MODEL_PATH)

# ─── 2. REDIS HELPER ───────────────────────────────────────────────────────────
def load_redis():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=0
    )

r = load_redis()

# ─── 3. LM STUDIO CONFIG ───────────────────────────────────────────────────────
LMSTUDIO_URL   = os.getenv("LMSTUDIO_URL",   "http://127.0.0.1:8080/v1/generate")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "mistral-7b")

# ─── 4. REQUEST/RESPONSE SCHEMAS ───────────────────────────────────────────────
class PredictionResponse(BaseModel):
    user_id: int
    anomaly_score: float
    is_fraud: bool

class ExplainResponse(PredictionResponse):
    explanation: str

app = FastAPI(title="Fraud Detection & Explainability API")

# ─── 5. PREDICT ENDPOINT ──────────────────────────────────────────────────────
@app.get("/predict", response_model=PredictionResponse)
def predict(user_id: int = Query(..., description="ID of the user to score")):
    key = f"user:{user_id}"
    if not r.exists(key):
        raise HTTPException(404, detail=f"No features for user {user_id}")

    data       = r.hgetall(key)
    count      = int(data[b"count"])
    avg_amount = float(data[b"avg_amount"])

    score    = float(model.decision_function([[count, avg_amount]])[0])
    is_fraud = score < 0.0

    return PredictionResponse(
        user_id=user_id,
        anomaly_score=score,
        is_fraud=is_fraud
    )

# ─── 6. EXPLAIN ENDPOINT ──────────────────────────────────────────────────────
@app.get("/explain", response_model=ExplainResponse)
def explain(user_id: int = Query(..., description="ID of the user to explain")):
    key = f"user:{user_id}"
    if not r.exists(key):
        raise HTTPException(404, detail=f"No features for user {user_id}")

    data       = r.hgetall(key)
    count      = int(data[b"count"])
    avg_amount = float(data[b"avg_amount"])
    score      = float(model.decision_function([[count, avg_amount]])[0])
    is_fraud   = score < 0.0

    prompt = (
        f"User {user_id} was flagged with anomaly score {score:.3f} "
        f"(fraud={is_fraud}). They made {count} transactions "
        f"averaging ${avg_amount:.2f}. Explain why this might indicate fraud."
    )

    try:
        resp = requests.post(
            LMSTUDIO_URL,
            json={
                "model": LMSTUDIO_MODEL,
                "prompt": prompt,
                "max_new_tokens": 100,
                "temperature": 0.7,
                "top_p": 0.9
            },
            timeout=10
        )
        resp.raise_for_status()
        explanation = resp.json()["results"][0]["text"].strip()
    except Exception:
        explanation = (
            f"User {user_id}, score {score:.3f}, made {count} txns averaging "
            f"${avg_amount:.2f}. This deviates significantly from normal behavior."
        )

    return ExplainResponse(
        user_id=user_id,
        anomaly_score=score,
        is_fraud=is_fraud,
        explanation=explanation
    )
