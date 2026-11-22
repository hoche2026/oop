> Tài liệu gốc trước v2. Các thay đổi mới về verify/rollback/CLI được mô tả
> trong CAP_NHAT_V2.md; dùng hướng dẫn chạy CHAY_KIEM_THU_VA_CHUP_ANH.md.

# Giao tiếp phần A — thiết bị và inventory

## 1. Môi trường đã kiểm thử

- Python 3.12 trên Ubuntu Server 24.04.
- Netmiko 4.8.0, Paramiko 4.0.0.
- Cài thư viện theo requirements.txt.
- Thông tin xác thực đặt trong .env, không đưa lên Git.
- .env.example chỉ chứa tên biến và giá trị mẫu.

## 2. Lab hiện tại

| Tên | IP quản trị | Platform | Role | Lớp |
|---|---|---|---|---|
| R1 | 192.168.241.21 | cisco_ios | router | CiscoIOSDevice |
| R2 | 192.168.241.22 | cisco_ios | router | CiscoIOSDevice |
| SW1 | 192.168.241.23 | cisco_ios | switch | CiscoIOSSwitchDevice |
| MT1 | 192.168.241.24 | mikrotik_routeros | router | MikroTikDevice |

R1 FastEthernet1/0: 10.10.12.1/30.
R2 FastEthernet1/0: 10.10.12.2/30.

Các IP quản trị thuộc mạng VMware của máy dựng lab.
Máy thành viên khác không tự truy cập được nếu chưa có đường mạng phù hợp.

## 3. Inventory

DeviceInfo có các trường:

- name
- host
- port
- platform
- group
- role
- tags
- credential_profile

InventoryManager nhận đường dẫn file YAML.

Các phương thức:

- load(): trả list[DeviceInfo].
- add(info): thêm DeviceInfo.
- update(name, changes): cập nhật bằng dictionary.
- delete(name): xóa theo tên.
- filter(group=None, role=None, tag=None): lọc; các điều kiện kết hợp AND.

Lỗi dữ liệu hoặc thao tác inventory được báo bằng InventoryError.

## 4. Tạo đối tượng thiết bị

```python
from app.inventory import InventoryManager
from app.devices.factory import DeviceFactory

inventory = InventoryManager("inventory/devices.yaml")
info = inventory.load()[0]
device = DeviceFactory.create(info)
```

Factory chọn lớp theo platform và role.
Phần xử lý danh sách thiết bị gọi phương thức chung, không tự phân nhánh vendor.

## 5. Các phương thức chung

| Phương thức | Kết quả / hành vi |
|---|---|
| connect() | Mở kết nối; lỗi thì phát sinh ngoại lệ |
| disconnect() | Đóng kết nối |
| send_command(command) | Trả chuỗi đầu ra |
| get_facts() | Trả dictionary thông tin thiết bị |
| backup_config() | Trả cấu hình văn bản dạng str |
| create_restore_point() | Trả dữ liệu phục hồi dạng str |
| push_config(config_text) | Áp lệnh và trả dictionary kết quả |
| restore_config(point_text) | Thực hiện phục hồi và trả dictionary |
| verify_config(config_text, checks) | Trả VerificationResult |

Không coi một phương thức không phát sinh ngoại lệ là bằng chứng mọi
chức năng đều đã đạt. Cần đọc kết quả và xác minh sau thao tác.

## 6. Phân biệt cấu hình văn bản và bản phục hồi

backup_config():

- Cisco: đầu ra show running-config.
- MikroTik: /export terse, mặc định ẩn thông tin nhạy cảm.
- Dùng để xem cấu hình, lưu lịch sử và so sánh.
- Khi diff, cần xử lý các dòng thời gian/tiêu đề thay đổi.

create_restore_point():

- Cisco: cấu hình văn bản.
- MikroTik: chuỗi JSON chứa bản sao nhị phân mã hóa, metadata,
  dung lượng, SHA256 và binary_base64.
- Lưu nguyên chuỗi trả về, không sửa nội dung.
- Dùng chuỗi này làm đầu vào restore_config().
- Không dùng gói nhị phân MikroTik để diff cấu hình.
- Base64 không phải mã hóa; bản .backup bên trong được RouterOS mã hóa.

B chịu trách nhiệm lưu hai loại dữ liệu và liên kết chúng với phiên bản,
thiết bị, thời gian. Không chỉ lưu export rồi giả định có thể phục hồi MT1.

## 7. Gọi thiết bị chỉ để đọc

```python
device = DeviceFactory.create(info)

try:
    device.connect()
    facts = device.get_facts()
    config_text = device.backup_config()
finally:
    device.disconnect()
```

Mỗi tác vụ hoặc worker dùng một đối tượng/kết nối riêng.
Không chia sẻ một kết nối SSH giữa các luồng.

## 8. Đẩy cấu hình và khôi phục

Cisco:

- push_config() chưa lưu startup-config.
- restore_config() sử dụng configure replace.
- Router dùng disk0:, switch IOL đã thử dùng unix:.
- Kiểm tra kết quả trước khi lưu startup-config.

MikroTik:

- push_config() nhận mỗi dòng một lệnh đầy đủ bắt đầu bằng /.
- Chưa hỗ trợ script nhiều dòng.
- Thay đổi cấu hình được RouterOS tự lưu.
- restore_config() chỉ nhận gói từ create_restore_point().
- Bản phục hồi phải khớp tên thiết bị, IP quản trị, hostname và phiên bản.
- Khôi phục sẽ reboot, sau đó chương trình chờ SSH trở lại.
- Cần biến <PROFILE>_BACKUP_PASSWORD đúng với bản sao.
- Đổi mật khẩu bản sao có thể ảnh hưởng việc khôi phục các phiên bản cũ.

Kết quả restore của Cisco và MikroTik hiện khác nhau.
Không truy cập một khóa như restored cho mọi nền tảng.

Sau restore phải gọi verify_config() và kiểm tra thêm điều kiện nghiệp vụ.
post_checks_required=True nghĩa là chưa hoàn thành xác minh nghiệp vụ.

## 9. VerificationResult

Có ba thuộc tính:

- passed: bool
- details: list[str]
- checks: dict[str, bool]

checks đầu vào hỗ trợ:

```python
checks = {
    "interfaces": {
        "TEN_CONG": {
            "ip_address": "IP_KY_VONG",
            "status": "up",
            "protocol": "up",
        },
    },
    "ping": {
        "target": "IP_DICH",
        "source": "IP_NGUON",
        "min_success_percent": 100,
    },
}
```

Có thể chỉ kiểm tra interfaces hoặc ping.
Địa chỉ ping hiện giới hạn IPv4.

verify_config() hiện kiểm tra các điều kiện trong checks.
Không tự chứng minh toàn bộ config_text đã được áp dụng chính xác.
Kịch bản cần kiểm tra VLAN, OSPF hoặc ACL phải bổ sung điều kiện tương ứng.

## 10. Dữ liệu facts

Các trường cơ bản đã dùng chung:

- schema_version
- device_name
- management_ip
- platform
- collected_at
- hostname
- os_version
- uptime
- hardware
- serial_numbers
- interfaces

Mỗi interface có name, ip_address, status, protocol.
MikroTik còn có ip_addresses để giữ danh sách địa chỉ kèm prefix.

Các mục thu thập bổ sung dùng cấu trúc:

```python
{
    "status": "ok",
    "data": ...,
    "error": None,
}
```

Trạng thái có thể là ok, empty, invalid hoặc error.
Mục không tồn tại không được tự coi là đã thu thập thành công.

Giới hạn hiện tại:

- CPU Cisco có thể bị đánh dấu invalid do số liệu mô phỏng bất nhất.
- serial_numbers của CHR hiện để trống, chưa thu thập.
- Phục hồi riêng cơ sở dữ liệu VLAN của IOL chưa được kiểm chứng.

## 11. Ngoại lệ và điều phối

Các ngoại lệ được định nghĩa trong app/contracts.py:

- InventoryError
- DeviceConnectionError
- DeviceCommandError
- BackupError
- RestoreError
- VerificationError

C bắt lỗi theo từng thiết bị, không để một thiết bị lỗi dừng toàn bộ danh sách.

Nếu push lỗi, một phần cấu hình có thể đã được áp dụng.
Nếu restore timeout hoặc mất SSH, trạng thái có thể chưa xác định;
không tự coi là thành công và không tự lặp thao tác phá vỡ trạng thái hiện tại.

## 12. Quy trình tích hợp dự kiến

1. Đọc và lọc inventory.
2. Tạo đối tượng bằng Factory, kết nối.
3. Thu thập trạng thái ban đầu.
4. Lấy cấu hình văn bản và tạo restore point.
5. B lưu bản sao thành công trước khi thay đổi.
6. C thực hiện dry-run hoặc áp cấu hình.
7. Xác minh các điều kiện sau thay đổi.
8. Nếu thất bại, C điều phối rollback từ restore point.
9. Xác minh lại theo trạng thái trước thay đổi.
10. Đóng kết nối và tổng hợp kết quả.

push_config() tự nó chưa có dry-run hoặc tự động rollback.
B/C phải tích hợp quy trình trên; chưa được coi các chức năng đó đã hoàn thành.

## 13. Phạm vi phần A

Đã kiểm chứng trên lab:

- Inventory CRUD và lọc.
- Kết nối, thu thập và lấy cấu hình trên bốn thiết bị.
- Đẩy cấu hình và xác minh trên Cisco/MikroTik.
- Khôi phục R1/R2 bằng cấu hình văn bản.
- Khôi phục running-config SW1 qua mô tả cổng.
- Khôi phục MT1 bằng backup nhị phân, reboot và kết nối lại.
- Từ chối các bản sao lỗi đã có trong chương trình demo.

Còn cần hoàn thiện:

- Chuẩn hóa tiếp các trường dữ liệu chi tiết.
- Tiếp tục kiểm thử tích hợp B/C; kiểm thử giả lập lỗi kết nối đã có.
- Chọn ảnh minh chứng và tích hợp theo docs/HANDOFF_A.md; README và gói A đã có.
- Phối hợp C thực hiện kịch bản mạng tự động theo đề bài.


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
