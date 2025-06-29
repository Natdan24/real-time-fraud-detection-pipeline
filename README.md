# real-time-fraud-detection-pipeline
cp .env.example .env
docker-compose up -d redis
source .venv/bin/activate
python -m uvicorn serve_model:app --reload --port 8000
