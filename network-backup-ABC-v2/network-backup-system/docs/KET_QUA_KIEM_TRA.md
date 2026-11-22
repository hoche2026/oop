# Kiểm chứng gói nguồn đã gộp fix R2

- Nguồn: bản ABC v2 cộng payload fix R2, không cần ZIP fix bên ngoài.
- Bổ sung docstring public API và chuẩn hóa bố cục Python. So sánh AST khi
  bỏ docstring: không thay đổi logic so với bản đã gộp fix trước biên tập.
- Chạy unittest tại đúng thư mục nguồn đóng gói: Ran 105 tests, OK.
- pycodestyle --ignore=E501,W503,W504 đạt; các ngoại lệ là độ dài chuỗi/
  regex/dữ liệu mẫu và quy ước ngắt toán tử, không khẳng định mọi dòng <=79 ký tự.
- requirements giữ các phiên bản môi trường ứng dụng đã kiểm tra; công cụ
  biên tập autopep8/pycodestyle nằm trong venv riêng, không thêm vào phụ thuộc app.
- Kết quả lab theo người dùng xác nhận: bốn thiết bị, backup, diff/baseline,
  rollback, lịch, OSPF apply/verify/restore, recheck sau sửa R2, native restore
  MT1 và kiểm tra cuối. Đội báo cáo đối chiếu ảnh gốc trước khi trích số liệu.
- Không có .env, database, backups, logs/reports vận hành thật trong gói.
- docs/ ngoài gốc gói chưa có báo cáo cuối; demo/ chưa có đủ 26 ảnh gốc.
  Người nhận bổ sung từ tài liệu/ảnh của nhóm trước khi nộp.
