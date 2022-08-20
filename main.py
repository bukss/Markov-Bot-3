from bot import Bot
import logging

logging.basicConfig(level=logging.INFO,
                    format="[%(levelname)s][%(asctime)s] %(message)s"
                    )
logger = logging.getLogger()
b = Bot("config.json", logger)
b.run()