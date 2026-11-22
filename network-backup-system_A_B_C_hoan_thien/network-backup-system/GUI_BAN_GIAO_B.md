# Bàn giao phần B — Dương

Gói ngày 11/11/2026 gồm code A đã bàn giao và phần B đã bổ sung,
để có thể kiểm thử độc lập trước khi ghép C. Đây chưa phải sản phẩm đủ A/B/C.

## Phần B cần ghép

- app/storage.py: file cấu hình, restore point và metadata SQLite.
- app/backup.py: phiên bản, diff, baseline, sai lệch, restore và verify.
- app/scheduler.py, config/schedule.example.yaml: lịch interval, nhận runner C.
- tests/test_storage.py, tests/test_backup.py, tests/test_scheduler.py.
- docs/handover_B.md: API và hướng dẫn ghép; docs/review_B.md: kết quả rà soát.

Đọc docs/handover_B.md trước. Nếu bạn đang có code A/C mới hơn, ghép các file
B theo API đã thống nhất; giữ thay đổi A/C hiện có thay vì ghi đè cả dự án.
Các file A kèm theo là bản nền đã dùng để kiểm thử phần B.

## Cài và kiểm thử

Dùng Python 3.12. Tại thư mục đã giải nén chứa requirements.txt:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Trên Ubuntu dùng python3.12 để tạo .venv, rồi gọi .venv/bin/python.
Kết quả kiểm thử offline gần nhất: 70/70 bài đạt. Chưa kiểm thử runner
thật của C và lab thật cho luồng tích hợp B. Không dùng test giả thay minh chứng lab.

Gói không có .env thật, .venv, database, file backup hay log vận hành.
Để thử lab, tạo .env từ .env.example và điền thông tin trên máy đích.
Không tự chạy demo push/restore trước khi chuẩn bị và thống nhất kịch bản lab.
