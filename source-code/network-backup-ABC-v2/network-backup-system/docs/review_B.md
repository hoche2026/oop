# Rà soát phần B — 10/11/2026

Áp dụng quy trình trong bản skill
[network-backup-review](skill-drafts/network-backup-review/SKILL.md).
Đây là báo cáo gồm lịch sử xác nhận hai P2 và lượt sửa theo yêu cầu tiếp theo.
Lượt xác nhận trước sửa đã ghi nhận 65 unittest, validator skill và hai phép
tái hiện riêng bằng dữ liệu giả. Không lấy kết quả đó xác nhận code mới.

## Trạng thái sau sửa hai P2

Đã sửa `app/backup.py` và `tests/test_backup.py`, cập nhật báo cáo này cùng
`docs/handover_B.md`. Giữ nguyên API công khai, không sửa A/C, storage hoặc
scheduler, không thêm thư viện và không thao tác thiết bị thật.

- **P2 độ bao phủ verify — đã sửa và xác nhận bằng kiểm thử offline:**
  `app/backup.py:121`, `131`, `157` truyền checks vào kiểm tra nội bộ;
  yêu cầu đủ ping và `<interface>.<field>` ở cả hai giai đoạn. Thiếu tiêu chí
  báo VerificationError kèm kết quả verify, stage và ID cứu hộ nếu đã có.
  Tôn trọng `interfaces_collection=False` của A như lỗi thu thập rõ ràng:
  cho phép precheck thất bại, nhưng không cho phép thành công sau restore.
- **P2 fixture Cisco — đã sửa và xác nhận bằng kiểm thử offline:** fixture tại
  `tests/test_backup.py:67` thêm source `192.0.2.2`; FakeDevice trả các tiêu
  chí theo checks. Thêm test đi qua `CiscoIOSDevice.verify_config()` thật,
  thay send_command và _collect_parsed bằng dữ liệu giả; chặn connect và
  disconnect, không đọc .env thật. Không sửa API A để phù hợp test.
- Năm phương thức test mới: thiếu ping/trường/interface ở cả precheck và
  sau restore (kiểm tra nội dung bản sao cứu hộ); fixture hợp lệ qua API A
  cho ping/interfaces/kết hợp; thiếu source bị A từ chối trước I/O; lỗi
  collection trước/sau restore; cờ collection=True không thay tiêu chí.

Đã gọi toàn bộ unittest sau sửa bằng lệnh được yêu cầu:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Phiên CLI sửa code bị chặn trước discovery với exit code 103: 0 test chạy
trong phiên đó. Lượt kiểm chứng tiếp theo ngày 10/11/2026 đã chạy lại trên
Python 3.12.10: **70/70 unittest đạt, exit code 0**, gồm 22 A, 11 storage,
21 BackupService và 16 scheduler. `pip check` báo không lỗi phụ thuộc.
Không cài lại Python hoặc thay .venv.

Đã đọc và chạy đạt cả năm test mới, gồm các subtest thiếu ping/trường/interface,
kiểm tra ID/nội dung bản sao cứu hộ sau restore, verify Cisco thật với I/O
giả và lỗi thu thập interface. Hai P2 được đóng trong phạm vi kiểm chứng
offline này. Chưa tích hợp TaskRunner thật hoặc lab thật. Các mục bên dưới
mô tả bản trước sửa và kết quả cũ, được giữ làm lịch sử.

## Phát hiện đã xác nhận trên bản trước sửa

### [P2] Chưa đối chiếu đủ tiêu chí verify với checks được yêu cầu

- Vị trí: [app/backup.py](../app/backup.py), dòng 157–170; nơi sử dụng kết quả
  sau restore ở dòng 131–142.
- Điều kiện: caller yêu cầu cả ping và trạng thái một interface, nhưng
  adapter trả `VerificationResult(True, [], {"ping": True})` ở hai lần verify.
  `_validate_verification()` chỉ kiểm tra checks không rỗng, giá trị bool và
  passed nhất quán với các giá trị đã trả. Hàm không nhận checks đầu vào nên
  không thể phát hiện kết quả interface bị thiếu; restore có thể trả
  `restored=True` dù tiêu chí đó chưa được kiểm tra.
- Ảnh hưởng: thiếu bảo vệ ở ranh giới B/A khi kết quả verify chỉ bao phủ một
  phần yêu cầu. Chưa có bằng chứng adapter A hiện tại bỏ sót ở đường chạy
  bình thường: vòng lặp của Cisco/MikroTik đang tạo kết quả từng trường
  interface và ping, hoặc đánh dấu lỗi thu thập. Vì vậy đây là thiếu kiểm tra
  hợp đồng ở B, không kết luận lab hiện đang báo thành công sai.
- Bằng chứng bổ sung: [tests/test_backup.py](../tests/test_backup.py), dòng
  216–228 chỉ kiểm tra kết quả rỗng, passed mâu thuẫn và sai kiểu; chưa có ca
  kết quả không rỗng nhưng thiếu một tiêu chí. FakeDevice dòng 43–45 luôn
  trả duy nhất ping, không phụ thuộc checks.
- Đề xuất: đối chiếu tập tiêu chí yêu cầu với kết quả theo ánh xạ API A
  hiện có (ping và `<interface>.<field>`), giữ nguyên chữ ký công khai
  `restore(device, backup_id, checks)`. Thêm ca thiếu một trường/interface
  hoặc ping: phải báo VerificationError, không trả thành công; sau thao tác
  vẫn giữ pre_backup_id. Trước khi áp dụng ánh xạ mới cần đối chiếu với A,
  không tự đổi schema kết quả.
- Mức chứng minh: đã tái hiện offline ngày 10/11/2026. Tạo BackupService và
  SQLite trong thư mục tạm, dùng FakeDevice hiện có, yêu cầu ping có source
  và Loopback0.status=up. Restore trả restored=True nhưng verification.checks
  chỉ có ping=True. Đây là tái hiện thiếu bảo vệ khi adapter trả thiếu dữ
  liệu, không phải bằng chứng adapter A hiện tại bỏ sót trong lab bình thường.

### [P2] Checks trong test restore Cisco không hợp lệ với API thật của A

- Vị trí: [tests/test_backup.py](../tests/test_backup.py), dòng 55; fake verify
  ở dòng 43–45 và test thành công dòng 144–155.
- Điều kiện: dùng bộ CHECKS hiện tại với CiscoIOSDevice thật. Bộ này chỉ có
  target và min_success_percent; thiếu source. Trong
  [app/devices/cisco_ios.py](../app/devices/cisco_ios.py), dòng 395–401,
  verify truy cập `ping_check["source"]` và chuyển KeyError thành
  VerificationError. BackupService sẽ dừng ở precheck, trước khi restore.
- Ảnh hưởng: test nghiệp vụ có thể đạt với fake dù chính đầu vào đó không
  chạy qua API Cisco thật. Đây là sai lệch fixture/thiếu test hợp đồng,
  không phải lỗi phải sửa trong API A. MikroTik cho phép bỏ source ở dòng
  491–495 của [app/devices/mikrotik.py](../app/devices/mikrotik.py), nên
  không giả định cùng mức bắt buộc giữa hai nền tảng.
- Đề xuất: dùng source IPv4 giả hợp lệ trong fixture Cisco; thêm kiểm thử
  offline đi qua verify_config thật của A với I/O giả để kiểm tra đầu vào
  B/C. Có thể tiếp tục dùng FakeDevice cho test thứ tự thao tác, nhưng không
  dùng kết quả đó làm minh chứng tương thích thiết bị. Không sửa A chỉ để
  phù hợp fake.
- Mức chứng minh: đã tái hiện offline ngày 10/11/2026. Gọi verify_config()
  thật của CiscoIOSDevice với BackupServiceTests.CHECKS; chặn send_command
  bằng mock để không thể có I/O mạng. Kết quả là VerificationError:
  `Ping can target va source la dia chi IPv4.` trước mọi lệnh thiết bị.

Không phát hiện P1 có đủ bằng chứng trong phạm vi đọc hiện tại. Điều này
không chứng minh mọi đường chạy đều đúng; runner thật và lab chưa tích hợp.

## Đối chiếu chín nhóm yêu cầu

| Nhóm | Quan sát tĩnh và giới hạn |
|---|---|
| 1. Hợp đồng/phạm vi | BackupService giữ các phương thức công khai; BackupRecord có sáu trường tại storage.py:33. Scheduler nhận runner từ ngoài. Chưa có runner/main.py của C để xác minh tích hợp. |
| 2. Phiên SSH | Ba module B không gọi connect/disconnect và không chứa lệnh cấu hình theo hãng. Callback scheduler gọi service trên thiết bị do runner cấp. Phiên riêng mỗi worker vẫn phải được C bảo đảm. |
| 3. Hai loại bản sao | backup.py:26 gọi riêng backup_config/create_restore_point; storage.py:133 tạo .cfg và .restore, liên kết qua backup_id. Không dùng export MikroTik thay restore point; diff chỉ đọc cấu hình. |
| 4. Sở hữu/hash | backup.py:108 kiểm tra thiết bị/platform trước khi đọc hai file; storage.py:193 kiểm tra tồn tại/hash và UTF-8. _safe_path kiểm tra đường dẫn nằm trong dự án. Các bài hash/path đã chạy đạt trong bộ 65 unittest. |
| 5. Bản sao trước restore | backup.py:124 lưu bản sao trước restore_config ở dòng 126; storage trả record sau transaction. Lỗi có pre_backup_id và stage. |
| 6. Verify/trạng thái | Trước sửa thiếu độ bao phủ như phát hiện thứ nhất; lượt sửa đã thêm đối chiếu tiêu chí, chưa chạy xác nhận. Verify rỗng, passed=False hoặc không nhất quán bị từ chối; lỗi restore không đi tiếp sang thành công và không có vòng retry/rollback. B trả ngoại lệ stage=restore để C xử lý timeout/chưa xác định, không trả thành công. |
| 7. Đồng thời | storage.py:93 mở connection riêng/đóng finally, timeout 30 giây, foreign keys; schema dùng WAL, SQL tham số và transaction. scheduler.py:160 khóa khi xét/gửi việc, dòng 170 chặn Future chưa xong cả lúc chờ/running. Phạm vi chỉ một instance và runner phải chờ worker hoàn tất; không coi khóa liên tiến trình chưa có là lỗi mới. |
| 8. Bí mật | Log scheduler chỉ ghi tên và loại ngoại lệ, không bật exc_info; chưa thấy chỗ B tự log payload. compare/check_changes trả diff nguyên văn, restore trả details/restore_result và giữ chuỗi nguyên nhân ngoại lệ: C phải lọc trước khi xuất báo cáo. Chưa có module reporting C nên không kết luận đã che bí mật toàn luồng. Báo cáo này chỉ dùng dữ liệu tổng hợp, không mở .env/bản sao thật. |
| 9. Minh chứng | Test B dùng fake và thư mục/DB tạm. Handoff A có kết quả lab riêng; không suy ra B đã tích hợp lab. Scheduler test dùng đồng hồ giả, không phải hai lượt backup thiết bị thật. |

## Lịch sử kiểm thử và kiểm tra skill trước sửa P2

Đã gọi đúng lệnh tại gốc dự án:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Phiên CLI ban đầu dừng với mã 103 trước discovery và báo Access is denied
khi kiểm tra Python gốc: 0 test chạy trong phiên đó. Không đủ bằng chứng
kết luận Python đã bị gỡ.

Phiên kiểm chứng tiếp theo cùng ngày đã chạy thành công lệnh trên:
**65/65 unittest đạt, exit code 0**. Không cài lại Python hoặc thay .venv.
Hai phép tái hiện riêng cũng có exit code 0 và đều xác nhận phát hiện;
chúng không được cộng vào số 65 unittest. Tất cả dùng dữ liệu giả, không
SSH hoặc chạy lab. Bộ test hiện có vẫn xanh vì chưa có ca bắt hai phát hiện.

Đã thử validator của skill-creator:

```powershell
.\.venv\Scripts\python.exe -X utf8 C:/Users/ADMIN/.codex/skills/.system/skill-creator/scripts/quick_validate.py docs/skill-drafts/network-backup-review
```

Validator ban đầu bị chặn trong CLI. Ở phiên kiểm chứng, chạy Python mặc
định gặp UnicodeDecodeError do mã hóa Windows; thêm `-X utf8` đọc đúng
tiếng Việt và validator trả **Skill is valid!, exit code 0**. Không sửa
validator hoặc cài thư viện mới. Đã đối chiếu chín nhóm yêu cầu, đường dẫn,
quy trình và mẫu báo lỗi. Validator không chứng minh skill đã được hệ thống
phát hiện; việc đặt skill đúng vị trí được ghi riêng bên dưới.

Không thêm thư viện/tool/helper script hay metadata UI không cần thiết.
Đã dùng bản skill chờ để thực hiện quy trình review trên.

## File tạo và phần còn cần

- `.agents/skills/network-backup-review/SKILL.md`: skill đã đặt đúng vị trí
  sau khi được cấp quyền ghi ngoài sandbox.
- `docs/skill-drafts/network-backup-review/SKILL.md`: bản chờ ban đầu được
  giữ lại, có SHA256 giống bản đã cài.
- `docs/review_B.md`: báo cáo này.

Trong phiên CLI ban đầu, bộ kiểm tra phê duyệt tự động từ chối ghi `.agents`
vì vùng này chỉ cho đọc. Trong lượt hoàn tất, đã yêu cầu quyền ghi ngoài
sandbox và được cho phép đặt bản skill đã xác thực vào vị trí yêu cầu.
Validator chạy với `-X utf8` trên cả bản chờ và bản đã cài đều trả
`Skill is valid!`, exit code 0. Hai file có cùng SHA256:
`EB872FA49EACB1685ACB1A49AB5B7FDF2DBF70B413B4FF26EE1FCC293180F0F9`.
Bản skill không có script hay tài nguyên phụ cần chuyển. Chưa quan sát
việc chọn skill trong một phiên CLI mới; không đồng nhất validator với
kiểm tra discovery của ứng dụng.

Validator, unittest và hai phép tái hiện đã chạy trong lượt kiểm chứng trước
sửa. Lượt sửa tiếp theo và trở ngại chạy test đã ghi ở đầu báo cáo.
Tiếp theo phối hợp C kiểm tra runner đồng bộ, phiên SSH riêng,
lọc báo cáo, rồi thực hiện kịch bản lab được cho phép để thu minh chứng.

Git báo không có repository ở thư mục hiện tại, nên chưa có git diff/nhánh
để đối chiếu. Không init Git hoặc commit. Đã đối chiếu SHA256 trước/sau cho
ba module B, ba file test tương ứng, AGENTS.md và docs/handover_B.md để kiểm
tra chúng được giữ nguyên trong lượt review trước sửa. Lượt sửa P2 chỉ đổi
backup.py, test_backup.py và hai tài liệu B đã liệt kê ở đầu báo cáo.
