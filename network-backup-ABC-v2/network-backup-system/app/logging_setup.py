"""Nhật ký metadata có người thực hiện, không ghi payload SSH/cấu hình."""
import getpass
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re

from app.security import private_dir, private_file

PROJECT_DIR = Path(__file__).resolve().parents[1]


class ActorFilter(logging.Filter):
    """Bổ sung tên tài khoản hệ điều hành đã làm sạch vào bản ghi log."""

    def filter(self, record):
        """Thêm actor an toàn vào bản ghi và cho phép handler xử lý tiếp."""
        record.actor = re.sub(r'[^A-Za-z0-9_.@-]', '_', getpass.getuser())
        return True


class PrivateRotatingHandler(RotatingFileHandler):
    """Giữ quyền riêng tư khi tạo và xoay file nhật ký trên POSIX."""

    def _open(self):
        import io
        return io.TextIOWrapper(private_file(self.baseFilename), encoding='utf-8')


def setup_logging():
    """Thiết lập log metadata có actor, quyền file riêng tư và giới hạn dung lượng."""
    folder = private_dir(PROJECT_DIR / 'logs')
    logger = logging.getLogger('app')
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = PrivateRotatingHandler(folder / 'operations.log',
                                         maxBytes=2_000_000, backupCount=3, encoding='utf-8')
        handler.addFilter(ActorFilter())
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s actor=%(actor)s %(name)s %(message)s'))
        logger.addHandler(handler)
    return logger
