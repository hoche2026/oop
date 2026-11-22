"""So sánh cấu hình, bỏ đúng header sinh tự động, giữ nguyên bản gốc."""
import re


VOLATILE = (
    r'^Building configuration\.\.\.$',
    r'^Current configuration\s*:\s*\d+ bytes$',
    r'^! Last configuration change at .+$',
    r'^! NVRAM config last updated at .+$',
    r'^! No configuration change since last restart$',
    r'^!Time: .+$',
    r'^# (?:\d{4}-\d{2}-\d{2}|[a-z]{3}/\d{2}/\d{4}) .+ by RouterOS .+$',
)


def comparison_lines(text):
    """Bỏ header và dấu phân cách IOS, bảo toàn lệnh, comment, nội dung banner."""
    lines = text.splitlines()
    cisco = (any(re.fullmatch(r'version\s+\S+', line) for line in lines)
             and any(re.fullmatch(r'hostname\s+\S+', line) for line in lines)
             and any(line == 'end' for line in lines))
    result = []
    banner_end = None
    for line in lines:
        if banner_end is not None:
            result.append(line)
            if banner_end in line:
                banner_end = None
            continue
        banner = re.match(r'^banner\s+\S+\s+(\^.|.)', line) if cisco else None
        if banner:
            result.append(line)
            delimiter = banner.group(1)
            if delimiter not in line[banner.end():]:
                banner_end = delimiter
            continue
        if any(re.fullmatch(pattern, line) for pattern in VOLATILE):
            continue
        if cisco and line.strip() == '!':
            continue
        result.append(line)
    # Header bị loại có thể để lại dòng rỗng ở hai đầu.
    while result and not result[0].strip():
        result.pop(0)
    while result and not result[-1].strip():
        result.pop()
    return [line + '\n' for line in result]
