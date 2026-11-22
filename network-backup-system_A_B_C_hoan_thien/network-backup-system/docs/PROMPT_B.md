# Prompt tiếp tục phần B trong Codex

Mở thư mục network-backup-system trong Codex rồi dùng nội dung sau.
Nếu code đã thay đổi, Codex cần kiểm tra trạng thái thực tế trước khi làm.

```text
Tôi là Dương, nhận phần B của dự án network-backup-system.
Hãy đọc AGENTS.md, docs/HANDOFF_A.md, docs/PART_A_API.md,
docs/handover_B.md và code hiện có trước khi sửa.

Đã có app/storage.py và app/backup.py. Mốc gần nhất có 49 unittest đạt.
Hãy kiểm tra lại tình trạng thực tế, giữ nguyên công việc đang có.

Tiếp tục phần B còn thiếu, ưu tiên app/scheduler.py,
config/schedule.example.yaml và tests/test_scheduler.py:
- Lịch sao lưu theo khoảng thời gian từ YAML, kiểm tra dữ liệu đầu vào.
- Gọi TaskRunner.run(device_infos, task_name, task_callable) của C.
  Nếu C chưa có runner, dùng đối tượng runner được truyền vào và runner giả
  trong kiểm thử; không viết lại phần C hoặc tự đổi hợp đồng công khai.
- task_callable nhận thiết bị đã kết nối và gọi BackupService.create_backup().
- Không cho hai lượt lịch chạy chồng lên cùng thiết bị; lỗi phải có dấu vết
  và không làm dừng lịch của thiết bị khác.
- Có cách chạy thường trực, dừng gọn và hướng dẫn nối với main.py của C.
- Kiểm thử ít nhất hai lượt chạy bằng đồng hồ/runner giả, không chờ lâu.
- Không cài dịch vụ hệ điều hành; không thêm thư viện nếu thư viện hiện có đủ.

Chỉ sửa phạm vi B. Giữ nguyên tên phương thức và dữ liệu A/B/C. B không tự
connect/disconnect hoặc viết lệnh riêng theo hãng. Giữ riêng cấu hình văn bản
và restore point; không lấy export MikroTik thay backup phục hồi nhị phân.
Nếu cần thay file dùng chung, nêu lý do và ảnh hưởng trước khi thay đổi.

Môi trường là Windows, .venv dùng Python 3.12. Chạy kiểm thử bằng
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Cập nhật docs/handover_B.md và mốc tiến độ trong AGENTS.md.

Thực hiện code và kiểm thử, giải thích từng bước bằng tiếng Việt. Báo rõ
file thay đổi, số kiểm thử thực sự đã chạy, hạn chế và bước thử lab còn cần.
Không tự kết nối/sửa thiết bị thật hoặc coi kiểm thử giả lập là minh chứng lab.
```
