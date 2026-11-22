# Bản tích hợp ABC v2

- Phạm vi người dùng đã cho phép: hoàn thiện toàn bộ code A+B+C và kịch bản lab.
- Đọc README.md, docs/CAP_NHAT_V2.md và docs/CHAY_KIEM_THU_VA_CHUP_ANH.md.
- Giữ API cũ của A/B/C; công khai rõ mọi mở rộng và kiểm tra coverage verify.
- Không lấy test giả làm minh chứng SSH/EVE hoặc tự điền số đo benchmark.
- Không tự chạy lệnh push/restore trong lab khi chỉ kiểm thử offline.
- Không đưa .env, backups, database/log/report thực nghiệm vào ZIP/Git.
- Kiểm tra bằng python -m unittest discover -s tests -v và pip check.
- Mỗi worker có phiên riêng. Không chia sẻ SSH giữa luồng; lỗi thiết bị được
  ghi riêng. Giữ task gốc failed khi rollback thành công; không retry restore
  vô hạn khi timeout. Sau restore phải xác minh hậu điều kiện.
- Khôi phục OSPF bằng state và backup trước thao tác; không xóa dữ liệu cứu hộ
  trước khi hoàn tất nghiệm thu. Không có khóa liên tiến trình.
