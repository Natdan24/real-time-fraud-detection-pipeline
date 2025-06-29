# consumer.py
import requests
import psycopg2
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import (
    StructType, StructField, IntegerType,
    DoubleType, StringType, LongType
)

# 1️⃣ Define the JSON schema for our transactions
transaction_schema = StructType([
    StructField("transaction_id", IntegerType()),
    StructField("user_id",       IntegerType()),
    StructField("amount",        DoubleType()),
    StructField("timestamp",     LongType()),
    StructField("country",       StringType()),
])

# 2️⃣ Build a SparkSession with the Kafka connector
spark = (
    SparkSession.builder
    .appName("KafkaTransactionConsumer")
    .master("local[*]")
    .config(
        "spark.jars.packages",
        "org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.1"
    )
    .getOrCreate()
)

# 3️⃣ Read as a streaming DataFrame from Kafka
kafka_df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "localhost:9092")
    .option("subscribe", "transactions")
    .option("startingOffsets", "earliest")
    .load()
)

# 4️⃣ Parse the JSON payload into columns
parsed_df = (
    kafka_df
    .selectExpr("CAST(value AS STRING) AS json_str")
    .select(from_json(col("json_str"), transaction_schema).alias("data"))
    .select("data.*")
)

# 5️⃣ Define our per-batch processing function
def process_batch(df, epoch_id):
    # Open a Postgres connection for this batch
    conn = psycopg2.connect(
        dbname="fraud_db",
        user="postgres",
        password="password",
        host="localhost",
        port=5432
    )
    cur = conn.cursor()

    for row in df.collect():
        user = row.user_id
        amt  = row.amount

        # a) Insert raw if not already inserted by producer
        cur.execute(
            """
            INSERT INTO transactions_raw
              (user_id, amount, timestamp, country)
            VALUES (%s, %s, to_timestamp(%s), %s)
            """,
            (user, amt, row.timestamp, row.country)
        )

        # b) Recompute summary from raw table
        cur.execute(
            "SELECT COUNT(*), SUM(amount) FROM transactions_raw WHERE user_id = %s",
            (user,)
        )
        count, total_amount = cur.fetchone()
        avg_amount = total_amount / count

        # c) Call our API to get anomaly score & flag
        resp = requests.get(
            "http://localhost:8000/predict",
            params={"user_id": user},
            timeout=5
        )
        resp.raise_for_status()
        result = resp.json()
        anomaly_score = result["anomaly_score"]
        is_fraud      = result["is_fraud"]

        # d) Upsert into our fraud_summary table
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

    cur.close()
    conn.close()


# 6️⃣ Hook our function into Spark Structured Streaming
query = (
    parsed_df
    .writeStream
    .foreachBatch(process_batch)
    .outputMode("append")
    .start()
)

print("💡 Spark consumer running—press Ctrl+C to stop.")
query.awaitTermination()
