# CHẠY GIAO DIỆN WEB – Network Backup System A+B+C

## 1. Cài đặt trên Windows 11 / VS Code / Python 3.13

Mở đúng thư mục **bên trong** có `main.py`, `web_app.py`, `requirements.txt`.

Ví dụ, nếu đã giải nén gói ZIP này vào `D:\Tai`:

```powershell
cd D:\Tai\network-backup-system
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Nếu có `.venv` ở thư mục cha, bạn có thể tiếp tục dùng môi trường cũ, nhưng **phải cài lại** file requirements mới để có Streamlit.

Tạo `.env` từ file mẫu và điền tài khoản SSH **trên máy của bạn**, KHÔNG đẩy `.env` lên Git:

```powershell
Copy-Item .env.example .env
```

## 2. Mở giao diện Web

```powershell
.\.venv\Scripts\python.exe -m streamlit run web_app.py --server.address 127.0.0.1 --server.port 8501
```

Mở: http://127.0.0.1:8501  (trình duyệt thường tự mở).

Muốn dừng Web: quay lại Terminal nhấn `Ctrl+C`.

**Không dùng `python web_app.py`**: Streamlit cần được chạy qua `-m streamlit run`.

## 3. Các mục Web

| Tab | Chức năng |
|---|---|
| Inventory | Xem, lọc nhóm/role/tag, thêm, sửa, xóa thiết bị |
| Thiết bị & SSH | Kết nối, thu thập facts đồng thời và trạng thái theo thiết bị |
| Backup & Kiểm tra | Backup thủ công nhiều thiết bị, kiểm tra khác biệt baseline |
| Phiên bản & Restore | Xem lịch sử, diff hai bản, chọn baseline, restore có xác nhận |
| Template & Apply | Render Jinja2, dry-run offline, apply có backup trước và rollback khi lỗi |
| Lịch sao lưu | Khởi động/dừng scheduler dùng file `config/schedule.example.yaml` |
| Báo cáo & Log | Xuất JSON/CSV, tải báo cáo, xem 120 dòng log cuối |

### Chú ý

- **Mọi thao tác SSH cần lab thật**, với IP và tài khoản đúng trong `inventory/devices.yaml` và `.env`. Số thiết bị inventory **không phải số Online**.
- Web không thay đổi code phần A, B, C; toàn bộ CLI cũ (`python main.py --help`) và test cũ vẫn dùng được.
- `Restore` và `Apply` có thể làm mất kết nối SSH. Chỉ dùng trên thiết bị lab, có truy cập console dự phòng, điều kiện xác minh YAML đúng môi trường.
- Tác vụ Apply dùng cơ chế rollback có sẵn của C (có thử khôi phục, **không khẳng định khôi phục đã được xác minh**).
- Nếu thiết bị không hỗ trợ trường CPU/RAM, phần facts hiển thị theo dữ liệu thực mà A trả về.
- Scheduler chạy theo **tiến trình Web**. Nếu cần lịch hoạt động liên tục, dùng terminal riêng `python main.py scheduler` (và đừng chạy đồng thời cả hai scheduler trên cùng thiết bị).
- Streamlit phiên bản này **chưa có đăng nhập/phân quyền**. Chỉ phục vụ `127.0.0.1`; không mở Internet/public IP. Không lưu `.env` vào thư mục public.
- Dùng một người điều khiển trên một máy ở phiên bản lab; không sử dụng như hệ thống quản lý mạng doanh nghiệp multi-user.

## 4. Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe main.py --help
```

Sau đó mở Web và thử theo thứ tự: Inventory -> Dry-run -> SSH/Facts -> Backup -> Lịch sử -> Baseline -> Check -> Diff -> Apply -> Restore -> Báo cáo.

## 5. Files thêm/sửa

**Thêm mới:** `web_app.py`, `app/web_backend.py`, `tests/test_web_backend.py`, `CHAY_WEB_WINDOWS.md`.

**Bổ sung** `requirements.txt` (thêm Streamlit), `.gitignore` (loại trừ `.streamlit/secrets.toml`), `README.md` (hướng dẫn Web), `SHA256SUMS.txt` (hash cập nhật).

**Giữ nguyên 100% nội dung:** `app/devices/`, `app/inventory.py`, `app/contracts.py`, `app/backup.py`, `app/storage.py`, `app/scheduler.py`, `app/normalization.py`, các file phần C cũ (`main.py`, `app/runner.py`, `app/config_service.py`, `app/reporting.py`, `app/logging_setup.py`), toàn bộ test A/B/C gốc.
