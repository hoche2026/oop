# Network Backup System

Hệ thống dòng lệnh dùng Python để quản lý thiết bị, sao lưu phiên bản và
khôi phục cấu hình mạng tập trung. Chương trình hỗ trợ Cisco IOS router,
switch Cisco IOS/IOL và MikroTik RouterOS qua SSH.

Người sử dụng có thể chọn một thiết bị hoặc một nhóm, thu thập thông tin,
lưu bản sao, so sánh với phiên bản trước, phát hiện thay đổi và phục hồi khi
cần. Dữ liệu được lưu thành file và metadata SQLite; kết quả tác vụ được
xuất ra JSON/CSV và ghi nhật ký.

## 1. Chức năng

- Đọc inventory YAML; thêm, sửa, xóa và lọc theo nhóm, vai trò, tag.
- Kết nối nhiều thiết bị đồng thời, mỗi worker có phiên SSH riêng.
- Thu thập thông tin hệ điều hành, cổng, route, ARP, láng giềng, CPU/RAM;
  switch có thêm VLAN và MAC. Trạng thái dữ liệu được giữ khi thiếu hoặc lỗi.
- Sao lưu cấu hình theo yêu cầu hoặc lịch interval; quản lý phiên bản và SHA256.
- So sánh hai phiên bản, chọn baseline và phát hiện sai lệch cấu hình.
- Khôi phục từ bản được chọn, tạo bản sao trước thao tác và xác minh kết quả.
- Render Jinja2, dry-run, áp cấu hình và rollback khi áp/xác minh thất bại.
- Thực nghiệm OSPF tự động trên hai router, kiểm tra neighbor, route và ping.
- Xuất báo cáo JSON/CSV và nhật ký có thời gian, người thực hiện, tác vụ/kết quả.

## 2. Cách hoạt động

1. Inventory cung cấp tên, IP, nền tảng và profile xác thực của thiết bị.
2. DeviceFactory tạo lớp thiết bị phù hợp; TaskRunner mở/đóng SSH cho từng tác vụ.
3. Dịch vụ nghiệp vụ gọi các phương thức chung của thiết bị để đọc, sao lưu,
   cấu hình hoặc phục hồi, thay vì dùng một lệnh chung cho mọi hãng.
4. BackupStorage lưu cấu hình văn bản và dữ liệu phục hồi riêng, liên kết cùng
   phiên bản trong SQLite. Cấu hình văn bản phục vụ diff; restore point dùng phục hồi.
5. Tác vụ trả trạng thái riêng từng thiết bị. Lỗi ở một thiết bị được tổng hợp
   vào kết quả; chương trình tiếp tục xử lý các thiết bị khác trong lượt chạy.

Cisco khôi phục running-config bằng configure replace. MikroTik phục hồi từ
native backup mã hóa, có reboot và chờ SSH trở lại. Export văn bản MikroTik
không thay thế cho native backup. Sau phục hồi, chương trình kiểm tra các
điều kiện đã yêu cầu; không coi việc lệnh trả về là bằng chứng đủ.

## 3. Cấu trúc gói

| Đường dẫn | Nội dung |
|---|---|
| `README.md` | Giới thiệu và hướng dẫn cài đặt, cấu hình, sử dụng |
| `source-code/network-backup-ABC-v2/network-backup-system/` | Thư mục chương trình chứa `main.py` |
| `docs/` | Tài liệu thiết kế và tài liệu mô tả hệ thống |
| `demo/` | Ảnh/video minh chứng nếu được bổ sung vào gói |

Trong thư mục chương trình:

| Đường dẫn | Nội dung |
|---|---|
| `main.py` | Điểm vào CLI |
| `app/devices/` | Lớp thiết bị trừu tượng, Factory và triển khai Cisco/MikroTik |
| `app/inventory.py` | Quản lý inventory |
| `app/backup.py`, `app/storage.py`, `app/scheduler.py` | Sao lưu, lưu trữ và lịch chạy |
| `app/config_service.py`, `app/runner.py` | Sinh/áp cấu hình và điều phối |
| `app/verification.py`, `app/comparison.py` | Xác minh và chuẩn hóa khi đối chiếu |
| `app/reporting.py`, `app/logging_setup.py` | Báo cáo và nhật ký |
| `inventory/devices.yaml` | Danh sách thiết bị |
| `.env.example` | Mẫu cấu hình xác thực |
| `templates/`, `config/` | Template, biến, checks và lịch mẫu |
| `samples/` | Dữ liệu giả minh họa, không phải kết quả thực nghiệm |
| `tests/` | Kiểm thử tự động với dữ liệu/thiết bị giả |

Các đường dẫn `app/`, `config/`, `data/` ở những phần sau được tính từ thư mục
chứa `main.py`. Tên thư mục cha có thể thay đổi; không cần dùng cùng tên user
hay đường dẫn tuyệt đối với máy đã thực nghiệm.

## 4. Yêu cầu môi trường

### Chạy chương trình và kiểm thử logic

- Python 3.12 là phiên bản đã được kiểm thử.
- Ubuntu Server 24.04 hoặc Windows có Python tương ứng.
- Tạo môi trường ảo riêng và cài thư viện từ `requirements.txt`.
- CLI inventory, dry-run và unittest chạy được khi chưa có thiết bị/SSH thật.

### Thực hiện tác vụ trên thiết bị

- Thiết bị thật hoặc mô phỏng bằng EVE-NG có IP quản trị và dịch vụ SSH.
- Máy chạy Python truy cập được IP/port SSH của thiết bị.
- Tài khoản có quyền đọc/cấu hình tương ứng; Cisco cần enable secret khi dùng.
- Chấp nhận đúng host key trên cùng máy và tài khoản hệ điều hành chạy Python.
- Có console dự phòng khi thử thay đổi hoặc khôi phục cấu hình.

VM/image thiết bị không được kèm trong gói mã nguồn. Một bố trí thực nghiệm
là VM EVE-NG chạy thiết bị và một VM Ubuntu chạy chương trình; máy khác có
đường mạng tới thiết bị cũng có thể chạy CLI.

## 5. Cài đặt

### 5.1. Mở thư mục chương trình

README này nằm cùng main.py và requirements.txt. Mở terminal tại thư mục
này rồi tiếp tục bước 5.2. Nếu đang ở thư mục ngoài cùng của gói, vào
source-code/network-backup-ABC-v2/network-backup-system trước khi chạy lệnh.
Tất cả lệnh sử dụng bên dưới được chạy tại thư mục có main.py.

### 5.2. Ubuntu hoặc Linux

Nếu Python/venv/pip chưa có, cài các gói hệ thống phù hợp, ví dụ trên Ubuntu:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

Tạo môi trường và cài thư viện:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
```

Kỳ vọng `No broken requirements found`. Trong terminal mới, kích hoạt lại
bằng `source .venv/bin/activate`; không tạo lại venv mỗi lần mở chương trình.

### 5.3. Windows PowerShell

Cài Python 3.12 rồi chạy tại thư mục chương trình:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Trong các lệnh `python ...` ở phần sau, người dùng Windows có thể thay
`python` bằng `.\.venv\Scripts\python.exe`. Không sao chép môi trường ảo
đã tạo trên một hệ điều hành sang hệ điều hành khác.

## 6. Cấu hình

### 6.1. Inventory

Chỉnh `inventory/devices.yaml` theo thiết bị thực tế. Ví dụ một bản ghi:

```yaml
devices:
  - name: R1
    host: 192.168.241.21
    port: 22
    platform: cisco_ios
    group: lab
    role: router
    tags: [core]
    credential_profile: LAB
```

`platform` hỗ trợ `cisco_ios` và `mikrotik_routeros`. Với Cisco, `role: switch`
chọn lớp switch có thu thập VLAN/MAC; router dùng `role: router`.
Tên phải duy nhất, IP/port hợp lệ. Profile LAB liên kết tới các biến LAB_*
trong phần xác thực dưới đây. Có thể dùng profile khác và đặt tên biến cùng
prefix tương ứng.

Inventory đi kèm mô tả môi trường thực nghiệm:

| Thiết bị | Nền tảng | IP quản trị |
|---|---|---|
| R1 | Cisco IOS router | 192.168.241.21 |
| R2 | Cisco IOS router | 192.168.241.22 |
| SW1 | Cisco IOL L2 | 192.168.241.23 |
| MT1 | MikroTik CHR | 192.168.241.24 |

Đây là IP mẫu trong mạng quản trị lab, không mặc nhiên truy cập được từ máy
khác. Cần chỉnh inventory khi sử dụng môi trường khác. Kịch bản OSPF ở mục
9 có yêu cầu topology riêng ngoài IP quản trị này.

### 6.2. Xác thực

Tạo `.env` khi chưa có. Trên Ubuntu/Linux:

```bash
cp -n .env.example .env
chmod 600 .env
nano .env
```

Trên Windows, sao chép `.env.example` thành `.env` bằng File Explorer hoặc
PowerShell khi chưa có file này. Điền giá trị thật trên máy chạy:

```dotenv
LAB_USERNAME=YOUR_SSH_USERNAME
LAB_PASSWORD=YOUR_SSH_PASSWORD
LAB_SECRET=YOUR_CISCO_ENABLE_SECRET
LAB_BACKUP_PASSWORD=YOUR_NATIVE_BACKUP_PASSWORD
```

Các giá trị `YOUR_...`/`CHANGE_ME` là placeholder, không dùng để đăng nhập.
LAB_BACKUP_PASSWORD dùng mã hóa/khôi phục native backup MikroTik; mật khẩu
phải khớp bản đã lưu. `.env` nằm cùng `main.py`; biến môi trường có sẵn được
ưu tiên hơn giá trị trong file.

Không đưa `.env`, mật khẩu, khóa hoặc backup thật lên kho mã nguồn. Trên
Windows quản lý quyền bằng NTFS ACL. Quyền file không thay thế mã hóa.

### 6.3. SSH host key

Trên cùng máy và user chạy Python, kết nối SSH thủ công lần đầu để xác minh
đúng danh tính và nhận host key của thiết bị. Ví dụ:

```bash
ssh netadmin@192.168.241.24
```

Một số image Cisco IOS cũ trong lab cần tùy chọn tương thích:

```bash
ssh -oKexAlgorithms=+diffie-hellman-group14-sha1 -oHostKeyAlgorithms=+ssh-rsa -oCiphers=+aes128-cbc netadmin@192.168.241.21
```

Nhận khóa riêng cho từng IP .21/.22/.23 nếu cần. Các thuật toán cũ này chỉ
phục vụ image lab tương ứng, không phải khuyến nghị cho hạ tầng production.
Không tắt kiểm tra host key để vượt lỗi kết nối.

## 7. Kiểm tra cài đặt và xem trợ giúp

```bash
python main.py --help
python main.py inventory
python -m unittest discover -s tests -v
```

Bộ kiểm thử hiện có 105 test; tổng kết mong đợi là `OK`. Các ca cố ý gây lỗi
có thể ghi `task_failed`; đọc kết luận cuối thay vì coi mọi dòng log lỗi là
một kiểm thử thất bại. Unittest sử dụng thiết bị/I/O giả, không thay nghiệm
thu kết nối và cấu hình trên lab thật.

Xem trước template mà chưa kết nối thiết bị:

```bash
python main.py dry-run --devices R1 --template cisco_interface.j2 --vars config/variables.example.yaml
```

Dry-run kiểm tra biến và các quy tắc lệnh cơ bản; không mô phỏng toàn bộ
cú pháp hoặc hành vi của hệ điều hành thiết bị.

## 8. Sử dụng các chức năng chính

Tùy chọn chung đặt trước tác vụ:

- `--summary`: hiển thị bảng ngắn trên terminal; báo cáo vẫn giữ chi tiết.
- `--report json` hoặc `--report csv`: chọn định dạng báo cáo, mặc định JSON.
- `--workers 4`: số worker; điều chỉnh theo tài nguyên và khả năng thiết bị.
- `--inventory DUONG_DAN`: chọn inventory khác.

### 8.1. Inventory và thu thập

```bash
python main.py inventory --role switch
python main.py --summary facts --group lab
python main.py --summary --report csv facts --devices R1 R2 SW1 MT1
```

Có thể lọc bằng `--group`, `--role`, `--tag`. CLI facts dùng dữ liệu chuẩn
hóa và giữ status của từng mục; task đọc xong không có nghĩa mọi chỉ số
CPU/RAM đều hợp lệ.

CRUD có mẫu file tại `config/device.example.yaml`. Khi thêm thiết bị thật,
đổi tên/IP trong file trước; thao tác này sửa inventory:

```bash
python main.py inventory-add --file config/device.example.yaml
python main.py inventory-update --device R3 --file config/device.example.yaml
python main.py inventory-delete --device R3 --confirm
```

File update là mapping các trường cần cập nhật. Có thể dùng demo CRUD trên
bản sao tạm để kiểm tra mà không sửa inventory thật:

```bash
python demo_inventory_crud.py
```

### 8.2. Sao lưu và phiên bản

```bash
python main.py --summary backup --devices R1 R2 SW1 MT1
python main.py list --device R1
```

Kết quả backup có ID dùng để tra phiên bản, diff và restore. Sao lưu không
sửa running-config nhưng có tạo file native backup trên MikroTik.

Để có hai phiên bản của R1, chạy backup R1 ở hai thời điểm rồi dùng `list`.
Các số ID trong ví dụ sau chỉ minh họa: thay bằng ID thực cùng thiết bị và
platform; không mặc định hai ID liên tiếp thuộc cùng router.

```bash
python main.py diff 1 5
python main.py baseline --device R1 --backup-id 1
python main.py --summary check --devices R1
```

`baseline` chọn bản chuẩn. `check` báo cấu hình hiện tại có khác baseline
hay không; chưa có baseline sẽ báo lỗi. Diff trực tiếp mặc định che các dòng
nhạy cảm phổ biến; `--raw` hiển thị nguyên nội dung để xem riêng trên máy
quản trị. Báo cáo tự động không chứa diff/preview thô. File backup gốc được
giữ nguyên, chỉ bản dùng so sánh được chuẩn hóa header/phân cách IOS.

### 8.3. Khôi phục một phiên bản

Dùng ID bản sao đúng thiết bị. Ví dụ dưới vẫn dùng ID minh họa 1:

```bash
python main.py --report json restore --device R1 --backup-id 1 --checks config/checks.restore.example.yaml --confirm
```

Trình tự: kiểm tra đúng thiết bị/platform và toàn vẹn file, lưu bản cứu hộ
trước thao tác, phục hồi, rồi xác minh theo checks. Mẫu checks.restore dùng
config_match để đối chiếu running-config với cấu hình của bản được chọn.
Nó không chứng minh mọi trạng thái động hoặc startup-config đã khớp.

MikroTik restore có reboot. Khi timeout hoặc chưa xác minh được trạng thái,
kiểm tra console/báo cáo trước khi quyết định thao tác tiếp, không lặp
restore liên tục. ID bản cứu hộ được giữ trong kết quả lỗi khi đã tạo được.

### 8.4. Template và áp cấu hình

Ví dụ template Cisco thay description cổng trong lab:

```bash
python main.py dry-run --devices R1 --template cisco_interface.j2 --vars config/variables.example.yaml
python main.py --report json apply --devices R1 --template cisco_interface.j2 --vars config/variables.example.yaml --checks config/checks.example.yaml --confirm
```

Checks phải kiểm tra đúng nội dung thay đổi. Ví dụ đổi description cần
interface_descriptions, không chỉ kiểm tra cổng vốn đang up/up. Biến/checks
có thể dùng chung hoặc tách theo `{devices: {R1: {...}, R2: {...}}}`.

Khi push/verify lỗi, dịch vụ gọi phục hồi bản trước một lần, đối chiếu lại
running-config và trả trạng thái rollback riêng. Task áp cấu hình gốc vẫn
`failed` dù rollback đã đạt. `rollback_verified` chỉ có phạm vi được ghi
trong kết quả, không đồng nghĩa toàn bộ mạng đã hội tụ.

### 8.5. Sao lưu theo lịch

```bash
python main.py --report json scheduler --schedule config/schedule.example.yaml
```

Sửa interval trong file lịch theo nhu cầu; `config/schedule.lab.yaml` có
khoảng 15 giây để thử. Lượt đầu sau một interval, không chạy ngay lúc mở.
Ctrl+C ngừng gửi việc mới và chờ việc đang chạy kết thúc. Mỗi lượt có báo
cáo riêng; xem thêm lịch sử bằng `list` và nhật ký.

Scheduler hoạt động khi tiến trình còn sống; chưa cài service hệ điều hành.
Khóa endpoint chỉ trong cùng tiến trình, không điều phối nhiều tiến trình
độc lập. Tránh chạy các chương trình cấu hình cùng thiết bị đồng thời.

## 9. Kịch bản OSPF trên hai router

Kịch bản đi kèm dành cho hai Cisco IOS router tên R1/R2, role router:

| Thành phần | R1 | R2 |
|---|---|---|
| Link trực tiếp | FastEthernet1/0 | FastEthernet1/0 |
| IP link | 10.10.12.1/30 | 10.10.12.2/30 |
| Loopback tạo thử | Loopback101 | Loopback101 |
| IP loopback/router ID | 10.255.1.1 | 10.255.2.2 |
| OSPF process và area | 10, area 0 | 10, area 0 |

Chỉ dùng khi topology và tài nguyên trên phù hợp. Nếu process 10 hoặc
Loopback101 đã tồn tại, chương trình từ chối ghi đè. Muốn dùng topology khác
cần điều chỉnh kế hoạch trong app/ospf_lab.py và template/checks tương ứng;
đổi IP inventory đơn thuần không biến kịch bản này thành OSPF tổng quát.

```bash
python main.py ospf dry-run
python main.py --summary ospf apply --confirm
python main.py ospf verify
python main.py ospf restore --confirm
```

Chạy tuần tự, đợi mỗi bước hoàn tất. Apply lưu bản trước của cả hai router và
state cứu hộ, push cả hai rồi mới đợi hội tụ. Verify kiểm tra neighbor FULL,
route OSPF và ping loopback. Nếu apply/verify lỗi, chương trình thử phục hồi
cả hai và giữ kết quả lỗi của tác vụ gốc.

`ospf restore` đưa cả hai về cấu hình trước kịch bản, kiểm tra config_match
và đóng state khi cả hai đạt. Giữ `data/ospf_state.json` và backups cho đến
khi hoàn tất phục hồi. Nếu restore đã chạy nhưng còn state, có thể dùng
`python verify_ospf_restore.py` để chỉ đọc/đối chiếu lại; chỉ dùng khi state
còn tồn tại. Cisco không tự save startup-config trong bài thử.

## 10. Dữ liệu và kết quả đầu ra

Các thư mục này được tạo trong thư mục có main.py:

| Đường dẫn | Nội dung |
|---|---|
| `data/app.db` | Metadata backup, restore point và baseline |
| `backups/TEN_THIET_BI/*.cfg` | Cấu hình văn bản để lưu phiên bản/diff |
| `backups/TEN_THIET_BI/*.restore` | Dữ liệu phục hồi gắn với phiên bản |
| `data/ospf_state.json` | ID bản trước và endpoint của bài thử OSPF |
| `logs/operations.log` | Nhật ký thực thi và actor; có xoay file |
| `reports/*.json`, `reports/*.csv` | Kết quả tác vụ và các lượt scheduler |
| `.local_backups/` | Bản cứu hộ của một số chương trình demo |

Kết quả từng thiết bị có task, status, thời gian bắt đầu, duration_seconds,
data và error. Mã thoát CLI: 0 khi lượt hoàn tất thành công, 1 khi có kết quả
thiết bị thất bại, 2 khi có lỗi đầu vào/khởi tạo không xử lý ở từng thiết bị.
Bài thử cố ý gây lỗi có thể trả 1 theo kịch bản, không phải mọi exit 1 đều
là lỗi bất ngờ.

File dữ liệu nhạy cảm được tạo với quyền riêng tư trên POSIX. Backup Cisco
không được mã hóa chỉ nhờ chmod; người quản trị vẫn phải bảo vệ nơi lưu.
Không công khai .env, native backup, restore point hoặc config/report thô
chưa rà nội dung.

## 11. Kiểm thử và chương trình mẫu

```bash
python -m unittest discover -s tests -v
python demo_all_devices.py
python demo_release_lab.py --confirm
python demo_mikrotik_restore.py
```

- Unittest kiểm tra logic/I/O giả, không thay đổi thiết bị thật.
- demo_all_devices thu thập thông tin bốn thiết bị đã cấu hình trong inventory.
- demo_release_lab thay thử description R1, kiểm tra diff/baseline rồi restore.
- demo_mikrotik_restore tạo bridge thử, nạp bản native và reboot MT1.

Hai demo cuối có thay đổi thiết bị. Chỉ chạy trong lab quản lý được và giữ
console dự phòng. Đo thời gian/độ chính xác dùng `benchmark.py` theo tài liệu
DO_THOI_GIAN; chương trình không cung cấp số đo minh họa để coi là số liệu thật.

## 12. Xử lý lỗi thường gặp

| Hiện tượng | Kiểm tra |
|---|---|
| Thiếu thư viện | Dùng đúng Python trong .venv, cài requirements và chạy pip check |
| Không đọc được inventory | Kiểm tra đường dẫn, YAML và đủ trường hợp lệ |
| Thiếu xác thực/đăng nhập lỗi | Kiểm tra profile, biến môi trường và .env; không in mật khẩu |
| SSH timeout | IP/port, route, VM/thiết bị đang chạy, dịch vụ SSH và firewall |
| Host key không được chấp nhận | Xác minh đúng khóa trên cùng máy/user, không tắt kiểm tra |
| Chưa có baseline | Tạo backup, lấy ID từ list rồi chọn baseline đúng thiết bị |
| Backup mất hoặc sai hash | Giữ dấu vết lỗi, dùng bản toàn vẹn khác; không sửa hash để bỏ qua |
| VerificationError | Xem checks/báo cáo, phân biệt dữ liệu chưa thu được với giá trị sai |
| OSPF chưa FULL | Kiểm tra link/IP/topology và trạng thái hai router; xem báo cáo từng pha |
| Có state OSPF | Dùng verify/restore theo trạng thái; không xóa state để cố apply lại |

## 13. Giới hạn và tài liệu thêm

CPU trên router mô phỏng có thể trả dữ liệu không nhất quán và được đánh dấu
invalid, không ép thành 0. CHR chưa thu thập serial phần cứng; uptime còn là
chuỗi theo vendor. Khôi phục riêng VLAN database IOL chưa được kiểm chứng.
Config-match là đối chiếu văn bản đã chuẩn hóa, không phải kiểm chứng mọi
trạng thái mạng hay cấu hình khởi động. Kịch bản OSPF mẫu chỉ áp dụng topology
đã nêu; lịch chạy chưa có khóa liên tiến trình hoặc mốc bền qua restart.

Tài liệu thiết kế tại `docs/THIET_KE.md`, hướng dẫn đo tại
`docs/DO_THOI_GIAN.md`. Thư mục docs của mã nguồn có thêm API thiết bị và
hướng dẫn kịch bản chi tiết. Tài liệu lịch sử không thay mô tả sử dụng hiện
tại trong README này.
