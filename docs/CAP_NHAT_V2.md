# Cập nhật v2 — 12/11/2026

## Nguồn và quyền thay đổi

Kế thừa bản tích hợp v1 (A+B+C). Người dùng yêu cầu hoàn thiện toàn bộ phần
còn thiếu để chỉ tải ZIP và chạy nghiệm thu. Sửa các module A/B/C liên quan,
giữ chữ ký công khai cũ và schema BackupRecord/TaskResult; thêm API tùy chọn.
Không nâng hàng loạt phiên bản thư viện A; ghim Jinja2/pytest và phụ thuộc
đã dùng trong môi trường kiểm tra để cài lại được.

## Verify mở rộng

`device.verify_config(config_text, checks)` giữ nguyên chữ ký, thêm các khóa:

| Khóa | Nền tảng | Ý nghĩa |
|---|---|---|
| config_match: true | Cả hai | Running config bằng văn bản config_text sau lọc header |
| config_lines: [dòng] | Cả hai | Mỗi dòng lệnh nguyên vẹn phải có trong export/run |
| config_absent: [dòng] | Cả hai | Dòng không được có |
| interface_descriptions: {tên: mô tả} | Cisco | Đúng description trong stanza interface |
| interface_comments: {tên: comment} | MikroTik | Đúng comment interface qua dữ liệu có cấu trúc |
| ospf_neighbors: [router-id] | Cisco | Đúng neighbor ID ở trạng thái FULL |
| ospf_routes: [prefix/mask] | Cisco | Đúng prefix, nguồn route là OSPF |

interfaces/ping cũ giữ nguyên. Coverage B/C dùng chung required_criteria:
không chấp nhận dict passed=True nếu thiếu kết quả một tiêu chí đã yêu cầu.
Chi tiết kết quả không in nội dung config_lines hoặc config gốc.

## Rollback và OSPF

ConfigService khi push/verify lỗi gọi restore đúng một lần từ bản trước,
đọc lại running-config và so với cấu hình nguyên bản của bản trước.
rollback=verified khi config_match đạt, verification_failed khi khác,
failed khi có lỗi restore/đọc/verify. Luôn giữ task gốc failed và pre_backup_id.
Phạm vi rollback_scope=running_config, không suy ra neighbor/route đã hội tụ.

OspfLab lưu backup cả R1/R2 trước lần push đầu; state JSON ghi nguyên tử
trước push. Push cả hai xong mới poll verify. Nếu apply/verify lỗi, thử
restore cả hai một lần qua B.restore(config_match), giữ mọi kết quả failed.
State còn lại cho cứu hộ bằng ospf restore; kiểm tra endpoint và hash cả hai
bản sao trước thao tác restore thủ công. Không chạy chồng hai CLI OSPF.

## Diff, lưu trữ và báo cáo

B vẫn lưu file gốc. comparison_lines chỉ loại các header nhận diện được:
Building configuration..., Current configuration : N bytes, ! Last
configuration change at..., ! NVRAM config last updated at..., ! No
configuration change since last restart, !Time:, header ngày giờ RouterOS.
Comment và lệnh khác không bị bỏ. Tất cả timestamp trong lệnh cấu hình
được giữ, không dùng regex bỏ mọi ngày giờ.

Dữ liệu mới và thư mục dữ liệu trên POSIX có quyền 600/700, không đổi umask
toàn tiến trình. SQLite file được tạo 600 trước connect. Report ghi thay thế
nguyên tử với quyền riêng tư. Rotating log mới và file xoay đều được tạo 600.
Windows cần NTFS ACL. Đây không phải mã hóa at-rest cho Cisco backup.

TaskRunner thêm on_results callback (mặc định None), dùng cho báo cáo mỗi
lượt scheduler. Khóa endpoint dùng chung giữa runner trong cùng tiến trình,
không phải khóa nhiều tiến trình. Scheduler vẫn cần tiến trình sống và
không tự cài service/hot reload. Mặc định report JSON; tùy chọn CSV.

## Cập nhật CLI

Có --summary; chọn nhóm/role/tag cho facts/backup/check/apply/dry-run;
biến/checks riêng theo {devices: {R1: {...}, R2: {...}}}; inventory CRUD;
ospf dry-run/apply/verify/restore; diff mặc định che dòng nhạy cảm phổ biến.
--raw cho diff là dữ liệu riêng tư, không đưa lên báo cáo. Không dùng che
regex như bảo đảm mọi bí mật có thể được nhận diện; report tự động bỏ hẳn diff.

## Chưa đo/chưa nghiệm thu

Chưa truy cập EVE của người dùng. Không có số đo nhanh hơn thủ công được
bịa sẵn. Chưa xác nhận mọi IOS/version, startup-config, hardware serial CHR,
VLAN database IOL hoặc routing vendor khác. Xem hướng dẫn và file kết quả
kiểm tra để phân biệt test I/O giả với nghiệm thu lab.
