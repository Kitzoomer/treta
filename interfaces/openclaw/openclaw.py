import time
import requests
import json
import os

INTERVAL = int(os.getenv("OPENCLAW_INTERVAL", "5"))

print("🟢 OpenClaw starting (loop mode)")
print(f"🟢 Interval: {INTERVAL} seconds")

event = {
    "type": "WakeWordDetected",
    "payload": {},
    "source": "openclaw-loop"
}

while True:
    try:
        print("🟢 OpenClaw: sending WakeWordDetected")
        r = requests.post(
            "http://treta-core:7777/event",
            headers={"Content-Type": "application/json"},
            data=json.dumps(event),
            timeout=5
        )
        print(f"🟢 OpenClaw: sent ({r.status_code})")
    except Exception as e:
        print(f"🔴 OpenClaw error: {e}")

    time.sleep(INTERVAL)
