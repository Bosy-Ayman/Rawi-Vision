"""
Test script to verify SmolVLM functionality and alert publishing
"""
import sys
import os
import json
import numpy as np
from PIL import Image
import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_smolvlm():
    """Test VLM loading and inference"""
    print("\n" + "="*60)
    print("TESTING SmolVLM MODEL")
    print("="*60)

    try:
        from utils.model_cache import get_smolvlm
        print("✓ Successfully imported get_smolvlm")

        print("\nLoading SmolVLM from cache...")
        processor, model = get_smolvlm()
        print("✓ SmolVLM loaded successfully!")

        # Create a dummy image for testing (red frame - potential anomaly)
        print("\nCreating test image...")
        dummy_image = np.ones((224, 224, 3), dtype=np.uint8) * [100, 50, 50]  # Reddish
        pil_img = Image.fromarray(dummy_image)

        # Test VLM inference
        print("\nRunning VLM inference on test image...")
        prompt = "First, describe any human activity in this surveillance frame in detail (ignore watermarks). Second, classify the activity by appending exactly one of these tags at the end: [normal], [violence], [theft], [trespassing], [vandalism], or [unusual_behavior]. If no crime is occurring, use [normal]."
        messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]

        text_input = processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = processor(images=[pil_img], text=text_input, return_tensors="pt")

        print("Processor inputs created successfully")

        import torch
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=35)

        print("✓ Model inference completed!")

        result = processor.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        print(f"\n📝 VLM Response:\n{result}")

        # Check if classification tag is present
        if any(tag in result for tag in ["[normal]", "[violence]", "[theft]", "[trespassing]", "[vandalism]", "[unusual_behavior]"]):
            print("\n✓ VLM correctly classified the scene with a tag!")
        else:
            print("\n⚠ VLM did not include a classification tag")

        return True

    except Exception as e:
        print(f"\n✗ VLM Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_kafka_alert():
    """Test Kafka alert publishing"""
    print("\n" + "="*60)
    print("TESTING KAFKA ALERT PUBLISHING")
    print("="*60)

    try:
        from confluent_kafka import Producer
        import json
        import base64
        import numpy as np
        import cv2

        print("Testing Kafka producer connection to localhost:29092...")
        producer = Producer({"bootstrap.servers": "localhost:29092"})

        # Create test event
        test_frame = np.ones((480, 640, 3), dtype=np.uint8) * [100, 50, 50]
        _, buffer = cv2.imencode(".jpg", test_frame)
        image_b64 = base64.b64encode(buffer).decode("utf-8")

        event = {
            "anomaly_type": "unusual_behavior",
            "description": "Test VLM description - unusual activity detected",
            "confidence_score": 0.87,
            "camera_id": "test_camera_001",
            "image_b64": image_b64,
            "timestamp": str(__import__('datetime').datetime.now())
        }

        print(f"\nPublishing test alert to Kafka topic 'anomaly-incidents'...")
        producer.produce("anomaly-incidents", key="anomaly", value=json.dumps(event).encode("utf-8"))
        producer.poll(0)
        print("✓ Alert published to Kafka!")

        print("\n📊 Alert Event:")
        print(json.dumps({k: v if k != "image_b64" else f"<base64_image:{len(v)}_bytes>" for k, v in event.items()}, indent=2))

        print("\n💡 Check if alert appears in dashboard at:")
        print("   http://localhost:3000/dashboard/anomalies")

        return True

    except Exception as e:
        print(f"\n✗ Kafka Test Failed: {e}")
        print("   Make sure Kafka is running on localhost:29092")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*60)
    print("ANOMALY DETECTION SYSTEM TEST".center(60))
    print("="*60)

    vlm_ok = test_smolvlm()
    kafka_ok = test_kafka_alert()

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"VLM Test:             {'✓ PASSED' if vlm_ok else '✗ FAILED'}")
    print(f"Kafka Alert Test:     {'✓ PASSED' if kafka_ok else '✗ FAILED'}")
    print("="*60)

    if vlm_ok and kafka_ok:
        print("\n✓ All systems ready! You can run the anomaly detection task.")
    else:
        print("\n⚠ Some tests failed. See errors above.")


if __name__ == "__main__":
    main()
