"""Phần C: xuất báo cáo metadata, không tiết lộ cấu hình/credentials."""
import csv
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from app.runner import safe_data

PROJECT_DIR = Path(__file__).resolve().parents[1]


class ReportService:
    def export(self, results, output_path, format='json'):
        if format not in {'json', 'csv'}:
            raise ValueError('Format phai la json hoac csv.')
        path = Path(output_path).resolve()
        # Không cho ghi tùy ý ra ngoài reports của dự án.
        if not path.is_relative_to((PROJECT_DIR / 'reports').resolve()):
            raise ValueError('Chi duoc xuat vao thu muc reports/.')
        if path.suffix.lower() != '.' + format:
            raise ValueError('Phan mo rong khong khop dinh dang.')
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [safe_data(asdict(x) if is_dataclass(x) else x) for x in results]
        if format == 'json':
            path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        else:
            columns = ['device', 'task', 'status', 'started_at', 'duration_seconds', 'data', 'error']
            with path.open('w', newline='', encoding='utf-8-sig') as stream:
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader()
                for row in rows:
                    writer.writerow({key: json.dumps(row.get(key), ensure_ascii=False)
                                     if key in {'data', 'error'} else row.get(key)
                                     for key in columns})
        return str(path)
