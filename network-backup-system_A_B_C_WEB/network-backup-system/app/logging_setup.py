"""Log metadata tác vụ; không log SSH payload hoặc mật khẩu."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]


def setup_logging():
    folder = PROJECT_DIR / 'logs'
    folder.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('app')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(folder / 'operations.log',
                                      maxBytes=2_000_000, backupCount=3, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
        logger.addHandler(handler)
    # Runner uses app.runner logger; parent named app catches it.
    return logger
