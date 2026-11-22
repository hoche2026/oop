# Đo thời gian và độ chính xác để viết Chương 7

Không có số đo mẫu điền sẵn. Đo trên cùng máy, cùng thiết bị, cùng phạm vi
công việc; thực hiện ba lần mỗi cách, ghi từng lần và trung bình. Không lấy
ping RTT, uptime hoặc thời gian chạy unittest làm thời gian tự động hóa.

## Phạm vi công việc phải giống nhau

Chọn R1/R2 để bắt đầu: kết nối từ Ubuntu, lấy running-config, lưu văn bản và
bản phục hồi (Cisco cũng là văn bản), ghi nhận thiết bị/thời gian. Cách tự
động gọi BackupService còn kiểm tra facts/hash và ghi SQLite; phải ghi rõ
phạm vi này trong bảng thay vì so với một lần chỉ gõ show trên console.

Nếu đo thêm MT1, cách thủ công phải gồm cả export, tạo native backup mã hóa,
tải bản native về máy; không so thời gian export đơn lẻ với workflow backup
đầy đủ. Benchmark tự động không tự sửa cấu hình chạy nhưng tạo bản sao.

## Đo tự động

```bash
python benchmark.py auto --devices R1 R2
```

Kết quả có tổng thời gian (bao gồm kết nối, thu thập, file/SQLite), số thiết
bị thành công và backup ID. Lưu file CSV reports/benchmark_auto_*.csv và
ảnh `T13a_ThoiGian_TuDong.png`. Chạy ba lần, không chọn riêng lần nhanh nhất.

## Đo thủ công

Mở sẵn terminal khác để SSH và lưu cấu hình, nhưng chưa bắt đầu tác vụ.

```bash
python benchmark.py manual --devices R1 R2
```

Enter lần đầu bắt đầu bấm giờ; thao tác thủ công trên terminal thứ hai;
Enter lần hai kết thúc. Đây là stopwatch do người dùng bấm, có sai số thao
tác; không tự suy ra cấu hình đúng. Lưu CSV/ảnh `T13b_ThoiGian_ThuCong.png`.
Không dùng phiên SSH đã mở sẵn cho một cách còn cách kia phải kết nối lại
mà không nêu sự khác biệt. Đo có thời gian nhập mật khẩu nếu phạm vi có login.

## Kiểm tra độ chính xác

Lưu toàn bộ show running-config thủ công vào file UTF-8 riêng trên máy lab,
bỏ dấu nhắc/lệnh đã gõ nhưng giữ nội dung cấu hình. Lấy ID bản tự động cùng
trạng thái thiết bị từ kết quả benchmark hoặc main.py list:

```bash
python benchmark.py compare --manual-file DUONG_DAN_FILE_THU_CONG --backup-id ID_THAT
```

Đây là hai chỗ phải thay bằng đường dẫn/ID thực tế. Kết quả
same_normalized_config=true mới chứng minh hai văn bản tương đương sau
lọc header theo comparison.py. Nếu thiết bị đổi cấu hình giữa hai lần lấy,
phải đo lại hoặc ghi rõ khác biệt, không sửa kết quả thành true.
Ảnh `T13c_DoChinhXac.png` không chụp nội dung config thô.

CSV thời gian ghi accuracy=not_measured; kết quả compare là phép kiểm tra
riêng, không tự gán accuracy=100% từ việc không phát sinh ngoại lệ.
Đội báo cáo lập bảng số thật: cách làm, thiết bị, phạm vi, thời gian ba lần,
trung bình, số bản đầy đủ và số bản đối chiếu đạt. Nêu sai số/thứ tự chạy.
