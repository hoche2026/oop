> Tài liệu gốc trước v2. Các thay đổi mới về verify/rollback/CLI được mô tả
> trong CAP_NHAT_V2.md; dùng hướng dẫn chạy CHAY_KIEM_THU_VA_CHUP_ANH.md.

# BỔ SUNG PHẦN C — NHỮNG GÌ ĐÃ THAY ĐỔI VÀ CÁCH CHẠY

## 1. Phạm vi thay đổi

**Giữ nguyên nội dung toàn bộ mã Python của A+B:**
- `app/contracts.py`, `app/inventory.py`, `app/normalization.py`
- `app/devices/*`, `app/backup.py`, `app/storage.py`, `app/scheduler.py`
- Các `demo_*.py`, `tests/test_backup.py`, `tests/test_storage.py`, v.v.

**Thêm mới (phần C):**
- `main.py`: CLI ghép các module.
- `app/runner.py`: chạy song song, quản lý kết nối theo worker; tổng hợp TaskResult.
- `app/config_service.py`: Jinja2, dry-run, backup trước khi áp, xác minh, gọi rollback một lần.
- `app/reporting.py`: xuất JSON/CSV vào `reports/`.
- `app/logging_setup.py`: log metadata vào `logs/operations.log`.
- `templates/cisco_interface.j2`, `templates/mikrotik_comment.j2`: template minh họa.
- `config/checks.example.yaml`, `config/variables.example.yaml`: ví dụ mẫu.
- `tests/test_part_c.py`: test phần C không cần SSH.
- `docs/HUONG_DAN_PHAN_C.md`: tài liệu này.

**Thay đổi file chung:**
- `requirements.txt`: thêm `Jinja2>=3.1,<4` và `pytest>=8,<10`; các dòng A+B cũ giữ nguyên.
- `README.md`: nối thêm hướng dẫn phần C ở cuối.
- `SHA256SUMS.txt`: tạo lại danh sách băm toàn bộ mã/tài liệu để tránh manifest cũ không còn đúng.

## 2. Cài đặt trên Windows 11, VS Code

Mở thư mục `network-backup-system` trong VS Code (không chạy trực tiếp bên trong ZIP).

PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
Copy-Item .env.example .env
```

Nếu máy chỉ có Python 3.13, có thể dùng `py -3.13` nếu các thư viện cài được; bản gốc A+B đã kiểm thử trên Python 3.12 Ubuntu. Không nên dùng Python 3.15 cho buổi chạy demo khi chưa kiểm thử.

Chỉnh `.env` với user/password/secret của lab; không đưa `.env` vào ZIP khi chia sẻ. Các IP mẫu `192.168.241.21` ... `192.168.241.24` chỉ hoạt động khi máy có mạng đến EVE-NG/lab tương ứng.

## 3. Test offline trước khi mở SSH

```powershell
.\.venv\Scripts\python.exe -m compileall -q app main.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe main.py --help
.\.venv\Scripts\python.exe main.py inventory
.\.venv\Scripts\python.exe main.py dry-run --devices R1 --template cisco_interface.j2 --vars config/variables.example.yaml
```

`dry-run` chỉ xem trước, không kết nối thiết bị. Trong ví dụ, một template sinh cùng cấu hình cho mọi thiết bị được chọn; dùng template đúng vendor và chọn đúng nhóm thiết bị.

## 4. Test tích hợp trên lab thật (chỉ khi có SSH)

```powershell
.\.venv\Scripts\python.exe main.py facts --devices R1
.\.venv\Scripts\python.exe main.py --report json backup --devices R1 R2
.\.venv\Scripts\python.exe main.py list --device R1
.\.venv\Scripts\python.exe main.py diff 1 2
.\.venv\Scripts\python.exe main.py baseline --device R1 --backup-id 1
.\.venv\Scripts\python.exe main.py check --devices R1
```

ID `1`, `2` ở trên là ví dụ, phải lấy ID thực từ lệnh `list`. `diff` chỉ so các bản của **cùng thiết bị và platform**.

Trước khi thay đổi cấu hình, chỉnh `config/checks.example.yaml` thành checks đúng interface thực tế. Chỉ thực hiện trên lab do bạn quản lý và đã có đường khôi phục ngoài băng.

```powershell
.\.venv\Scripts\python.exe main.py --report json apply --devices R1 --template cisco_interface.j2 --vars config/variables.example.yaml --checks config/checks.example.yaml --confirm
.\.venv\Scripts\python.exe main.py restore --device R1 --backup-id 1 --checks config/checks.example.yaml --confirm
.\.venv\Scripts\python.exe main.py scheduler --schedule config/schedule.example.yaml
```

Scheduler chỉ chạy khi lệnh đang mở. Bấm Ctrl+C để dừng; lượt đầu sau interval được cấu hình. Chọn một lịch có interval ngắn hơn để test, không sửa trực tiếp file mẫu nếu đang chia sẻ nhóm.

## 5. Hạn chế cần biết (quan trọng)

- `dry-run` chỉ xác nhận mẫu Jinja2 có đủ biến và kiểm tra cú pháp cơ bản, **không** mô phỏng thay đổi cấu hình trên thiết bị.
- `verify_config()` của phần A hiện chỉ hỗ trợ `interfaces`/`ping`; phải cung cấp `--checks` thực tế và kiểm tra có bao phủ thay đổi vừa áp không. Việc thay description không được đảm bảo bằng checks IP/status; bổ sung tiêu chí phù hợp ở A nếu muốn xác minh description.
- Với thất bại khi `apply`, phần C gọi `device.restore_config()` từ restore point do B lưu, **một lần**; mã `rollback=restore_invoked` chỉ có nghĩa thao tác đã trả về, **không chứng minh** trạng thái được khôi phục đầy đủ. Phải kiểm tra lại thiết bị, nhất là khi rớt SSH/RouterOS tự khởi động.
- `push_config()` của Cisco A không lưu startup-config; sau khi xác minh và được phép, cần quy trình lưu startup riêng.
- Kết quả task/report bỏ trường `output`, mật khẩu và nội dung cấu hình; file backup/log vẫn là dữ liệu nhạy cảm, cần kiểm soát quyền truy cập.
- Không có test SSH thật trong môi trường đóng gói. Để nghiệm thu cuối cùng cần chạy trên 4 thiết bị lab theo hướng dẫn A+B.


## Trạng thái mới v2

Đã mở rộng verify, kiểm tra rollback/config_match, diff header, quyền file,
CLI và scheduler report. Chi tiết tại CAP_NHAT_V2.md; kết quả mới tại
KET_QUA_KIEM_TRA.md. Các số test và giới hạn phía trên là lịch sử trước v2.
