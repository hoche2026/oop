"""Quyền riêng tư file trên POSIX; Windows cần ACL tài khoản tương ứng."""
import os
from pathlib import Path


def private_dir(path):
    """Tạo thư mục dữ liệu, đặt quyền 700 trên POSIX."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == 'posix':
        path.chmod(0o700)
    return path


def private_file(path, exclusive=False):
    """Mở file nhị phân, quyền 600 ngay lúc tạo; không dùng umask toàn tiến trình."""
    path = Path(path)
    private_dir(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | (
        os.O_EXCL if exclusive else os.O_APPEND)
    fd = os.open(path, flags, 0o600)
    if os.name == 'posix':
        os.fchmod(fd, 0o600)
    return os.fdopen(fd, 'ab')


def write_private(path, text):
    """Ghi thay thế nguyên tử; không để nội dung mới hiện ra với quyền rộng."""
    from uuid import uuid4
    path = Path(path)
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        with private_file(temporary, exclusive=True) as stream:
            stream.write(text.encode('utf-8'))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
