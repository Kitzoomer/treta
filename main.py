from core.app import TretaApp


def main():
    print("🧠 Treta Core starting...")
    app = TretaApp()
    print(f"🧠 Restored state: {app.state_machine.state}")
    print("[BOOT] Starting HTTP server")

    try:
        app.run()
    except KeyboardInterrupt:
        print("🛑 Treta Core stopped by user")


if __name__ == "__main__":
    main()
