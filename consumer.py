import pyspark
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

# 5️⃣ Write the stream to the console
query = (
    parsed_df
    .writeStream
    .outputMode("append")
    .format("console")
    .option("truncate", False)
    .start()
)

print("💡 Spark consumer running—press Ctrl+C to stop.")
query.awaitTermination()
