
# Real-Time Fraud Detection Pipeline

An end-to-end, containerized microservice for ingesting, processing, detecting, and monitoring fraudulent transactions in real time. Built with Kafka, Redis, PostgreSQL, FastAPI, Prometheus, Grafana, and a Streamlit dashboard.

---

## 🚀 Features

- **Ingestion**: Simulate and publish JSON/Avro transactions to Kafka  
- **Stream Processing**: Python consumer (or PySpark) writes raw records to PostgreSQL, updates Redis feature store, and calls FastAPI for anomaly scoring  
- **Machine Learning**: Isolation Forest (with optional XGBoost & Autoencoder baselines)  
- **Serving & Explainability**: FastAPI `/predict` and `/explain` endpoints backed by Mistral 7B LLM  
- **Observability**: Prometheus metrics, Alertmanager rules, Grafana dashboards  
- **Visualization**: Interactive Streamlit app for country-level fraud, top-risk users, and trend analysis  
- **CI/CD & Automation**: GitHub Actions workflows for lint, tests, Docker builds, nightly backups, and ETL cleanup  

---

## 📋 Prerequisites

- Docker & Docker Compose  
- Python 3.12 (+ venv)  
- (Optional) LMStudio with Mistral-7B running at `host.docker.internal:1234`  

---

## 🔧 Local Quickstart

1. **Clone & configure**  
   ```bash
   git clone https://github.com/Natdan24/real-time-fraud-detection-pipeline.git
   cd real-time-fraud-detection-pipeline
   cp .env.example .env
   ```

2. **Launch core services**  
   ```bash
   docker-compose up -d
   ```

   > **Persistence Note:**  
   > Redis and Postgres are backed by named Docker volumes (`redis-data`, `postgres-data`) in your `docker-compose.yml`. This ensures feature-store and raw data persist across restarts.

3. **Activate Python environment**  
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Start the API**  
   ```bash
   uvicorn serve_model:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Run the producer & consumer** (in separate terminals)  
   ```bash
   python producer.py
   python consumer.py
   ```

6. **Explore the dashboards**  
   - **Streamlit**:  
     ```bash
     streamlit run app.py
     ```  
     http://localhost:8501  
   - **Grafana**: http://localhost:3000 (admin/admin)  
   - **Prometheus**: http://localhost:9090/targets  

---

## 📂 Repository Layout

```
.
├── producer.py                  
├── consumer.py                  
├── feature_store.py             
├── extract_features.py          
├── train_if.py / eval_if.py     
├── train_xgb.py / eval_xgb.py   
├── train_ae.py / eval_ae.py     
├── serve_model.py               
├── app.py                       
├── metrics.py                   
├── sql/schema.sql               
├── prometheus/                  
├── alertmanager/                
├── .github/workflows/           
├── docker-compose.yml           
├── requirements*.txt            
└── README.md                    
```

---

## 🔍 Usage & Endpoints

- **GET /predict?user_id=_ID_**  
  Returns `{ user_id, anomaly_score, is_fraud }`.

- **GET /explain?user_id=_ID_**  
  Returns LLM-generated rationale for that user’s fraud score.

- **GET /metrics**  
  Prometheus-formatted counters:
  ```
  fraud_summary_total_transactions_total
  fraud_summary_is_fraud_total
  http_requests_total{handler="/predict",status="2xx"}
  ```

---

## 📊 Visualization Dashboard

See full Streamlit dashboard screenshots and explanations in `docs/images/`.

---

## 🔄 Avro Transaction Ingestion

We produce and consume Avro-encoded transaction messages. See `producer.py` and `consumer.py`.

---

## 📈 Monitoring & Alerts

### Prometheus

- **Rules:** Defined in `prometheus/rules.yml`  
  - **HighPredictTraffic**  
  - **HighFraudRate**

### Grafana Dashboards

- **Panels:**  
  - Throughput  
  - Fraud Rate  
  - Inference Latency (95th percentile)

---

## ⚙️ CI/CD & Automation

- **GitHub Actions**  
  - `ci.yml`, `nightly-backup.yml`  
- **Utility Scripts**  
  - `etl_cleanup.sh`, `backup_fraud_summary.sh`  

---

## 🛠️ Troubleshooting

Includes tips for `/metrics` not loading, producer Kafka errors, and more (see full docs).

---

**Enjoy building and showcasing your real-time fraud detection pipeline!**
