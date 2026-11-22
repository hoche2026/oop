# Sửa đối chiếu sau restore R2

Minh chứng lab: R1 đạt, R2 failed ở verify. Đọc lại R2 cho thấy OSPF 10 và
Loopback101 không còn; diff sau chuẩn hóa chỉ có thêm một dòng ! đơn lẻ.

Bộ so sánh mới bỏ dòng ! phân cách ngoài banner khi nhận diện cấu hình IOS
có version/hostname/end. Không sửa file backup gốc, không bỏ dòng lệnh hay
comment có nội dung. Giữ nguyên ! và chuỗi giống header bên trong banner.
Văn bản ngoài IOS không bị áp quy tắc này.

Sáu test bổ sung: separator đầu/thân, lệnh/comment thật, banner, văn bản
ngoài IOS và recheck chỉ đọc. Tổng sau sửa: 105 unittest.

verify_ospf_restore.py kiểm tra state/endpoint/hash, kết nối đọc cấu hình và
so với bản trước của cả hai router. Không gọi push/restore. Chỉ sau khi cả
hai khớp và lưu report thành công mới xóa state; backups giữ nguyên. Nếu
chưa khớp, giữ state và báo failed, không thử restore lặp.
