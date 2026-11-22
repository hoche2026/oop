# Bàn giao phần B — lưu trữ và nghiệp vụ sao lưu

## Phạm vi đã làm

- `app/storage.py`: `BackupStorage` và `BackupRecord`.
- `app/backup.py`: `BackupService` theo hợp đồng A/B/C.
- `tests/test_storage.py`: kiểm thử offline, không kết nối hoặc sửa thiết bị.
- `tests/test_backup.py`: kiểm thử nghiệp vụ với thiết bị giả lập.
- Đã triển khai diff, baseline, phát hiện sai lệch và luồng restore.
- Đã bổ sung `app/scheduler.py`, `config/schedule.example.yaml` và
  `tests/test_scheduler.py`; sau sửa hai P2 đã chạy đạt toàn bộ 70 unittest,
  gồm 21 bài BackupService và 16 bài scheduler.
- Chưa kiểm thử tích hợp B với TaskRunner thật của C hoặc lab thật.

`BackupRecord` có đúng sáu trường theo phân công: backup_id, device_name,
platform, created_at, file_path và sha256. Hiện lớp này nằm trong module do B
quản lý; chưa sửa file dùng chung `app/contracts.py`.

## API lưu trữ

| Phương thức | Kết quả |
|---|---|
| `BackupStorage(project_dir=None)` | Khởi tạo schema tại `data/app.db`; mặc định dùng thư mục dự án |
| `save_backup(device_name, platform, config_text, restore_point)` | `BackupRecord` |
| `get_backup(backup_id)` | `BackupRecord`, không đọc file |
| `list_backups(device_name)` | Danh sách metadata, mới nhất trước |
| `read_backup(backup_id)` | Chuỗi cấu hình, đã kiểm tra SHA256 |
| `read_restore_point(backup_id)` | Chuỗi phục hồi nguyên bản, đã kiểm tra SHA256 |
| `set_baseline(device_name, backup_id)` | Kiểm tra sở hữu/toàn vẹn rồi lưu tham chiếu |
| `get_baseline(device_name)` | Metadata baseline; chưa có thì phát sinh `BackupError` |

Đây là API nội bộ tầng lưu trữ. C dùng `BackupService` ở phần dưới.

## API BackupService dành cho C

Khởi tạo `BackupService(storage=None)`. Không truyền storage thì dùng
`BackupStorage()` tại thư mục dự án. Có thể truyền kho riêng khi kiểm thử.

| Phương thức | Kết quả |
|---|---|
| `create_backup(device)` | BackupRecord; đã lưu văn bản và restore point |
| `list_backups(device_name)` | Danh sách BackupRecord mới nhất trước |
| `read_backup(backup_id)` | Văn bản cấu hình đã kiểm tra hash |
| `compare(first_id, second_id)` | Unified diff; giống nhau trả chuỗi rỗng |
| `set_baseline(device_name, backup_id)` | Không trả dữ liệu |
| `check_changes(device)` | Dictionary device, baseline_id, changed, diff |
| `restore(device, backup_id, checks)` | Dictionary kết quả có pre_backup_id |

Ví dụ tích hợp (device đã được C kết nối, checks theo API của A):

```python
from app.backup import BackupService

service = BackupService()
record = service.create_backup(device)
service.set_baseline(device.name, record.backup_id)
changes = service.check_changes(device)
# Chỉ gọi khi cần khôi phục trên lab đã chuẩn bị:
# result = service.restore(device, record.backup_id, checks)
```

Không tự connect/disconnect trong B. Để đọc platform qua API công khai của
A, service gọi `get_normalized_facts()`; không truy cập thuộc tính `_info`.
Việc này có chi phí thu thập facts, cần tính vào thời gian tác vụ thực tế.

Diff chỉ chuẩn hóa CRLF/LF và bỏ khác biệt newline cuối văn bản. Các dòng
timestamp, tiêu đề, comment, khoảng trắng và lệnh được giữ trong so sánh.
Chưa có bộ lọc dòng biến động; nếu cần bổ sung phải ghi rõ quy tắc.
So sánh từ chối phiên bản khác thiết bị/platform. Chưa có baseline thì báo lỗi.
`check_changes()` không tạo thêm restore point trên thiết bị.

Restore kiểm tra thiết bị/platform, đọc và xác minh cả hai file, kiểm tra
checks bằng `verify_config()` của A trên trạng thái hiện tại, rồi mới tạo
bản sao trước thao tác và gọi `restore_config(point_text)`. Kết quả precheck
passed=False không chặn restore vì trạng thái hiện tại có thể đang sai;
ngoại lệ hoặc kết quả xác minh không hợp lệ sẽ chặn thao tác. Sau restore
phải gọi verify lần nữa và yêu cầu passed=True với checks không rỗng.

Sau sửa P2, cả precheck và verify sau restore đều đối chiếu độ bao phủ:
`ping` nếu yêu cầu ping, và `<interface>.<field>` cho từng trường interface
theo đúng kết quả API A hiện có. Thiếu tiêu chí phát sinh VerificationError,
kèm verification, stage và pre_backup_id (None nếu chưa tạo bản sao).
Không thay đổi chữ ký công khai hay schema A/B/C.

Khi A trả `interfaces_collection=False`, các tiêu chí interface được ghi
nhận là đã thử nhưng không thu thập được. Precheck vẫn được phép passed=False
để phục hồi trạng thái đang lỗi; sau restore passed=False luôn làm tác vụ
thất bại. Cờ `interfaces_collection=True` không thay được các trường thiếu.

Kết quả thành công có device, backup_id, pre_backup_id, restored,
verification và restore_result (giữ nguyên dictionary của A). Cần đọc
verification; kết quả thô của A có thể vẫn có post_checks_required=True.
Xác minh này chỉ chứng minh hậu điều kiện A hỗ trợ, không chứng minh toàn
bộ cấu hình đã giống bản sao.

Khi lỗi, service phát sinh RestoreError hoặc VerificationError. Ngoại lệ
có thuộc tính `pre_backup_id` (None nếu chưa lưu được bản sao), `backup_id`
và `stage` (validate/precheck/pre_backup/restore/verify). Nếu verify trả
passed=False, ngoại lệ còn có `verification` dạng dictionary. C nên đưa
các trường này vào data của tác vụ thất bại để giữ dấu vết cứu hộ. B không
tự retry hoặc rollback khi chính restore/verify thất bại.

## Dữ liệu và quan hệ với A

- File `.cfg`: nguyên văn `device.backup_config()`, phục vụ diff/baseline.
- File `.restore`: nguyên văn `device.create_restore_point()`, phục vụ restore.
- Hai file liên kết bằng backup_id trong bảng `backups` và `restore_points`.
- Bảng `baselines` chỉ tham chiếu backup_id, không ghi đè phiên bản cũ.
- Chuỗi UTF-8 được ghi bằng bytes để giữ cả xuống dòng CRLF/LF nguyên bản.
- Thời gian ISO 8601 dùng UTC có múi giờ; tên file có microsecond và UUID.
- Không phân nhánh vendor trong tầng lưu trữ. Export MikroTik và gói phục hồi
  nhị phân JSON của A được lưu riêng, không thay thế cho nhau.

Mỗi thao tác dùng connection SQLite riêng, timeout ghi 30 giây, bật foreign
keys; database dùng WAL. Hai file được ghi trước transaction metadata. Khi
ghi file hoặc transaction thất bại, dọn các file vừa tạo và không công bố bản
sao. Nếu tiến trình bị tắt đột ngột giữa lúc ghi và commit, có thể còn file
mồ côi; chưa có chức năng tự dọn hoặc bảo đảm giao dịch nguyên tử giữa filesystem
và SQLite. Nếu file bị xóa/sửa sau commit, việc đọc sẽ báo `BackupError`.

## Chạy kiểm thử trên Windows

Tại thư mục dự án, dùng môi trường Python 3.12 đã cài:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_storage.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_backup.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_scheduler.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Kiểm thử dùng thư mục tạm trong dự án rồi tự dọn. Các trường hợp gồm: lưu/đọc
Unicode và xuống dòng nguyên bản, mở lại DB, nhiều phiên bản, baseline khác
thiết bị, thiếu bản sao, file mất/sai hash, đường dẫn vượt thư mục dự án,
lỗi ghi file, rollback transaction và 24 lượt ghi qua 8 worker.

Kết quả lần chạy trước ngày 10/11/2026 trên Windows, Python 3.12.10: toàn bộ 49 bài
unittest đạt, gồm 22 bài của A, 11 bài storage và 16 bài BackupService.
Các kiểm thử nghiệp vụ gồm sai lệch/baseline, diff, lỗi thu thập, bản sao
khác thiết bị/platform, restore point lỗi, kiểm tra trước thao tác, lỗi lưu
bản sao cứu hộ, lỗi restore, verify thất bại và kết quả verify thiếu/không
nhất quán. Tất cả đều offline, không có thao tác với lab thật.

Phiên CLI viết scheduler ngày 10/11/2026 báo không truy cập được Python
gốc và dừng trước khi thu thập kiểm thử. Đây là lỗi quan sát trong phiên
đó; chưa xác định nguyên nhân khác biệt về môi trường/quyền truy cập.

Kiểm tra lại sau đó cùng ngày: Python gốc và `.venv` đều chạy được với
Python 3.12.10, không phải cài lại hoặc tạo lại môi trường. Đã chạy:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Kết quả trước lượt sửa P2: `No broken requirements found` và **65/65 bài
unittest đạt**, gồm 22 bài A, 11 storage, 16 BackupService và 16 scheduler.
Kết quả này xác nhận code scheduler hiện tại bằng kiểm thử offline;
chưa xác nhận runner thật hoặc thiết bị thật. Khi phiên khác báo thiếu
Python, kiểm tra lại đường dẫn/quyền truy cập trước khi kết luận phải cài lại.

Lượt sửa hai P2 ngày 10/11/2026: đã bổ sung năm phương thức test hồi quy
trong `tests/test_backup.py`, sửa FakeDevice trả kết quả theo checks và thêm
source IPv4 giả hợp lệ vào fixture Cisco. Các ca mới kiểm tra thiếu ping,
trường hoặc interface ở precheck/sau restore; giữ ID và nội dung bản sao cứu
hộ khi lỗi sau restore; cờ collection không thay kết quả thiếu; verify_config
thật của Cisco với I/O giả cho ping/interfaces; thiếu source bị A từ chối;
lỗi thu thập interface trước/sau restore được xử lý đúng giai đoạn.

Phiên CLI sửa code bị chặn trước discovery với exit code 103. Trong lượt
kiểm chứng tiếp theo ngày 10/11/2026, đã chạy lại trên Python 3.12.10:
**70/70 unittest đạt, exit code 0** (22 A, 11 storage, 21 BackupService,
16 scheduler). `pip check` không phát hiện lỗi phụ thuộc. Cả năm bài hồi quy
mới đạt, xác nhận xử lý hai P2 trong phạm vi offline. Không cài lại Python
hoặc thay .venv. Mọi dữ liệu trong test là giả; không kết nối/push/restore
thiết bị thật. Chưa xác nhận tích hợp runner thật và lab.

## Scheduler và điểm nối dành cho C

Chưa có `main.py` hoặc TaskRunner trong bản mã nguồn đang mở. B nhận runner
qua constructor; không bổ sung hoặc thay đổi module C hay file dùng chung.

```yaml
schedules:
  - device: R1
    interval_seconds: 300
  - device: MT1
    interval_seconds: 900
```

Tên phải có trong `device_infos` do C truyền vào. Mỗi thiết bị chỉ có một
lịch; interval là số giây dương hữu hạn, chấp nhận số thập phân. Từ chối
bool, chuỗi số, NaN/infinity, tên sai, tên trùng, khóa lạ/khóa YAML trùng,
trường thiếu và danh sách rỗng. Đọc YAML bằng SafeLoader riêng, không ảnh
hưởng bộ đọc inventory của A. File ví dụ có bốn tên thiết bị trong lab;
kiểm tra inventory và chỉnh lịch trước khi dùng.

| API | Hành vi |
|---|---|
| `load_schedule(file_path)` | Tuple `ScheduleEntry(device, interval_seconds)`; lỗi đầu vào báo `BackupError` |
| `BackupScheduler(entries, device_infos, runner, backup_service, *, max_workers=4, clock=time.monotonic, logger=None)` | Kiểm tra tên với inventory; tạo pool riêng cho scheduler |
| `BackupScheduler.from_yaml(file_path, device_infos, runner, backup_service, **kwargs)` | Đọc lịch và khởi tạo |
| `run_pending()` | Gửi các lượt đến hạn, trả dict tên -> Future; không chờ SSH |
| `run_forever(poll_seconds=1.0)` | Vòng lặp trên luồng hiện tại, tự close khi dừng/Ctrl+C |
| `stop()` | Ngừng nhận lượt mới, đánh thức vòng lặp; không chặn chờ tác vụ |
| `close()` | Ngừng nhận lượt mới, hủy việc đang chờ trong pool, chờ việc đang chạy hoàn tất |

Ví dụ đoạn nối để C đặt trong nhánh chạy lịch của `main.py` sau khi đã
tạo `runner` theo triển khai của C (đây là hướng dẫn, chưa sửa main.py):

```python
from app.backup import BackupService
from app.inventory import InventoryManager
from app.scheduler import BackupScheduler

device_infos = InventoryManager("inventory/devices.yaml").load()
scheduler = BackupScheduler.from_yaml(
    "config/schedule.example.yaml", device_infos, runner, BackupService(),
)
try:
    scheduler.run_forever()
finally:
    scheduler.close()  # Gọi lặp được; đảm bảo dọn nếu lỗi bên ngoài vòng lặp.
```

C cần cấu hình logging theo hệ thống chung trước khi chạy. Scheduler dùng
logger `app.scheduler`, không tự thêm handler/file log. Log ghi tên thiết
bị, sự kiện gửi việc, bỏ lượt do đang bận, hoàn tất runner, lỗi backup hoặc
runner/submit (chỉ loại ngoại lệ, không in payload SSH hay cấu hình).

Mỗi lượt gọi đúng hợp đồng
`runner.run([device_info], "backup", task_callable)`. Task callable nhận
thiết bị đã kết nối và gọi `BackupService.create_backup(device)`, giữ nguyên
kết quả `BackupRecord` hoặc phát sinh ngoại lệ. C sở hữu tạo đối tượng,
connect/disconnect trong finally và tổng hợp kết quả. **Runner.run phải chờ
toàn bộ worker của lượt đó hoàn tất trước khi trả về**; nếu runner chỉ gửi
việc rồi trả về ngay thì scheduler không thể biết lúc nào thiết bị hết bận.
C cần bảo đảm runner dùng được từ nhiều luồng hoặc chọn `max_workers=1`.

`run_pending()` trả Future giữ nguyên kết quả/ngoại lệ của runner, không
chuẩn hóa schema kết quả C chưa có. Ví dụ sau khi đến hạn:
`futures["R1"].result()` trả nguyên kết quả `runner.run(...)`. Trong chế độ
thường trực, C/runner phải lưu báo cáo và log lỗi kết nối hoặc kết quả thất
bại mà runner đã bắt thành dữ liệu; thông báo runner hoàn tất không đồng
nghĩa backup thành công. Lỗi phát sinh từ task backup vẫn được B log trước
khi chuyển cho runner, kể cả khi runner bắt lỗi đó.

Quy tắc thời gian và dừng:

- Dùng đồng hồ monotonic, lượt đầu sau một interval từ lúc khởi tạo.
- Tại mỗi lần poll đến hạn, mốc sau bằng thời điểm poll + interval. Không
  chạy bù hàng loạt sau khi tiến trình chậm hoặc bị tạm dừng; poll gây độ trễ
  tối đa thông thường bằng poll_seconds, cộng thời gian chờ worker.
- Một Future chưa hoàn tất (đang chờ hoặc chạy) giữ chỗ thiết bị. Nếu đến
  hạn khi đang bận, bỏ lượt và log; thiết bị khác vẫn được điều phối.
- `stop()` gọi được từ luồng khác. `close()` chờ các runner đang chạy và
  không ép đóng phiên SSH; thời gian dừng phụ thuộc timeout hữu hạn của A/C.
  Không gọi `close()` từ chính callback backup/worker vì sẽ chờ luồng đó.
- Chống chồng chỉ trong cùng một instance scheduler. Chưa có khóa liên
  tiến trình/instance hoặc khóa chung với tác vụ thủ công của C; C cần
  điều phối nếu có các nguồn chạy đồng thời. Không chạy nhiều scheduler
  cho cùng thiết bị.
- Chỉ chạy khi tiến trình còn sống; không lưu mốc đến hạn qua khởi động lại,
  không hot reload YAML, không cài dịch vụ hệ điều hành.

Đã chạy đạt 16 phương thức unittest scheduler: YAML hợp lệ/sai,
hai lượt đồng hồ giả, interval riêng và bỏ chạy bù, chống chồng lúc chạy và
chờ pool, lỗi backup/runner/submit không ngăn thiết bị khác, retry ở interval
kế tiếp, log lỗi khi runner đã bắt ngoại lệ, stop/close/Ctrl+C. Một bài dùng
BackupService và SQLite thật trong thư mục tạm với thiết bị giả để kiểm tra
hai phiên bản có cấu hình và restore point riêng. Không dùng SSH thật,
không chờ interval thật; Event chỉ dùng đồng bộ luồng với timeout ngắn.

Bản giải nén ban đầu không có `.git`, nên lúc review chưa kiểm tra được nhánh.
Khi chuẩn bị bàn giao Git theo yêu cầu của Dương, dự án được thêm vào thư mục
`network-backup-system/` của repository `Yena198/oop`, nhánh `dương`.
File `network_automation.py` đã có trên nhánh được giữ nguyên. Bộ 70 unittest
đã chạy đạt lần nữa tại bản chuẩn bị đẩy Git. Các kết quả review trước đó
không có commit vẫn được giữ làm lịch sử.

Không đưa `data/`, `backups/`, `.env` hoặc dữ liệu phục hồi thật lên Git.
Khi chuẩn bị đẩy Git theo yêu cầu của Dương, `.gitignore` đã được bổ sung
data/, backups/, logs/, reports/ và các thư mục tạm của kiểm thử B. Vẫn cần
kiểm tra từng file định commit; không đưa bản sao thực nghiệm lên kho.

## Máy ảo và minh chứng còn cần

- Viết code và chạy unittest trên Windows hiện tại không cần máy ảo.
- Để thử thiết bị thật, có thể dùng EVE-NG của A và Ubuntu Server 24.04 đã
  chạy Python 3.12 của A. Máy Dương phải có đường mạng tới lab nếu kết nối
  trực tiếp; IP VMware trong inventory không tự truy cập được từ máy khác.
- Nếu chưa có đường mạng, chuyển code B sang máy/Ubuntu của A để chạy tích
  hợp. Tạo lại .venv từ requirements tại máy đích, không chép .venv Windows.
- Chỉ dựng lab riêng khi cần độc lập: phải phối hợp A về EVE-NG, image,
  topology, tài nguyên máy và SSH; không cần cài thêm chỉ để chạy unit test.
- Minh chứng cần có: hai phiên bản riêng, diff đúng thay đổi, baseline và
  sai lệch, restore khôi phục được thay đổi (kể cả dòng thừa), hậu điều kiện
  verify, ID bản sao trước thao tác và ít nhất hai lượt lịch chạy qua TaskRunner.
- Thử trên bốn thiết bị/hai nền tảng đã bàn giao. Không lấy FakeDevice làm
  minh chứng thiết bị thật. Ghi riêng hạn chế verify/VLAN của A.

Chưa có kết quả tích hợp với lab. Cần thử luồng trên với C/TaskRunner và
thiết bị thật, thu minh chứng, rồi cập nhật kết quả thực tế vào tài liệu.
