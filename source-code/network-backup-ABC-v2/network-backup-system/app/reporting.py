"""Phần C: xuất báo cáo metadata, không tiết lộ cấu hình/credentials."""
import csv
import json
import io
from dataclasses import asdict, is_dataclass
from pathlib import Path
from app.runner import safe_data
from app.security import write_private

PROJECT_DIR = Path(__file__).resolve().parents[1]


class ReportService:
    """Xuất kết quả tác vụ đã lọc dữ liệu nhạy cảm sang JSON hoặc CSV."""

    def export(self, results, output_path, format='json'):
        """Ghi metadata đã lọc vào reports, kiểm tra đường dẫn và định dạng."""
        if format not in {'json', 'csv'}:
            raise ValueError('Format phai la json hoac csv.')
        path = Path(output_path).resolve()
        # Không cho ghi tùy ý ra ngoài reports của dự án.
        if not path.is_relative_to((PROJECT_DIR / 'reports').resolve()):
            raise ValueError('Chi duoc xuat vao thu muc reports/.')
        if path.suffix.lower() != '.' + format:
            raise ValueError('Phan mo rong khong khop dinh dang.')
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [safe_data(asdict(x) if is_dataclass(x) else x)
                for x in results]
        if format == 'json':
            write_private(path, json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            columns = ['device', 'task', 'status', 'started_at',
                       'duration_seconds', 'data', 'error']
            with io.StringIO(newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader()
                for row in rows:
                    writer.writerow({key: json.dumps(row.get(key), ensure_ascii=False)
                                     if key in {'data', 'error'} else row.get(key)
                                     for key in columns})
                write_private(path, '\ufeff' + stream.getvalue())
        return str(path)
