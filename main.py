import logging

from core.app import TretaApp
from core.logging_config import configure_logging


logger = logging.getLogger("treta.main")


def main():
    configure_logging()
    logger.info("Treta Core starting")
    app = TretaApp()
    logger.info("Restored state", extra={"state": app.state_machine.state})
    logger.info("Starting HTTP server")

    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Treta Core stopped by user")


if __name__ == "__main__":
    main()
