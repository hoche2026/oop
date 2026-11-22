# Network Backup System — Phần A

Module quản lý inventory và giao tiếp thiết bị mạng cho bài tập lớn OOP.

## 1. Chức năng đã kiểm chứng

- Đọc, thêm, sửa, xóa và lọc inventory.
- Tạo đối tượng thiết bị bằng Factory.
- Kết nối SSH với Cisco IOS và MikroTik RouterOS.
- Thu thập thông tin thiết bị, trạng thái cổng và dữ liệu vận hành.
- Lấy cấu hình văn bản.
- Đẩy cấu hình và xác minh IP, trạng thái cổng, ping.
- Khôi phục cấu hình trên R1, R2, SW1 và MT1.
- Kiểm thử từ chối bản sao lỗi và giả lập lỗi kết nối.

Đây là phần A, chưa phải toàn bộ sản phẩm nhóm.
Lưu trữ phiên bản, lịch chạy, CLI, dry-run, điều phối rollback và báo cáo
cần được tích hợp với phần B/C.

## 2. Môi trường

Đã kiểm thử trên:

- Ubuntu Server 24.04, Python 3.12.
- Netmiko 4.8.0.
- Paramiko 4.0.0.
- EVE-NG với Cisco 7206VXR, Cisco IOL L2 và MikroTik CHR.

requirements.txt ghi lại các phiên bản thư viện trong môi trường đã chạy.
Chưa xác nhận khả năng cài đặt trên mọi hệ điều hành hoặc phiên bản Python.

## 3. Cấu trúc chính

- app/contracts.py: kiểu dữ liệu và ngoại lệ dùng chung.
- app/inventory.py: quản lý inventory.
- app/devices/base.py: lớp thiết bị trừu tượng.
- app/devices/cisco_ios.py: thiết bị Cisco IOS.
- app/devices/cisco_ios_switch.py: lớp switch Cisco.
- app/devices/mikrotik.py: thiết bị MikroTik.
- app/devices/factory.py: chọn lớp thiết bị.
- inventory/devices.yaml: danh sách thiết bị.
- tests/: kiểm thử giả lập.
- docs/PART_A_API.md: giao tiếp và giới hạn dành cho B/C.
- demo_*.py: các chương trình thực hành và kiểm chứng.

## 4. Cài đặt trên Ubuntu của thành viên mới

Mở terminal tại thư mục dự án.

Nếu máy chưa có hỗ trợ môi trường ảo:

```bash
sudo apt update
sudo apt install python3-venv
```

Tạo và kích hoạt môi trường:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
```

Không sao chép thư mục .venv từ máy khác.
Máy đã có môi trường hoạt động thì chỉ cần kích hoạt, không tạo lại mỗi lần.

## 5. Cấu hình xác thực

Tạo .env từ .env.example nếu chưa có:

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Không chạy lệnh sao chép trên nếu đã có .env được cấu hình.

Điền:

- LAB_USERNAME: tài khoản SSH.
- LAB_PASSWORD: mật khẩu SSH.
- LAB_SECRET: enable secret của Cisco.
- LAB_BACKUP_PASSWORD: mật khẩu mã hóa backup nhị phân MikroTik.

Không đưa .env, bản sao thiết bị hoặc khóa riêng tư vào Git.
Không in thông tin xác thực trong ảnh minh chứng và báo cáo.

## 6. Inventory và kết nối mạng

Lab hiện tại:

| Thiết bị | IP quản trị |
|---|---|
| R1 | 192.168.241.21 |
| R2 | 192.168.241.22 |
| SW1 | 192.168.241.23 |
| MT1 | 192.168.241.24 |

Đây là địa chỉ trong mạng VMware của máy dựng lab.
Thành viên dùng máy khác phải có đường mạng tới lab hoặc gửi code
sang máy dựng lab để kiểm thử tích hợp.

Không cần dựng EVE riêng chỉ để viết logic lưu trữ, CLI hoặc chạy kiểm thử
giả lập. Kiểm thử thiết bị thật cần lab đang chạy và truy cập được.

Trước lần kết nối Python đầu tiên, dùng SSH thủ công để xác minh và chấp
nhận khóa thiết bị. Chương trình bật kiểm tra host key; không tự chấp nhận
khóa chưa biết.

Ví dụ SSH tới MikroTik:

```bash
ssh netadmin@192.168.241.24
```

Với các image Cisco cũ trong lab:

```bash
ssh -oKexAlgorithms=+diffie-hellman-group14-sha1 -oHostKeyAlgorithms=+ssh-rsa -oCiphers=+aes128-cbc netadmin@192.168.241.21
```

Thay IP tương ứng cho R2/SW1. Những tùy chọn này phục vụ image lab cũ.
Nếu khóa thiết bị thay đổi, xác minh nguyên nhân trước khi cập nhật known_hosts.

## 7. Chạy kiểm thử không cần thiết bị

```bash
source .venv/bin/activate
python -m unittest discover -s tests -p "test_*.py" -v
```

Hiện có 22 bài kiểm thử, gồm nhiều trường hợp con.
Kiểm thử giả lập không chứng minh thiết bị thật hoạt động.

## 8. Chạy kiểm tra chỉ đọc với lab thật

Bật máy ảo EVE, Ubuntu chạy chương trình và các node cần kiểm thử.

```bash
source .venv/bin/activate
python demo_inventory.py
python demo_all_devices.py
```

Kết quả lab hiện tại mong đợi:

```text
KET NOI VA THU THAP: 4/4
```

Đọc thêm bảng status của từng mục:
ok, empty, invalid hoặc error.
Kết nối 4/4 không có nghĩa mọi dữ liệu đều hợp lệ.

Các bài đọc riêng:

```bash
python demo_device.py
python demo_switch_facts.py
python demo_mikrotik.py
```

## 9. Các bài thử có thay đổi thiết bị

Chỉ chạy trên lab thử nghiệm đã kiểm tra trạng thái ban đầu.

- demo_push_link.py: cấu hình liên kết R1–R2.
- demo_restore.py: thử khôi phục R1.
- demo_restore_r2.py: thử khôi phục R2.
- demo_switch_restore.py: thử khôi phục running-config SW1.
- demo_mikrotik_push.py: thêm và xóa bridge thử.
- demo_mikrotik_restore.py: tạo bản sao mới, thêm bridge thử,
  khôi phục MT1 và chờ reboot.

Không chạy các bài thay đổi cấu hình đồng thời trên cùng thiết bị.
Không tự chạy lại khi báo lỗi hoặc trạng thái khôi phục chưa xác định.

demo_mikrotik_restore.py sẽ làm MT1 khởi động lại.
Giữ console EVE để theo dõi.

Bản sao trong .local_backups được lưu riêng, không đưa vào gói mã nguồn.
Các bài demo có thể để lại file backup trên thiết bị;
chưa có cơ chế tự dọn toàn bộ file cũ.

## 10. Dùng phần A từ B/C

Đọc docs/PART_A_API.md trước khi tích hợp.

Các phương thức chính:

- backup_config(): cấu hình văn bản để lưu lịch sử và diff.
- create_restore_point(): dữ liệu dùng để phục hồi.
- restore_config(point_text): nhận nguyên restore point.
- verify_config(config_text, checks): xác minh điều kiện trong checks.

Với MikroTik, export văn bản không thay thế bản sao nhị phân để phục hồi.

B lưu restore point thành công trước khi C áp cấu hình.
C điều phối dry-run, xác minh, rollback và bắt lỗi riêng cho từng thiết bị.
Mỗi worker dùng đối tượng và kết nối riêng.

## 11. Giới hạn hiện tại

- Serial của MikroTik CHR chưa được thu thập.
- CPU Cisco mô phỏng có thể trả số liệu bất nhất và bị đánh dấu invalid.
- Khôi phục riêng cơ sở dữ liệu VLAN của SW1 chưa được kiểm chứng.
- verify_config() chưa kiểm tra toàn bộ nội dung cấu hình,
  cũng chưa có điều kiện chuyên biệt cho OSPF/VLAN/ACL.
- Chưa kiểm thử tích hợp đầy đủ với phần B/C.
- Kịch bản mạng tự động theo yêu cầu bài tập lớn vẫn cần phối hợp triển khai.

## 12. Mỗi lần mở máy

1. Bật hai máy ảo EVE và Ubuntu chạy chương trình.
2. Mở lab EVE, bật các node cần dùng.
3. SSH vào Ubuntu.
4. Vào thư mục dự án và kích hoạt .venv.
5. Chạy bài kiểm tra hoặc chương trình cần dùng.

```bash
cd ~/network-backup-system
source .venv/bin/activate
python demo_all_devices.py
```

Không cần mở phiên SSH thủ công tới từng thiết bị trước mỗi lần chạy Python.
Việc xác minh host key chỉ cần thực hiện khi chưa có khóa hoặc khóa thay đổi.

## 13. Minh chứng nên lưu

- Topology đủ bốn thiết bị.
- Inventory và kết quả lọc.
- Bảng thu thập 4/4 thiết bị.
- Kết quả unittest: Ran 7 tests, OK.
- Khôi phục và xác minh R1/R2.
- Khôi phục SW1: mô tả thử biến mất, quản trị vẫn hoạt động.
- Khôi phục MT1: reboot, kết nối lại, bridge thử biến mất.
- Từ chối bản sao lỗi trên Cisco và MikroTik.

Không đưa nội dung bản sao nhạy cảm hoặc mật khẩu vào minh chứng.


## Cập nhật chuẩn hóa dữ liệu — phiên bản 2

B/C dùng device.get_normalized_facts() cho dữ liệu báo cáo và xử lý chung.
get_facts() vẫn trả dữ liệu theo cấu trúc thu thập ban đầu.

get_normalized_facts() trả dictionary có normalization_version=2.

Các mục đã thống nhất:

- cpu.data: usage_percent, sample_window, valid.
- memory.data: total_bytes, used_bytes, free_bytes, used_percent, scope, valid.
- routing_table.data: danh sách destination, protocol, protocol_detail,
  next_hops, distance, metric, routing_table, active.
- Mỗi next_hop có address và interface.
- arp_table.data: danh sách ip_address, mac_address, interface, state, complete.
- neighbors.data: danh sách device_name, management_ip, local_interfaces,
  remote_interface, platform.

Các section giữ cấu trúc status, data, error.
Status có thể là ok, empty, invalid, error hoặc not_collected.
Trường không có dữ liệu được để None, không tự suy diễn giá trị.

CPU invalid không cung cấp usage_percent hợp lệ.
sample_window của CPU và scope của RAM phải được giữ khi báo cáo;
cùng tên trường không có nghĩa phạm vi đo hoàn toàn tương đương.

MAC trong ARP được đưa về dạng chữ thường, ngăn cách bằng dấu hai chấm.
VLAN/MAC table của switch vẫn giữ cấu trúc parser hiện tại.
Uptime hiện vẫn là chuỗi hiển thị của thiết bị, chưa đổi thành số giây chung.

Không dùng cdp_neighbors trong dữ liệu chuẩn để viết logic chung;
dùng neighbors. Khóa cdp_neighbors gốc có thể vẫn còn trong dictionary.

Đã chạy đạt 22 bài unittest và kiểm tra chuẩn hóa trên bốn thiết bị.
Việc này không thay thế kiểm thử tích hợp B/C hoặc kịch bản mạng tự động.

Các giới hạn còn lại: serial của CHR chưa thu thập; phục hồi riêng cơ sở
dữ liệu VLAN của IOL chưa kiểm chứng; kịch bản OSPF/VLAN/ACL tự động và
quy trình dry-run/rollback tổng thể cần tiếp tục tích hợp.


## Bản rà soát A — reviewfix 1

Đã bổ sung kiểm tra SSH còn sống, kết nối lại khi phiên cũ đã chết,
giữ nguyên lỗi ban đầu khi cleanup thất bại, phát hiện thêm lỗi CLI Cisco
và cô lập lỗi cấu trúc dữ liệu RAM/section. Có 22 unittest đã chạy đạt.

Gói bàn giao phải kèm .gitignore. Kết quả kiểm thử giả lập không thay thế
kiểm tra trên lab hoặc tích hợp B/C. Không thay đổi chữ ký phương thức.


Bắt đầu bàn giao B/C: đọc docs/HANDOFF_A.md.

---

## Bổ sung phần C: CLI / template / điều phối / báo cáo

Phần C đã được ghép mà không sửa mã Python A+B. Xem **`docs/HUONG_DAN_PHAN_C.md`**
để biết danh sách file thêm/sửa, các lệnh VS Code/PowerShell, kiểm thử offline
và quy trình thử SSH/backup/rollback trên lab. Điểm vào CLI: `python main.py --help`.
