# Chạy bản tổng A+B+C và chụp minh chứng

Mỗi mục: chạy lệnh -> đợi kết quả -> chụp -> lưu đúng tên ảnh -> chuyển mục.
Không cần sửa mã Python. Không ghi đè thư mục A cũ. Không chụp mật khẩu/.env
hoặc backup thô. Tất cả kết quả mô tả dưới đây là kỳ vọng cần xác nhận tại
lab của bạn, không phải kết quả EVE đã được xác nhận bởi tác giả bản ZIP.

## Bước 0 — Cài bản nguồn đã gộp fix

Bản nguồn này đã tích hợp fix dòng phân cách R2. Không tải/cài lại hai ZIP
cũ. Làm theo README.md ngay tại thư mục có main.py để tạo venv và cấu hình.
Tên chương trình và thư mục network-backup-ABC-v2/network-backup-system giữ
nguyên để đối chiếu với ảnh. Mỗi máy có thể đặt thư mục cha ở vị trí khác.

Người đang có lab chạy đạt không cần ghi đè bản đang chạy hoặc chạy lại các
bài thay đổi chỉ để đóng gói. Các bước sau là hướng dẫn tái hiện cho người mới.

## T01 — Topology

Không chạy lệnh. Chụp EVE nhìn rõ R1/R2/SW1/MT1, MangQuanTri và đường nối
FastEthernet1/0 R1–R2. Lưu `T01_Topology.png`. Dùng Chương 6.

## T02 — Kiểm thử offline

```bash
clear
python -m unittest discover -s tests -v
```

Chụp phần cuối có số test và OK. Lưu `T02_Unittest.png`, Chương 7.
Một số ca cố ý gây lỗi có log task_failed là bình thường nếu tổng kết OK.
Nếu tổng kết FAILED, dừng và gửi kết quả, chưa chạy bước thay đổi lab.

## T03 — Kết nối/thu thập đủ bốn thiết bị

```bash
clear
python demo_all_devices.py
```

Chụp hai bảng và dòng 4/4. Lưu `T03_ThuThap_4ThietBi.png`, Chương 7.
CPU invalid trên Dynamips phải giữ nguyên, không đổi thành 0/ok.

## T04 — Backup qua CLI chung

```bash
clear
python main.py --summary --report json backup --devices R1 R2 SW1 MT1
```

Kỳ vọng bốn dòng success, mỗi thiết bị có backup ID, có đường dẫn report.
Lưu `T04_Backup_4ThietBi.png`, Chương 7. Bản .cfg và .restore nằm trong
backups/, metadata ở data/app.db. Backup không thay đổi running-config,
nhưng MikroTik tạo file backup nhị phân trên thiết bị.

## T05 — Vòng đời phiên bản/diff/baseline/restore R1

Bước này đổi thử description FastEthernet1/0 rồi khôi phục R1. Không chạy
khi thành viên khác đang cấu hình R1. Giữ console EVE dự phòng.

```bash
clear
python demo_release_lab.py --confirm
```

Kỳ vọng status success, diff_detected=true, drift_detected=true,
restored=true, drift_after_restore=false, và có ID các bản trước/sau/cứu hộ.
Lưu `T05_VongDoi_Backup_R1.png`, Chương 7. Nếu R1 chưa có baseline, demo
để lại bản trước thử làm baseline; baseline cũ nếu có sẽ được đặt lại.
Gateway ping kỳ vọng 192.168.241.2 theo mạng quản trị A.

## T06 — Rollback khi xác minh cố ý sai

Bước này áp description rồi dùng kỳ vọng cố ý sai để kích hoạt rollback.
Không phải lỗi bất ngờ. R1 được phục hồi từ bản ngay trước thao tác.

```bash
clear
python main.py --report json apply --devices R1 --template cisco_interface.j2 --vars config/variables.example.yaml --checks config/checks.rollback_demo.yaml --confirm
```

Kỳ vọng task status=failed (vì tác vụ áp cấu hình thất bại), đồng thời
rollback=verified, rollback_verified=true, rollback_scope=running_config.
Lưu `T06_Rollback_DaXacMinh.png`, Chương 7. Exit code 1 ở bài thử này là
đúng. Nếu rollback_error/verification_failed thì dừng để xem xét; không
tự lặp apply/restore nhiều lần khi chưa biết trạng thái.

## T07 — Lịch sao lưu hai lượt

```bash
clear
python main.py --report json scheduler --schedule config/schedule.lab.yaml
```

Lượt đầu sau khoảng 15 giây. Để chạy ít nhất 35–45 giây và chờ tác vụ đã gửi
hoàn tất, Ctrl+C để dừng. Mở lịch sử:

```bash
python main.py list --device R1
python main.py list --device R2
```

Chụp ít nhất hai phiên bản có thời gian/ID khác nhau, lưu `T07_Lich_Backup.png`.
Reports scheduled_backup_*.json chứa kết quả từng lượt; log ở logs/operations.log.
Không mở nhiều scheduler, không chạy tác vụ thay đổi trong lúc thử lịch.

## T08 — Xem trước OSPF, không thay đổi thiết bị

```bash
clear
python main.py ospf dry-run
```

Hai cấu hình phải khác IP/router-id: R1 10.255.1.1, R2 10.255.2.2.
Lưu `T08_OSPF_DryRun.png`. Kịch bản dùng process 10, Loopback101, mạng
R1–R2 10.10.12.0/30 và area 0; không đổi cổng quản trị.

## T09 — Tự động cấu hình OSPF và kiểm tra hội tụ

Chỉ chạy sau khi T03 đủ 4/4 và không còn scheduler. Không cấu hình OSPF
bằng tay trước. Nếu process 10/Loopback101 đã tồn tại, chương trình sẽ từ
chối ghi đè. Nếu data/ospf_state.json đã tồn tại, dùng verify hoặc restore.

```bash
clear
python main.py --summary --report json ospf apply --confirm
```

Chương trình sao lưu cả hai, lưu state cứu hộ trước push, áp cả hai rồi
chờ hội tụ tối đa khoảng 90 giây cộng thời gian I/O. Kỳ vọng các dòng
ospf_prepare, ospf_apply, ospf_verify của R1/R2 đều success.
Lưu `T09_OSPF_TuDong.png`, Chương 7 và yêu cầu 4.4.
Nếu lỗi, chương trình thử phục hồi cả hai bằng bản trước, giữ trạng thái
failed của tác vụ gốc. Nếu ngắt Ctrl+C giữa chừng, state vẫn giữ để cứu hộ.

## T10 — Minh chứng chức năng OSPF

```bash
clear
python main.py --report json ospf verify
```

Chụp verification: ospf_neighbors, ospf_routes, ping đều true ở hai router.
Lưu `T10a_OSPF_Verify.png`. Nếu cần ảnh lệnh thiết bị trực tiếp, mở console
R1/R2, vào enable, chạy (không cấu hình thủ công):

```text
show ip ospf neighbor
show ip route ospf
```

Neighbor phải FULL, R1 học 10.255.2.2/32, R2 học 10.255.1.1/32 qua OSPF.
Lưu `T10b_OSPF_Neighbor_Route.png`. Trong console R1 có thể chạy:

```text
ping 10.255.2.2 source 10.255.1.1 repeat 5
```

Lưu `T10c_OSPF_Ping.png`. Đây là kiểm chứng kịch bản, không phải số đo
thời gian tiết kiệm của tự động hóa.

## T11 — Khôi phục cả lab về trước thử OSPF

```bash
clear
python main.py --report json ospf restore --confirm
```

Kỳ vọng hai task success và config_match=true; state được xóa sau khi cả
hai phục hồi đạt. Lưu `T11_OSPF_Restore.png`. Không xóa state/backups trước
bước này. Nếu một thiết bị lỗi, state giữ lại để kiểm tra/cứu hộ.
Đây là restore cấu hình chạy; không tự ghi startup-config trong bài thử.

## T12 — Khôi phục native MikroTik

Chỉ thực hiện khi MT1 rảnh. Demo sẽ tạo bridge thử, khôi phục rồi reboot.

```bash
clear
python demo_mikrotik_restore.py
```

Chụp file_verified, reboot_observed, reconnected=true, bridge thử biến mất
và kết quả kiểm tra IP/cổng/ping. Lưu `T12_MikroTik_Restore.png`.
LAB_BACKUP_PASSWORD phải đúng; không chia sẻ file native/restore point.

## T13 — Thời gian và độ chính xác thủ công/tự động

Đọc docs/DO_THOI_GIAN.md trước khi đo. Không tự điền số nhanh hơn bao nhiêu
lần từ kết quả unit test hoặc thời gian ping. Mỗi ảnh dùng cùng thiết bị,
cùng phạm vi tác vụ và điều kiện máy, ghi rõ phần chưa đo.

## Nếu cần dừng buổi thử

Không tắt VM giữa native restore. Nếu OSPF đang áp/lưu state, kiểm tra và
hoàn tất T11 trước khi xóa dữ liệu. Các ảnh chọn lọc gửi đội báo cáo cùng
docs/THIET_KE.md; không gửi .env, backups thật hoặc report còn chứa dữ liệu
nhạy cảm. Bản sao cứu hộ giữ riêng trên máy lab.
