from confluent_kafka import Producer
import json   # ✅ FIX HERE

def main():
    print("Testing Kafka Anomaly Alert...")
    try:
        producer = Producer({
            "bootstrap.servers": "localhost:29092"
        })

        event = {
            "anomaly_type": "Violence",
            "description": "Test anomaly alert description",
            "confidence_score": 0.99,
            "camera_id": "test_cam_01",
        }

        producer.produce(
            "anomaly-incidents",
            key="anomaly",
            value=json.dumps(event).encode("utf-8")
        )

        producer.flush()
        print("Successfully sent test event to Kafka on localhost:29092")

    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    main()