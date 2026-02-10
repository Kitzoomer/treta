import time
import requests

TRETA_EVENT_URL = "http://treta-core:7777/event"

def send_wake():
    print("🔊 OpenClaw: sending WakeWordDetected")
    requests.post(
        TRETA_EVENT_URL,
        json={
            "type": "WakeWordDetected",
            "payload": {},
            "source": "openclaw"
        },
        timeout=2
    )

if __name__ == "__main__":
    # 🔁 Solo dispara UNA vez y se detiene
    time.sleep(2)
    send_wake()
    print("✅ OpenClaw: done (no loop)")
