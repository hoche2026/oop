# Quy tắc làm việc trong dự án

## Bối cảnh và cách hỗ trợ

- Dự án: hệ thống sao lưu và khôi phục cấu hình tập trung, bài tập lớn OOP.
- Dương nhận phần B: sao lưu, phiên bản, diff, baseline, phát hiện thay đổi,
  khôi phục, lịch sao lưu và SQLite.
- A đã bàn giao module thiết bị và inventory. C phụ trách CLI, điều phối,
  cấu hình hàng loạt, log/báo cáo và tích hợp.
- Hướng dẫn bằng tiếng Việt, giải thích ngắn gọn mục đích của lệnh và code.
  Triển khai theo từng bước có thể kiểm tra được; báo rõ phần hoàn thành,
  kết quả kiểm thử và phần chưa làm.
- Không suy diễn chức năng đã hoàn thành từ kế hoạch hoặc tên phương thức.
  Căn cứ vào code và kết quả chạy thực tế.

## Đọc trước khi tích hợp

- `docs/HANDOFF_A.md`: phạm vi bàn giao của A.
- `docs/PART_A_API.md`: giao tiếp thực tế và giới hạn thiết bị.
- `docs/handover_B.md`: phần B đã làm, API lưu trữ và hạn chế hiện tại.
- `README.md`: môi trường và cách sử dụng lab.

## Ranh giới trách nhiệm và file

- B quản lý: `app/storage.py`, `app/backup.py`, `app/scheduler.py`,
  `config/schedule.example.yaml`, `tests/test_storage.py`,
  `tests/test_backup.py`, `docs/handover_B.md`; có thể bổ sung kiểm thử
  scheduler và tài liệu/demo thuộc phạm vi B khi cần.
- A quản lý `app/devices/`, `app/inventory.py`, inventory mẫu và kiểm thử A.
- C quản lý `main.py`, runner, config service, reporting, logging setup,
  templates và README tổng hợp.
- Khi làm B, giữ thay đổi trong phạm vi B. Nếu phát hiện lỗi ở A/C, nêu rõ
  lỗi và ảnh hưởng; phối hợp trước khi sửa giao tiếp hoặc hành vi liên quan.
- File dùng chung cần nhóm thống nhất trước khi thay đổi giao tiếp hoặc
  cấu hình chung: `app/contracts.py`, `requirements.txt`, `.env.example`,
  `.gitignore`. Nếu Dương đã xác nhận phạm vi thay đổi trong cuộc trao đổi
  hiện tại thì thực hiện trong phạm vi đó, không hỏi lại cùng một việc.
- Không tự đổi tên hàm, tham số, kiểu dữ liệu công khai giữa A/B/C.
  Đề xuất thay đổi phải nêu hàm cũ, hàm mới, lý do và phần bị ảnh hưởng.

## Môi trường và công nghệ

- Dùng Python 3.12 theo môi trường đã kiểm thử của A; máy Dương đã cài 3.12.10.
- Dùng `.venv` riêng của dự án; không sao chép môi trường ảo giữa các máy.
- Trên Windows, ưu tiên gọi `.\.venv\Scripts\python.exe` trực tiếp để tránh
  shortcut Microsoft Store hoặc Python khác trong PATH.
- Cài thư viện theo `requirements.txt`; không tự nâng phiên bản hàng loạt.
- Công nghệ chung: Netmiko, PyYAML, python-dotenv, Jinja2; thư viện chuẩn
  `sqlite3`, `difflib`, `logging`, `ThreadPoolExecutor`.
- Bản phân công dự kiến pytest; code bàn giao và kiểm thử hiện có dùng
  unittest. Dùng bộ kiểm thử đang chạy được, chưa cần thêm pytest để bắt đầu.
- Chưa cần cài thêm skill, plugin hoặc framework subagent để viết phần B.

## Hợp đồng BackupService cần giữ

Các phương thức công khai dự kiến theo phân công:

| Phương thức | Kết quả |
|---|---|
| `create_backup(device)` | `BackupRecord` |
| `list_backups(device_name)` | Danh sách `BackupRecord` |
| `read_backup(backup_id)` | Chuỗi cấu hình |
| `compare(first_id, second_id)` | Chuỗi unified diff |
| `set_baseline(device_name, backup_id)` | Không trả dữ liệu |
| `check_changes(device)` | Dictionary: device, baseline_id, changed, diff |
| `restore(device, backup_id, checks)` | Dictionary kết quả, kèm ID bản sao trước thao tác |

- `BackupRecord` có sáu trường: backup_id, device_name, platform,
  created_at, file_path, sha256. Hiện được định nghĩa trong `app/storage.py`.
- Dùng ngoại lệ có ý nghĩa từ `app/contracts.py`, như `BackupError`,
  `RestoreError`, `VerificationError`; không biến lỗi thành thành công.

## Kết nối và phối hợp với A/C

- B nhận thiết bị đã kết nối. Trong luồng tích hợp, TaskRunner của C tạo
  thiết bị, connect, gọi tác vụ và disconnect trong finally.
- B không tự đóng kết nối mà C đang quản lý.
- Mỗi worker dùng đối tượng và phiên SSH riêng; không chia sẻ phiên SSH
  giữa các luồng.
- Không viết lệnh Cisco/MikroTik hoặc chuỗi `if platform == ...` trong B.
  Gọi phương thức chung của A.
- Khi cần facts chung, dùng `get_normalized_facts()` và kiểm tra status;
  dữ liệu invalid/không thu thập được không được coi là hợp lệ.

## Dữ liệu sao lưu và baseline

- `device.backup_config()` trả văn bản để lưu lịch sử, diff và baseline.
- `device.create_restore_point()` trả chuỗi phục hồi; lưu nguyên chuỗi riêng
  và liên kết với cùng phiên bản. `restore_config()` nhận chuỗi phục hồi này.
- MikroTik export văn bản không thay thế được backup nhị phân phục hồi.
  Không dùng nội dung gói nhị phân để diff cấu hình.
- Lưu nguyên văn UTF-8, giữ xuống dòng. Nếu cần chuẩn hóa để diff thì làm
  trên bản dùng so sánh và ghi rõ quy tắc bỏ qua dòng; không sửa file gốc.
- Mỗi phiên bản có file riêng, thời gian ISO 8601 có múi giờ và SHA256.
  Baseline chỉ tham chiếu backup_id; không ghi đè bản sao cũ.
- Chưa có baseline phải báo lỗi rõ ràng, không trả changed=False mặc định.
- Đường dẫn lưu trong metadata tương đối với dự án; không hardcode đường
  dẫn máy cá nhân. Từ chối tên/đường dẫn thoát ra ngoài thư mục dự án.
- Kiểm tra file tồn tại và SHA256 khi đọc dữ liệu dùng cho phục hồi.

## Khôi phục và xác minh

1. Kiểm tra bản sao đúng thiết bị và nền tảng.
2. Kiểm tra toàn vẹn cấu hình và restore point.
3. Tạo, lưu thành công bản sao trước thao tác.
4. Gọi phương thức khôi phục của A bằng restore point đã lưu.
5. Xác minh theo checks và trả kết quả kèm ID bản sao trước thao tác.

- Không có ngoại lệ chưa đủ để kết luận khôi phục thành công.
- Không giả định dictionary kết quả restore của các nền tảng có cùng khóa.
- Kiểm tra `VerificationResult.passed`, details và checks. Tiêu chí chưa
  được kiểm tra phải thể hiện rõ, không tự mặc định đạt.
- A hiện kiểm tra hậu điều kiện interface/ping; chưa chứng minh toàn bộ
  cấu hình giống bản sao hoặc các điều kiện chuyên biệt OSPF/VLAN/ACL.
- Restore MikroTik có reboot. Khi timeout/mất SSH, báo trạng thái chưa xác
  định nếu chưa xác minh được; không tự lặp restore/rollback vô hạn.
- Tác vụ thất bại dù rollback thành công vẫn phải ghi nhận thất bại,
  kèm kết quả rollback riêng.

## SQLite và lịch chạy

- Không chia sẻ một connection SQLite giữa các worker. Mở connection theo
  thao tác, đóng rõ ràng; context manager của sqlite3 chỉ quản lý transaction,
  không tự đóng connection.
- Dùng truy vấn có tham số, foreign keys, transaction và timeout phù hợp.
  Tầng lưu trữ hiện dùng WAL và timeout 30 giây.
- Chỉ công bố phiên bản sau khi ghi đủ hai file và commit metadata thành công.
  Báo đúng giới hạn: filesystem và SQLite chưa có giao dịch nguyên tử chung;
  tắt tiến trình đột ngột có thể để lại file mồ côi.
- B đọc lịch theo khoảng thời gian và gọi TaskRunner của C để thực thi.
- Không cho hai lượt sao lưu theo lịch chồng lên cùng thiết bị.
- Scheduler chỉ hoạt động khi tiến trình chạy; bản đầu không cần cài dịch vụ
  hệ điều hành. Không dùng lịch tự động của ứng dụng AI thay scheduler dự án.

## Kiểm thử, dữ liệu nhạy cảm và bàn giao

- Kiểm thử logic bằng thiết bị giả lập và thư mục/database tạm; không cần
  EVE hoặc thông tin đăng nhập thật cho kiểm thử offline.
- Không tự chạy các demo push/restore có thay đổi thiết bị khi chỉ kiểm thử
  code offline. Kiểm thử lab phải theo kịch bản và phạm vi đã được cho phép.
- Kiểm thử thay đổi có ý nghĩa: nhiều phiên bản, diff, baseline, lỗi file/hash,
  lỗi DB, restore/verify thất bại, ghi đồng thời, lịch không chồng tác vụ.
- Khi thay đổi chức năng B, cập nhật kiểm thử và `docs/handover_B.md`.
- Tại thư mục gốc dự án, chạy trên PowerShell:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_storage.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

- Chỉ báo số kiểm thử đạt sau khi thực sự chạy. Phân biệt kiểm thử giả lập
  với minh chứng trên thiết bị thật.
- Không commit `.venv`, `.env`, mật khẩu, khóa, database hoặc bản sao thật.
  Các thư mục dữ liệu sinh ra gồm `data/`, `backups/`, `logs/`, `reports/`.
- `.gitignore` đã bỏ qua data/, backups/, logs/, reports/ và thư mục tạm của
  kiểm thử B. Kiểm tra danh sách file trước khi commit; không dùng `git add .`
  thiếu kiểm tra.
- Log và ảnh minh chứng phải che bí mật. Base64 không phải mã hóa.
- Theo quy ước nhóm, phần B dùng nhánh `feature/backup` trong kho chung;
  kiểm tra trạng thái Git trước khi thao tác. Không ghi đè thay đổi của người khác.
- Bàn giao cần có API thực tế, hướng dẫn chạy, đầu vào/đầu ra mẫu, kết quả
  kiểm thử, minh chứng đã loại bí mật và các hạn chế còn tồn tại.

## Mốc hiện tại — 10/11/2026

- Đã có `BackupStorage`, `BackupRecord`, quản lý baseline và `BackupService`
  (sao lưu, lịch sử, diff, phát hiện sai lệch, luồng restore/verify).
- Đã có scheduler interval YAML nhận runner của C, cấu hình ví dụ và
  16 phương thức unittest scheduler.
- Kiểm tra lại ngày 10/11/2026: Python gốc và .venv đều chạy được với
  Python 3.12.10. Sau sửa hai P2, toàn bộ 70/70 unittest đạt (22 A, 11 storage,
  21 BackupService, 16 scheduler); pip check không phát hiện lỗi phụ thuộc.
- Hai P2 về độ bao phủ verify và fixture source Cisco đã sửa, có năm test
  hồi quy chạy đạt; xem `docs/review_B.md`. Xác nhận này chỉ áp dụng offline.
- Phiên CLI trước đó báo không truy cập được Python và không chạy được test.
  Nguyên nhân khác biệt giữa các phiên chưa xác định; không coi thông báo
  đó là bằng chứng Python đã bị gỡ. Không cần cài lại ở trạng thái hiện tại.
- Chưa có TaskRunner/main.py của C trong bản đang mở; chưa kiểm thử tích hợp
  runner thật hoặc lab thật.
- Bản giải nén ban đầu chưa có Git. Bản bàn giao trên Git được đặt trong
  network-backup-system/ của repository Yena198/oop, nhánh dương.
- Cập nhật mục này khi tiến độ thay đổi; không dùng mốc cũ làm bằng chứng
  cho code mới chưa được kiểm thử.
