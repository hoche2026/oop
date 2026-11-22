---
name: network-backup-review
description: Rà soát Python và nghiệp vụ phần B của network-backup-system khi được yêu cầu review, kiểm tra trước tích hợp hoặc đánh giá sao lưu, khôi phục, SQLite và scheduler. Dùng để tìm lỗi có bằng chứng; không tự triển khai sửa lỗi hay chạy thiết bị thật.
---

# Rà soát phần B

Đưa ra phát hiện có thể kiểm tra lại bằng code và kiểm thử, giải thích bằng
tiếng Việt. Một yêu cầu review chỉ cho phép đọc, kiểm thử offline và viết
báo cáo; chỉ sửa nghiệp vụ khi người dùng đã yêu cầu sửa. Không thêm công cụ,
thư viện, thay môi trường hoặc chạy demo lab chỉ để hoàn tất review.

## Đọc và lần theo luồng

Các đường dẫn dưới đây tính từ gốc dự án, không từ thư mục skill.

1. Đọc `AGENTS.md`, `docs/HANDOFF_A.md`, `docs/PART_A_API.md`,
   `docs/handover_B.md`; dùng `README.md` khi cần cách chạy/môi trường.
   Kiểm tra `git status --short --branch`; nếu không có kho Git, ghi giới hạn
   đó, không tự khởi tạo kho hoặc kết luận không có thay đổi của người khác.
2. Đọc `app/storage.py`, `app/backup.py`, `app/scheduler.py` và các file
   `tests/test_storage.py`, `tests/test_backup.py`, `tests/test_scheduler.py`.
   Đọc `config/schedule.example.yaml` và nơi gọi nếu cần kiểm tra tích hợp.
   Đối chiếu `app/contracts.py` và phương thức A liên quan khi thấy nghi vấn;
   không suy luận hành vi chỉ từ tên hàm, kế hoạch hay tài liệu bàn giao.
3. Lần theo dữ liệu từ thiết bị -> hai loại bản sao -> file/SQLite ->
   baseline/diff -> restore/verify -> kết quả cho C. Với scheduler, theo dõi
   cả việc đang chờ pool, đang chạy, hoàn tất, lỗi và dừng. Đối chiếu test
   với API thật; fake trả thành công vô điều kiện không chứng minh tích hợp.
4. Với mỗi nghi vấn, tìm điều kiện kích hoạt và ảnh hưởng, kiểm tra nhánh
   lỗi cùng test liên quan. Nếu cần tái hiện, chỉ dùng dữ liệu giả và thư mục/
   database tạm, không ghi vào kho bản sao thật. Phân biệt suy luận tĩnh,
   tái hiện đã chạy và điểm còn cần xác minh.

## Các bất biến phải đối chiếu

| Mục | Cần kiểm tra trong code và test |
|---|---|
| Hợp đồng A/B/C | Giữ chữ ký, tham số, kiểu dữ liệu và sáu trường BackupRecord theo AGENTS.md. B quản lý storage/backup/scheduler; A quản lý thiết bị/inventory; C quản lý runner/CLI/log/báo cáo. File dùng chung và thay đổi giao tiếp cần theo phạm vi đã thống nhất. Báo lỗi liên quan A/C, không tự sửa ngoài phạm vi. |
| Phiên SSH | B nhận thiết bị đã kết nối; không tự connect/disconnect phiên C sở hữu, không viết lệnh theo hãng. Mỗi worker có đối tượng và phiên riêng; không chia sẻ phiên giữa luồng. Dùng facts chuẩn hóa và kiểm tra status khi dựa vào section có status. |
| Hai loại bản sao | Lưu nguyên UTF-8/xuống dòng từ backup_config() cho lịch sử/diff và nguyên chuỗi create_restore_point() riêng cho restore_config(). Liên kết cùng phiên bản; export MikroTik không thay được backup nhị phân. Diff không dùng gói nhị phân; quy tắc chuẩn hóa phải rõ và không sửa file gốc. |
| Sở hữu/toàn vẹn | Đúng tên thiết bị/platform, đường dẫn tương đối nằm trong dự án, phiên bản riêng có thời gian kèm múi giờ và SHA256. Kiểm tra tồn tại/hash của cả cấu hình và restore point trước restore. Baseline chỉ tham chiếu ID; chưa có phải báo lỗi. |
| Thứ tự restore | Kiểm tra mục tiêu và toàn vẹn -> lưu thành công bản sao trước thao tác -> restore bằng restore point -> verify -> kết quả có pre_backup_id. Lỗi lưu bản sao phải chặn restore. Lỗi sau đó vẫn giữ ID cứu hộ và stage cho C. |
| Kết luận verify | Kiểm tra passed, details, checks và độ bao phủ các tiêu chí được yêu cầu; dictionary không rỗng chưa đủ. Không giả định khóa restore chung giữa Cisco/MikroTik. Verify thiếu/thất bại hoặc timeout/mất SSH chưa xác minh được phải giữ trạng thái thất bại/chưa xác định. Không suy ra toàn bộ cấu hình đã khớp chỉ từ interface/ping. Không retry/rollback vô hạn; rollback thành công vẫn giữ thất bại của tác vụ gốc. |
| SQLite/đồng thời | Connection riêng mỗi thao tác, đóng rõ trong finally; context transaction không tự đóng connection. Truy vấn tham số, foreign keys, transaction, timeout/WAL theo thiết kế. Chỉ công bố khi đủ hai file và commit metadata. Xem cleanup khi lỗi; không gọi filesystem + SQLite là giao dịch nguyên tử chung. |
| Scheduler | YAML kiểm tra kiểu, giá trị và tên với inventory; gọi runner.run(device_infos, task_name, task_callable), callback gọi create_backup trên thiết bị đã kết nối. Chặn chồng cả việc chờ và chạy theo thiết bị trong phạm vi instance đã thiết kế. Kiểm tra giả định runner đồng bộ, lỗi riêng từng thiết bị, dấu vết lỗi, ít nhất hai lượt đồng hồ giả, stop/close. Khóa liên tiến trình hoặc tác vụ thủ công chưa có và đã công bố là giới hạn, không tự coi là hồi quy. |
| Bí mật và bằng chứng | Không đưa mật khẩu, secret, payload restore, cấu hình/diff nhạy cảm hoặc chuỗi ngoại lệ SSH thô vào báo cáo/log minh chứng. Dùng dữ liệu tổng hợp và che giá trị nhạy cảm; Base64 không phải mã hóa. Đọc code để kiểm tra đường truyền dữ liệu, không mở .env/backup thật nếu không cần. Phân biệt test fake, tích hợp runner thật và lab thật. |

## Kiểm thử

Chạy tại gốc dự án trên PowerShell, dùng Python 3.12 của `.venv`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Khi cần khoanh vùng, dùng cùng lệnh với `-p test_storage.py`,
`-p test_backup.py` hoặc `-p test_scheduler.py`. Không thêm pytest/framework
để chạy bộ unittest hiện có. Không tự chạy demo push/restore hoặc kết nối
thiết bị thật. Kiểm thử cần bao phủ nhiều phiên bản, baseline/diff, lỗi
file/hash/DB, restore/verify thất bại, ghi đồng thời và lịch không chồng.

Ghi lệnh, exit code và số test thực sự chạy theo output. Nếu Python không
khởi động hoặc discovery lỗi, ghi đúng trở ngại và phần chưa chạy; không lấy
số test trong mã hoặc lần chạy cũ làm kết quả mới. Khi báo không tìm thấy
Python, kiểm tra đường dẫn/quyền truy cập sẵn có; không suy ra đã bị gỡ hoặc
tự cài lại. Kết quả bàn giao từ phiên khác phải ghi riêng là lịch sử.

## Báo cáo

Đưa phát hiện theo mức độ, rồi kết quả kiểm thử và giới hạn. Mỗi phát hiện
cần: `[P1/P2/P3] tiêu đề`, `file:dòng` chính xác, tình huống kích hoạt,
hành vi hiện tại, tác động, bằng chứng và hướng khắc phục/kiểm thử đề xuất.
Nêu rõ chưa tái hiện khi chỉ suy luận tĩnh. Không đưa nghi vấn chưa đủ bằng
chứng vào danh sách lỗi đã xác nhận; ghi riêng câu hỏi/giới hạn tích hợp.

- **P1 — nghiêm trọng:** có đường chạy thực tế dẫn tới khôi phục sai thiết
  bị, mất bản sao cứu hộ, thành công giả khi tác vụ đã lỗi hoặc lộ bí mật.
  Nêu điều kiện cụ thể; không nâng mức chỉ vì đề tài khôi phục có rủi ro.
- **P2 — cần sửa:** lỗi chức năng có điều kiện rõ, thiếu bảo vệ/kiểm thử
  ở ranh giới hợp đồng có ảnh hưởng cụ thể; nêu mức ảnh hưởng thực tế hiện tại.
- **P3 — nhẹ:** hạn chế chẩn đoán/tài liệu/bảo trì có tác động nhỏ đã chỉ ra.

Nếu không tìm thấy lỗi, nói không có phát hiện trong phạm vi đã kiểm tra,
không khẳng định hệ thống hoàn toàn đúng. Nêu riêng giới hạn đã công bố
(file mồ côi khi crash, khóa scheduler trong một instance, phạm vi verify A,
runner/lab chưa tích hợp). Dùng link file kèm dòng, không dán cấu hình thật.
Kết thúc bằng phần đã rà soát, số test thực chạy và bước kiểm chứng còn cần.
