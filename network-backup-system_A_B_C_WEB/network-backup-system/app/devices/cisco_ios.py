import re
from datetime import datetime, timezone

from netmiko import ConnectHandler
from ntc_templates.parse import parse_output

from app.contracts import DeviceCommandError, DeviceConnectionError
from app.devices.base import NetworkDevice


class CiscoIOSDevice(NetworkDevice):
    _restore_file_system = "disk0:"
    """Giao tiếp và thu thập thông tin Cisco IOS bằng Netmiko."""

    def connect(self):
        """Mở SSH và vào chế độ đặc quyền."""
        if self._reuse_connection():
            return

        try:
            self._connection = ConnectHandler(
                device_type="cisco_ios",
                host=self.host,
                port=self._info.port,
                username=self._username,
                password=self._password,
                secret=self._secret,
                conn_timeout=15,
                auth_timeout=30,
                banner_timeout=30,
                ssh_strict=True,
                system_host_keys=True,
            )
            self._connection.enable()

        except Exception as error:
            self._discard_connection()
            raise DeviceConnectionError(
                f"{self.name}: ket noi hoac vao enable that bai "
                f"({type(error).__name__})."
            ) from error

    def disconnect(self):
        """Đóng kết nối; gọi nhiều lần vẫn an toàn."""
        connection = self._connection
        self._connection = None

        if connection is not None:
            connection.disconnect()

    def send_command(self, command):
        """Gửi lệnh và phát hiện phản hồi lỗi CLI thường gặp."""
        if self._connection is None:
            raise DeviceConnectionError(
                f"{self.name}: chua ket noi."
            )

        if not isinstance(command, str) or not command.strip():
            raise DeviceCommandError("Lenh phai la chuoi khong rong.")

        try:
            output = self._connection.send_command(
                command,
                read_timeout=30,
            )
        except Exception as error:
            raise DeviceCommandError(
                f"{self.name}: khong thuc thi duoc lenh "
                f"({type(error).__name__})."
            ) from error

        error_pattern = (
            r"(?im)^\s*%\s*(?:Invalid input|Incomplete command|"
            r"Ambiguous command|Authorization failed|Error\b|"
            r"Unrecognized command|Unknown command)"
        )
        if re.search(error_pattern, output):
            raise DeviceCommandError(
                f"{self.name}: thiet bi tu choi lenh."
            )

        return output

    def backup_config(self):
        """Lấy running-config để phần B quản lý bản sao."""
        output = self.send_command("show running-config")

        if not output.strip() or "end" not in output.splitlines():
            raise DeviceCommandError(
                f"{self.name}: cau hinh nhan ve rong hoac chua day du."
            )

        return output

    @staticmethod
    def _parse_table(command, output):
        """Phân tích bảng bằng NTC Templates."""
        records = parse_output(
            platform="cisco_ios",
            command=command,
            data=output,
        )

        if not isinstance(records, list) or not all(
            isinstance(record, dict) for record in records
        ):
            raise ValueError("Ket qua phan tich khong phai danh sach ban ghi.")

        return records

    def _collect_parsed(self, command):
        """Lấy bảng bắt buộc phải có bản ghi."""
        output = self.send_command(command)

        try:
            records = self._parse_table(command, output)
        except Exception as error:
            raise DeviceCommandError(
                f"{self.name}: khong phan tich duoc {command} "
                f"({type(error).__name__})."
            ) from error

        if not records:
            raise DeviceCommandError(
                f"{self.name}: {command} khong tra ve ban ghi."
            )

        return records

    @staticmethod
    def _parse_cpu(output):
        """Phân tích tổng CPU và kiểm tra tính nhất quán."""
        pattern = (
            r"five seconds:\s*(\d+)%/(\d+)%;"
            r"\s*one minute:\s*(\d+)%;"
            r"\s*five minutes:\s*(\d+)%"
        )
        match = re.search(pattern, output, re.IGNORECASE)

        if match is None:
            raise ValueError("Khong nhan dien duoc dong thong ke CPU.")

        total, interrupt, one_minute, five_minutes = map(
            int, match.groups()
        )

        values = (total, interrupt, one_minute, five_minutes)
        valid = (
            all(0 <= value <= 100 for value in values)
            and interrupt <= total
        )

        return {
            "five_seconds_percent": total,
            "interrupt_percent": interrupt,
            "one_minute_percent": one_minute,
            "five_minutes_percent": five_minutes,
            "valid": valid,
            "raw": output.strip(),
            "note": (
                None
                if valid
                else "So lieu CPU ngoai mien hoac khong nhat quan."
            ),
        }

    @staticmethod
    def _parse_memory(output):
        """Phân tích từng vùng nhớ, đơn vị byte."""
        pattern = (
            r"^\s*(\S+)\s+[0-9A-Fa-f]+\s+"
            r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$"
        )
        pools = []

        for line in output.splitlines():
            match = re.match(pattern, line)
            if match is None:
                continue

            name = match.group(1)
            total, used, free, lowest, largest = map(
                int, match.groups()[1:]
            )
            valid = total > 0 and used + free == total

            pools.append({
                "name": name,
                "total_bytes": total,
                "used_bytes": used,
                "free_bytes": free,
                "lowest_free_bytes": lowest,
                "largest_free_block_bytes": largest,
                "used_percent": (
                    round(used * 100 / total, 2) if valid else None
                ),
                "valid": valid,
            })

        if not pools:
            raise ValueError("Khong nhan dien duoc cac vung nho.")

        return {
            "pools": pools,
            "valid": all(pool["valid"] for pool in pools),
        }

    def _collect_section(self, command, parser):
        """Thu thập một mục; lỗi không làm mất các mục còn lại."""
        try:
            output = self.send_command(command)
            data = parser(output)

            if isinstance(data, list):
                status = "ok" if data else "empty"
            elif isinstance(data, dict) and data.get("valid") is False:
                status = "invalid"
            else:
                status = "ok"

            return {
                "status": status,
                "data": data,
                "error": None,
            }

        except Exception as error:
            return {
                "status": "error",
                "data": None,
                "error": f"{type(error).__name__}: {error}",
            }

    def get_facts(self):
        """Thu thập thông tin hệ thống, bảng mạng và tài nguyên."""
        version = self._collect_parsed("show version")[0]
        interface_records = self._collect_parsed(
            "show ip interface brief"
        )

        interfaces = []

        for record in interface_records:
            name = record.get("interface") or record.get("intf")
            address = record.get("ip_address") or record.get("ipaddr")

            if not name:
                raise DeviceCommandError(
                    f"{self.name}: ban ghi cong thieu ten interface."
                )

            interfaces.append({
                "name": name,
                "ip_address": (
                    None if address in (None, "", "unassigned") else address
                ),
                "status": record.get("status") or None,
                "protocol": record.get("proto") or None,
            })

        facts = {
            "schema_version": 1,
            "device_name": self.name,
            "management_ip": self.host,
            "platform": self._info.platform,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "hostname": version.get("hostname") or None,
            "os_version": version.get("version") or None,
            "uptime": version.get("uptime") or None,
            "hardware": version.get("hardware") or [],
            "serial_numbers": version.get("serial") or [],
            "interfaces": interfaces,
        }

        table_commands = {
            "routing_table": "show ip route",
            "arp_table": "show ip arp",
            "cdp_neighbors": "show cdp neighbors",
        }

        for section, command in table_commands.items():
            facts[section] = self._collect_section(
                command,
                lambda output, cmd=command: self._parse_table(cmd, output),
            )

        facts["cpu"] = self._collect_section(
            "show processes cpu | include CPU utilization",
            self._parse_cpu,
        )
        facts["memory"] = self._collect_section(
            "show memory statistics",
            self._parse_memory,
        )

        return facts

    def push_config(self, config_text):
        """Áp các dòng cấu hình; chưa lưu startup-config hay rollback."""
        if self._connection is None:
            raise DeviceConnectionError(
                f"{self.name}: chua ket noi."
            )

        if not isinstance(config_text, str) or not config_text.strip():
            raise DeviceCommandError("Cau hinh phai la chuoi khong rong.")

        commands = [
            line.strip()
            for line in config_text.splitlines()
            if line.strip() and not line.strip().startswith("!")
        ]

        if not commands:
            raise DeviceCommandError("Khong co lenh cau hinh.")

        forbidden = {
            "configure terminal", "conf t", "end",
            "write memory", "wr", "reload",
        }
        if any(command.lower() in forbidden for command in commands):
            raise DeviceCommandError(
                "Chi truyen lenh cau hinh, khong kem lenh EXEC."
            )

        error_pattern = (
            r"(?im)^%\s*(?:Invalid input|Incomplete command|"
            r"Ambiguous command|Authorization failed|"
            r"Error|Bad mask|Inconsistent)"
        )

        try:
            self._connection.enable()
            output = self._connection.send_config_set(
                commands,
                read_timeout=60,
                error_pattern=error_pattern,
            )

        except Exception as error:
            raise DeviceCommandError(
                f"{self.name}: ap cau hinh that bai "
                f"({type(error).__name__}); "
                "mot so lenh truoc do co the da duoc ap."
            ) from error

        return {
            "device": self.name,
            "commands_sent": len(commands),
            "output": output,
            "saved_to_startup": False,
        }

    def verify_config(self, config_text, checks):
        """Xác minh hậu điều kiện; chưa so sánh toàn bộ cấu hình."""
        from ipaddress import IPv4Address

        from app.contracts import VerificationError, VerificationResult

        if not isinstance(config_text, str):
            raise VerificationError("config_text phai la chuoi.")

        if not isinstance(checks, dict) or not checks:
            raise VerificationError("checks phai la dictionary khong rong.")

        if set(checks) - {"interfaces", "ping"}:
            raise VerificationError("Chi ho tro checks interfaces va ping.")

        expected_interfaces = checks.get("interfaces", {})
        if not isinstance(expected_interfaces, dict):
            raise VerificationError("interfaces phai la dictionary.")

        for name, expected in expected_interfaces.items():
            if not isinstance(name, str) or not name.strip():
                raise VerificationError("Ten cong khong hop le.")

            if not isinstance(expected, dict) or not expected:
                raise VerificationError("Dieu kien cong phai khong rong.")

            if set(expected) - {"ip_address", "status", "protocol"}:
                raise VerificationError("Truong kiem tra cong chua ho tro.")

            if not all(isinstance(value, str) for value in expected.values()):
                raise VerificationError("Gia tri kiem tra cong phai la chuoi.")

        ping_check = checks.get("ping")
        if ping_check is not None:
            if not isinstance(ping_check, dict):
                raise VerificationError("ping phai la dictionary.")

            allowed = {"target", "source", "min_success_percent"}
            if set(ping_check) - allowed:
                raise VerificationError("Truong kiem tra ping chua ho tro.")

            try:
                target = str(IPv4Address(ping_check["target"]))
                source = str(IPv4Address(ping_check["source"]))
            except (KeyError, ValueError, TypeError) as error:
                raise VerificationError(
                    "Ping can target va source la dia chi IPv4."
                ) from error

            threshold = ping_check.get("min_success_percent", 100)
            if type(threshold) is not int or not 0 <= threshold <= 100:
                raise VerificationError("Nguong ping phai tu 0 den 100.")

        if not expected_interfaces and ping_check is None:
            raise VerificationError("Khong co dieu kien nao de kiem tra.")

        results = {}
        details = []

        if expected_interfaces:
            try:
                records = self._collect_parsed("show ip interface brief")
                actual_interfaces = {}

                for record in records:
                    name = record.get("interface") or record.get("intf")
                    actual_interfaces[name] = {
                        "ip_address": (
                            record.get("ip_address") or record.get("ipaddr")
                        ),
                        "status": record.get("status"),
                        "protocol": record.get("proto"),
                    }

                for name, expected in expected_interfaces.items():
                    actual = actual_interfaces.get(name, {})

                    for field, value in expected.items():
                        key = f"{name}.{field}"
                        results[key] = actual.get(field) == value
                        details.append(
                            f"{key}: expected={value}, "
                            f"actual={actual.get(field)}"
                        )

            except (DeviceCommandError, DeviceConnectionError) as error:
                results["interfaces_collection"] = False
                details.append(f"Khong kiem tra duoc cong: {error}")

        if ping_check is not None:
            try:
                command = (
                    f"ping {target} source {source} repeat 5 timeout 2"
                )
                output = self.send_command(command)
                match = re.search(
                    r"Success rate is\s+(\d+)\s+percent",
                    output,
                )

                if match is None:
                    results["ping"] = False
                    details.append("Khong doc duoc ty le ping.")
                else:
                    percent = int(match.group(1))
                    results["ping"] = (
                        0 <= percent <= 100 and percent >= threshold
                    )
                    details.append(
                        f"ping {source} -> {target}: "
                        f"{percent}%, required>={threshold}%"
                    )

            except (DeviceCommandError, DeviceConnectionError) as error:
                results["ping"] = False
                details.append(f"Khong kiem tra duoc ping: {error}")

        return VerificationResult(
            passed=bool(results) and all(results.values()),
            details=details,
            checks=results,
        )
    def restore_config(self, config_text: str):
        import re
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from uuid import uuid4

        from netmiko import file_transfer

        from app.contracts import RestoreError

        if self._connection is None:
            raise RestoreError("Chua ket noi thiet bi.")

        if not isinstance(config_text, str) or not config_text.strip():
            raise RestoreError("Ban cau hinh phai la chuoi khong rong.")

        # Bo phan tieu de do lenh show running-config sinh ra.
        lines = config_text.replace("\r\n", "\n").splitlines()
        start = next(
            (
                index
                for index, line in enumerate(lines)
                if re.fullmatch(r"version\s+\S+", line.strip())
            ),
            None,
        )

        if start is None:
            raise RestoreError("Khong tim thay dong version trong ban sao.")

        lines = lines[start:]

        while lines and not lines[-1].strip():
            lines.pop()

        if not lines or lines[-1].strip() != "end":
            raise RestoreError("Ban sao thieu dong end o cuoi.")

        normalized = "\n".join(lines) + "\n"

        hostname_match = re.search(
            r"^hostname\s+(\S+)\s*$",
            normalized,
            flags=re.MULTILINE,
        )

        if hostname_match is None:
            raise RestoreError("Ban sao thieu hostname.")

        if not re.search(r"^interface\s+\S+", normalized, re.MULTILINE):
            raise RestoreError("Ban sao thieu cau hinh interface.")

        remote_name = f"oop_restore_{uuid4().hex}.cfg"
        remote_path = f"{self._restore_file_system}{remote_name}"
        stage = "kiem tra ban sao"

        try:
            self._connection.enable()

            # Chan viec nap nham ban sao cua router khac hostname.
            current_config = self.backup_config()
            current_hostname = re.search(
                r"^hostname\s+(\S+)\s*$",
                current_config,
                flags=re.MULTILINE,
            )

            if current_hostname is None:
                raise RestoreError("Khong doc duoc hostname hien tai.")

            if hostname_match.group(1) != current_hostname.group(1):
                raise RestoreError(
                    "Hostname ban sao khac hostname thiet bi hien tai."
                )

            stage = "chuyen va xac minh file"

            with TemporaryDirectory() as temporary_dir:
                local_file = Path(temporary_dir) / remote_name
                local_file.touch(mode=0o600)
                local_file.write_text(normalized, encoding="utf-8")

                transfer_result = file_transfer(
                    self._connection,
                    source_file=str(local_file),
                    dest_file=remote_name,
                    file_system=self._restore_file_system,
                    direction="put",
                    overwrite_file=False,
                    disable_md5=False,
                )

            if not transfer_result.get("file_verified"):
                raise RestoreError(
                    "File chua duoc xac minh; chua thuc hien khoi phuc."
                )

            stage = "thay the running-config"
            prompt = self._connection.find_prompt()

            output = self._connection.send_command(
                f"configure replace {remote_path} force",
                expect_string=re.escape(prompt),
                read_timeout=120,
            )

            error_pattern = (
                r"(?im)^%\s*(?:Error|Invalid|Failed|"
                r"Unable|Authorization failed)"
            )

            if (
                "Rollback Done" not in output
                or re.search(error_pattern, output)
            ):
                raise RestoreError(
                    "Router chua xac nhan khoi phuc thanh cong. "
                    f"Kiem tra console; file: {remote_path}"
                )

            return {
                "device": self.name,
                "restored": True,
                "remote_file": remote_path,
                "file_verified": True,
                "saved_to_startup": False,
                "post_checks_required": True,
            }

        except RestoreError:
            raise

        except Exception as error:
            raise RestoreError(
                f"Loi tai buoc '{stage}': {type(error).__name__}. "
                f"File dich: {remote_path}. "
                "Neu da bat dau thay the cau hinh, can kiem tra console."
            ) from error
