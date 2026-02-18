import select
import sys
import time

from core.bus import EventBus
from core.events import (
    EVENT_ERROR,
    EVENT_LLM_RESPONSE_READY,
    EVENT_TRANSCRIPT_READY,
    EVENT_TTS_FINISHED,
    EVENT_WAKE_WORD,
    Event,
)


def keyboard_loop(bus: EventBus | None = None):
    event_bus = bus or EventBus()
    print("⌨️  Modo teclado (DEBUG)")
    print("Comandos: wake | think | speak | idle | error | quit")

    while True:
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            cmd = sys.stdin.readline().strip().lower()

            if cmd == "wake":
                event_bus.push(Event(EVENT_WAKE_WORD, {}, "keyboard"))
            elif cmd == "think":
                event_bus.push(Event(EVENT_TRANSCRIPT_READY, {}, "keyboard"))
            elif cmd == "speak":
                event_bus.push(Event(EVENT_LLM_RESPONSE_READY, {}, "keyboard"))
            elif cmd == "idle":
                event_bus.push(Event(EVENT_TTS_FINISHED, {}, "keyboard"))
            elif cmd == "error":
                event_bus.push(Event(EVENT_ERROR, {}, "keyboard"))
            elif cmd == "quit":
                print("🛑 Saliendo del modo teclado")
                break
            elif cmd:
                print(f"❓ Comando desconocido: {cmd}")

        time.sleep(0.05)
