# serve_model.py
from openai.error import RateLimitError
from dotenv import load_dotenv
load_dotenv()   # reads .env into os.environ
import os, openai
openai.api_key = os.getenv("OPENAI_API_KEY")

import os
import openai
from joblib import load
import redis
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# ─── 1. LOAD YOUR TRAINED MODEL ───────────────────────────────────────────────
# Look for an env var MODEL_PATH, otherwise fall back to the local file
MODEL_PATH = os.getenv("MODEL_PATH", "fraud_isolation_forest.joblib")
model = load(MODEL_PATH)

# ─── 2. CONNECT TO REDIS FEATURE STORE ────────────────────────────────────────
# We assume Redis is reachable on localhost:6379
r = redis.Redis(host="localhost", port=6379, db=0)

# ─── 3. CONFIGURE OPENAI ──────────────────────────────────────────────────────
# Make sure you have set OPENAI_API_KEY in your environment
openai.api_key = os.getenv("OPENAI_API_KEY")

# ─── 4. DEFINE REQUEST/RESPONSE SCHEMAS ───────────────────────────────────────
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

    data = r.hgetall(key)
    count = int(data[b"count"])
    avg_amount = float(data[b"avg_amount"])

    score = float(model.decision_function([[count, avg_amount]])[0])
    is_fraud = score < 0.0

    return PredictionResponse(
        user_id=user_id,
        anomaly_score=score,
        is_fraud=is_fraud
    )

# ─── 6. EXPLAIN ENDPOINT ──────────────────────────────────────────────────────
@app.get("/explain", response_model=ExplainResponse)
async def explain(user_id: int = Query(...)):
    key = f"user:{user_id}"
    if not r.exists(key):
        raise HTTPException(404, detail=f"No features for user {user_id}")

    data = r.hgetall(key)
    count = int(data[b"count"])
    avg_amount = float(data[b"avg_amount"])
    score = float(model.decision_function([[count, avg_amount]])[0])
    is_fraud = score < 0.0

    prompt = (
        f"User {user_id} was flagged with anomaly score {score:.3f} "
        f"(fraud={is_fraud}). They have made {count} transactions "
        f"with an average amount of ${avg_amount:.2f}. "
        "Explain in plain English why this pattern might indicate fraud."
    )

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a fintech fraud expert."},
                {"role": "user",   "content": prompt}
            ],
            max_tokens=150
        )
        explanation = resp.choices[0].message.content.strip()
    except RateLimitError:
        # Fallback stub if quota is exhausted
        explanation = (
         f"(Quota hit) User {user_id} has {count} txns, avg "
         f"${avg_amount:.2f}, score {score:.3f}. This looks suspicious"
          "because their activity deviates significantly from normal behavior."
           )


    return ExplainResponse(
        user_id=user_id,
        anomaly_score=score,
        is_fraud=is_fraud,
        explanation=explanation
    )
