# Bàn giao phần A — bản reviewed-v1

Đây là bản mã nguồn đầy đủ của phần A sau rà soát. Thành viên B/C giải nén
ra thư mục mới, đọc README.md và docs/PART_A_API.md trước khi tích hợp.
Không cần cài gói A-reviewfix-1 lên bản này vì các sửa đổi đã được đưa vào.

## Phạm vi bàn giao

- Inventory YAML: đọc, CRUD, lọc nhóm/vai trò/tag.
- Lớp thiết bị trừu tượng, Factory, Cisco router/switch và MikroTik.
- SSH có xác minh host key và kiểm tra phiên còn sống khi connect().
- Thu thập facts gốc và facts chuẩn hóa phiên bản 2.
- Lấy cấu hình văn bản, tạo restore point, đẩy cấu hình.
- Khôi phục Cisco bằng configure replace; MikroTik bằng backup nhị phân,
  reboot và kết nối lại.
- Xác minh hậu điều kiện interface và ping IPv4.
- Bộ kiểm thử giả lập, các chương trình demo và hướng dẫn chạy.

## Bằng chứng kiểm tra

- Môi trường review Python 3.12 cài được requirements.txt; pip check đạt.
- 15 tests gốc đạt trước sửa; 22 tests đạt sau sửa, gồm 7 tests hồi quy mới.
- Bài thử CRUD trên bản inventory tạm đạt; inventory gốc không bị sửa.
- Người dùng đã chạy lab thực tế với R1/R2/SW1/MT1: kết nối và thu thập 4/4;
  đã thử push, verify và khôi phục trên lab theo từng nền tảng.
- Sau áp dụng reviewfix-1, ảnh người dùng cung cấp tiếp tục cho thấy 4/4,
  RAM đọc được và CPU bất thường được đánh dấu invalid/None.
- Môi trường review không truy cập EVE của người dùng, không tự chạy lại
  push hoặc restore trên thiết bị thật.

## Những sửa đổi đã đưa vào

1. Bổ sung .gitignore trong gói bàn giao.
2. Không tái sử dụng phiên SSH đã chết; xử lý khi kiểm tra phiên gặp lỗi.
3. Cleanup thất bại không che mất lỗi connect/enable ban đầu.
4. Phát hiện thêm phản hồi lỗi CLI Cisco bắt đầu bằng % Error và lỗi lệnh.
5. Dữ liệu RAM/section sai cấu trúc được đánh dấu error ở từng mục.

## B bắt đầu từ đâu

- Gọi backup_config() để lưu văn bản và làm diff.
- Gọi create_restore_point() và lưu nguyên chuỗi riêng để có thể phục hồi.
- Liên kết hai loại bản sao theo thiết bị, thời gian và phiên bản trong kho.
- Không dùng export MikroTik thay thế gói backup nhị phân.
- Không chia sẻ mật khẩu, .env hoặc backup thật qua gói mã nguồn/Git.

## C bắt đầu từ đâu

- Dùng InventoryManager và DeviceFactory; mỗi worker có kết nối riêng.
- Dùng get_normalized_facts() cho dữ liệu chung; kiểm tra status từng mục.
- Lưu restore point thành công trước khi thay đổi; điều phối dry-run,
  push, verify, rollback và tổng hợp lỗi theo từng thiết bị.
- Sau restore, kiểm tra điều kiện trạng thái ban đầu, không chỉ kiểm tra
  một cờ trong dictionary kết quả.
- Kết quả restore Cisco/MikroTik có khóa riêng; xem tài liệu API.

## Giới hạn cần giữ trong báo cáo và kiểm thử tích hợp

- CPU Dynamips có thể báo 0%/100%; không ép số liệu lỗi thành giá trị hợp lệ.
- Phạm vi đo CPU/RAM khác nhau được giữ ở sample_window và scope.
- Serial CHR chưa thu thập; không tự dùng system-id làm serial phần cứng.
- Phục hồi riêng cơ sở dữ liệu VLAN của IOL chưa kiểm chứng.
- verify_config() chưa xác minh toàn bộ cấu hình hoặc chuyên biệt OSPF/VLAN/ACL.
- Kịch bản định tuyến/chuyển mạch tự động của đề bài và quy trình tích hợp
  B/C vẫn cần triển khai; đây chưa phải sản phẩm hoàn chỉnh của cả nhóm.

## Cách dùng bản này

Trên máy mới, tạo .venv và .env theo README. Lab cần truy cập được nếu chạy
bài kiểm tra thiết bị thật. Chỉ chạy unittest thì không cần EVE.

Trên máy đại ca đã áp dụng reviewfix-1, không cần ghi đè dự án đang chạy
bằng ZIP này. Giữ .env và dữ liệu backup hiện có; ZIP này dùng bàn giao.

Không kèm máy ảo, image thiết bị, .env thật, .venv, cấu hình backup thật
hoặc ảnh minh chứng trong gói. Ảnh minh chứng đã chụp được bàn giao riêng
sau khi kiểm tra không chứa mật khẩu hoặc cấu hình nhạy cảm.
