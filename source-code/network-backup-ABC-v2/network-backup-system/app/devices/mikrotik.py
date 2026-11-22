import json
import re
from datetime import datetime, timezone

from netmiko import ConnectHandler

from app.contracts import (
    DeviceCommandError,
    DeviceConnectionError,
    RestoreError,
    VerificationError,
)
from app.devices.base import NetworkDevice


class MikroTikDevice(NetworkDevice):
    """Giao tiếp RouterOS và phục hồi bằng bản sao native mã hóa."""

    def connect(self):
        """Mở SSH, kiểm tra host key và chuyển lỗi kết nối thành ngoại lệ chung."""
        if self._reuse_connection():
            return

        try:
            self._connection = ConnectHandler(
                device_type="mikrotik_routeros",
                host=self._info.host,
                port=self._info.port,
                username=self._username,
                password=self._password,
                conn_timeout=15,
                auth_timeout=30,
                banner_timeout=30,
                ssh_strict=True,
                system_host_keys=True,
            )

        except Exception as error:
            self._discard_connection()
            raise DeviceConnectionError(
                f"Khong ket noi duoc {self.name}: "
                f"{type(error).__name__}"
            ) from error

    def disconnect(self):
        """Đóng phiên SSH đang giữ và giải phóng tham chiếu kết nối."""
        connection = self._connection
        self._connection = None

        if connection is not None:
            connection.disconnect()

    def send_command(self, command):
        """Thực thi lệnh đọc và phát hiện phản hồi lỗi của thiết bị."""
        if self._connection is None:
            raise DeviceConnectionError("Chua ket noi thiet bi.")

        if not isinstance(command, str) or not command.strip():
            raise DeviceCommandError("Lenh phai la chuoi khong rong.")

        try:
            output = self._connection.send_command(
                command,
                read_timeout=60,
            )
        except Exception as error:
            raise DeviceCommandError(
                f"Khong thuc thi duoc lenh: {type(error).__name__}"
            ) from error

        error_pattern = (
            r"(?im)^\s*(?:failure:|syntax error|bad command name|"
            r"expected end of command|not enough permissions)"
        )

        if re.search(error_pattern, output):
            raise DeviceCommandError(
                "RouterOS bao loi khi thuc thi lenh."
            )

        return output

    def backup_config(self):
        """Lấy cấu hình văn bản để lưu phiên bản và so sánh, không phải native backup."""
        output = self.send_command("/export terse")

        if not output.strip() or "#error exporting" in output.lower():
            raise DeviceCommandError(
                "Ban export rong hoac co loi khi xuat cau hinh."
            )

        if "/system identity" not in output:
            raise DeviceCommandError(
                "Ban export thieu muc system identity."
            )

        return output

    def _read_rows(self, menu):
        command = (
            f":put [:serialize to=json "
            f"value=[{menu} print as-value]]"
        )
        output = self.send_command(command)

        try:
            rows = json.loads(output)
        except json.JSONDecodeError as error:
            raise DeviceCommandError(
                f"Khong doc duoc JSON tu {menu}."
            ) from error

        if not isinstance(rows, list) or not all(
            isinstance(row, dict) for row in rows
        ):
            raise DeviceCommandError(
                f"Du lieu {menu} khong phai danh sach ban ghi."
            )

        return rows

    @staticmethod
    def _is_true(value):
        return str(value).lower() in {"true", "yes", "1"}

    def get_facts(self):
        """Thu thập facts và dữ liệu vận hành theo khả năng của nền tảng."""
        hostname = self.send_command(
            ":put [/system identity get name]"
        ).strip()

        resource_output = self.send_command(
            "/system resource print"
        )
        resources = {}

        for line in resource_output.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                resources[key.strip()] = value.strip()

        if not hostname or not resources.get("version"):
            raise DeviceCommandError(
                "Thieu hostname hoac phien ban RouterOS."
            )

        port_rows = self._read_rows("/interface")
        address_rows = self._read_rows("/ip address")
        interfaces = []

        for port in port_rows:
            name = port.get("name")

            if not name:
                raise DeviceCommandError("Interface thieu ten.")

            addresses = [
                row["address"]
                for row in address_rows
                if row.get("interface") == name
                and row.get("address")
                and not self._is_true(row.get("disabled", False))
            ]

            disabled = self._is_true(port.get("disabled", False))
            running = self._is_true(port.get("running", False))

            if disabled:
                status = "administratively down"
            else:
                status = "up" if running else "down"

            interfaces.append({
                "name": name,
                "ip_address": (
                    addresses[0].split("/")[0]
                    if addresses else None
                ),
                "ip_addresses": addresses,
                "status": status,
                "protocol": "up" if running and not disabled else "down",
            })

        board = resources.get("board-name")

        facts = {
            "schema_version": 1,
            "device_name": self.name,
            "management_ip": self.host,
            "platform": self._info.platform,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "hostname": hostname,
            "os_version": resources["version"],
            "uptime": resources.get("uptime"),
            "hardware": [board] if board else [],
            "serial_numbers": [],
            "interfaces": interfaces,
            "collection_scope": "extended",
        }
        facts.update(self._get_extra_facts())
        return facts

    def push_config(self, config_text):
        """Áp các lệnh cấu hình; tầng nghiệp vụ chịu trách nhiệm backup và rollback."""
        if self._connection is None:
            raise DeviceConnectionError("Chua ket noi thiet bi.")

        if not isinstance(config_text, str) or not config_text.strip():
            raise DeviceCommandError("Cau hinh phai la chuoi khong rong.")

        commands = [
            line.strip()
            for line in config_text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

        if not commands:
            raise DeviceCommandError("Khong co lenh cau hinh.")

        if any(not command.startswith("/") for command in commands):
            raise DeviceCommandError(
                "Moi dong phai la mot lenh RouterOS day du, "
                "bat dau bang dau /."
            )

        outputs = []
        completed = 0

        try:
            for command in commands:
                outputs.append(self.send_command(command))
                completed += 1

        except (DeviceCommandError, DeviceConnectionError) as error:
            raise DeviceCommandError(
                f"Dung khi ap cau hinh sau {completed} lenh "
                "da xac nhan thanh cong. Lenh gap loi co the "
                "da tac dong; can kiem tra lai thiet bi."
            ) from error

        return {
            "device": self.name,
            "commands_sent": completed,
            "output": "\n".join(outputs),
            "saved_to_startup": None,
            "persistence": "automatic",
        }

    def restore_config(self, config_text):
        """Nạp native backup RouterOS đúng định danh, chờ reboot và kết nối lại."""
        import base64
        import hashlib
        import os
        import time
        from uuid import uuid4

        if self._connection is None:
            raise DeviceConnectionError("Chua ket noi thiet bi.")

        if (
            not isinstance(config_text, str)
            or not config_text.strip()
            or len(config_text) > 24 * 1024 * 1024
        ):
            raise RestoreError("Goi phuc hoi rong hoac qua lon.")

        try:
            point = json.loads(config_text)

            if not isinstance(point, dict):
                raise ValueError("Sai cau truc")

            if (
                point.get("schema_version") != 1
                or point.get("kind") != "mikrotik_native"
                or point.get("encrypted") is not True
            ):
                raise ValueError("Sai loai ban sao")

            if (
                point.get("device_name") != self.name
                or point.get("management_ip") != self.host
            ):
                raise ValueError("Ban sao khac thiet bi")

            data = base64.b64decode(
                point["binary_base64"],
                validate=True,
            )

            if (
                not 0 < len(data) <= 16 * 1024 * 1024
                or len(data) != point["size_bytes"]
                or hashlib.sha256(data).hexdigest() != point["sha256"]
            ):
                raise ValueError("Du lieu ban sao khong khop")

        except Exception:
            raise RestoreError(
                "Goi phuc hoi khong hop le. "
                "Phai dung ket qua create_restore_point(), "
                "khong dung ban /export."
            ) from None

        password = os.getenv(
            f"{self._info.credential_profile}_BACKUP_PASSWORD"
        )

        if not password:
            raise RestoreError("Thieu bien moi truong BACKUP_PASSWORD.")

        remote_file = f"oop_load_{uuid4().hex}.backup"
        stage = "kiem tra thiet bi"

        try:
            hostname = self.send_command(
                ":put [/system identity get name]"
            ).strip()
            version = self.send_command(
                ":put [/system resource get version]"
            ).strip()

            if (
                hostname != point.get("hostname")
                or version != point.get("routeros_version")
            ):
                raise RestoreError(
                    "Hostname hoac RouterOS khac ban sao."
                )

            before_uptime = self._read_uptime_seconds()

            if before_uptime < 30:
                raise RestoreError(
                    "MT1 vua khoi dong. Cho uptime tren 30 giay roi thu."
                )

            stage = "tai va xac minh file"
            ssh_client = self._connection.remote_conn_pre

            with ssh_client.open_sftp() as sftp:
                sftp.get_channel().settimeout(60)

                with sftp.open(remote_file, "wb") as remote:
                    remote.write(data)

                if sftp.stat(remote_file).st_size != len(data):
                    raise RestoreError("Dung luong file tai len khong khop.")

                with sftp.open(remote_file, "rb") as remote:
                    uploaded = remote.read(16 * 1024 * 1024 + 1)

                if hashlib.sha256(uploaded).hexdigest() != point["sha256"]:
                    raise RestoreError("SHA256 file tai len khong khop.")

            stage = "yeu cau khoi phuc"
            command = (
                f"/system backup load name={remote_file} "
                f"password={self._quote_routeros(password)}"
            )

            response = self._connection.send_command_timing(
                command,
                read_timeout=30,
                last_read=1,
                strip_prompt=False,
            )

            if not re.search(
                r"restore.*reboot",
                response,
                flags=re.IGNORECASE | re.DOTALL,
            ):
                raise RestoreError(
                    "Khong nhan duoc cau hoi xac nhan restore/reboot. "
                    "Chua gui xac nhan."
                )

            stage = "xac nhan va cho khoi dong lai"

            try:
                response = self._connection.send_command_timing(
                    "y",
                    read_timeout=15,
                    last_read=1,
                    strip_prompt=False,
                )
            except Exception:
                # Mat SSH co the do reboot; chua coi la thanh cong.
                response = ""

            if re.search(
                r"(?im)^\s*(?:failure:|error:|not enough permissions)",
                response,
            ):
                raise RestoreError("Router tu choi khoi phuc.")

        except RestoreError:
            raise

        except Exception as error:
            raise RestoreError(
                f"Loi tai buoc '{stage}': {type(error).__name__}. "
                "Kiem tra console MT1."
            ) from None

        finally:
            try:
                self.disconnect()
            except Exception:
                pass

        time.sleep(5)
        deadline = time.monotonic() + 180

        while time.monotonic() < deadline:
            try:
                self.connect()
                after_uptime = self._read_uptime_seconds()

                if after_uptime < before_uptime:
                    actual_hostname = self.send_command(
                        ":put [/system identity get name]"
                    ).strip()

                    if actual_hostname != point["hostname"]:
                        raise RestoreError(
                            "Hostname sau reboot khong khop."
                        )

                    return {
                        "device": self.name,
                        "file_verified": True,
                        "reboot_observed": True,
                        "reconnected": True,
                        "post_checks_required": True,
                    }

            except RestoreError:
                raise

            except Exception:
                pass

            try:
                self.disconnect()
            except Exception:
                pass

            time.sleep(3)

        raise RestoreError(
            "Chua xac nhan duoc reboot va ket noi lai trong thoi gian cho. "
            "Trang thai khoi phuc chua xac dinh; kiem tra console MT1."
        )

    def verify_config(self, config_text, checks):
        """Xác minh checks được hỗ trợ; không coi thiếu dữ liệu là đạt."""
        from app.verification import verify_extended

        return verify_extended(self, config_text, checks, self._verify_basic, "mikrotik_routeros")

    def _verify_basic(self, config_text, checks):
        from ipaddress import IPv4Address

        from app.contracts import VerificationResult

        if not isinstance(config_text, str):
            raise VerificationError("config_text phai la chuoi.")

        if not isinstance(checks, dict) or not checks:
            raise VerificationError("checks phai la dict khong rong.")

        if set(checks) - {"interfaces", "ping"}:
            raise VerificationError("Co loai kiem tra chua ho tro.")

        interfaces = checks.get("interfaces", {})

        if not isinstance(interfaces, dict):
            raise VerificationError("interfaces phai la dict.")

        for name, expected in interfaces.items():
            if not isinstance(name, str) or not name.strip():
                raise VerificationError("Ten interface khong hop le.")

            if not isinstance(expected, dict) or not expected:
                raise VerificationError("Ky vong interface khong hop le.")

            if set(expected) - {"ip_address", "status", "protocol"}:
                raise VerificationError("Truong interface chua ho tro.")

            if not all(isinstance(value, str) for value in expected.values()):
                raise VerificationError("Gia tri ky vong phai la chuoi.")

        ping = checks.get("ping")
        target = source = None
        minimum = 100

        if ping is not None:
            if not isinstance(ping, dict):
                raise VerificationError("ping phai la dict.")

            if set(ping) - {"target", "source", "min_success_percent"}:
                raise VerificationError("Truong ping chua ho tro.")

            try:
                target = str(IPv4Address(ping.get("target")))

                if ping.get("source") is not None:
                    source = str(IPv4Address(ping["source"]))

            except (ValueError, TypeError) as error:
                raise VerificationError(
                    "Dia chi ping phai la IPv4 hop le."
                ) from error

            minimum = ping.get("min_success_percent", 100)

            if type(minimum) is not int or not 0 <= minimum <= 100:
                raise VerificationError("Nguong ping phai tu 0 den 100.")

        if not interfaces and ping is None:
            raise VerificationError("Khong co dieu kien can kiem tra.")

        results = {}
        details = []

        if interfaces:
            try:
                facts = self.get_facts()
                actual_ports = {
                    port["name"]: port
                    for port in facts["interfaces"]
                }

                for name, expected in interfaces.items():
                    actual = actual_ports.get(name, {})

                    for field, value in expected.items():
                        key = f"{name}.{field}"
                        actual_value = actual.get(field)
                        results[key] = actual_value == value
                        details.append(
                            f"{key}: expected={value}, actual={actual_value}"
                        )

            except (DeviceCommandError, DeviceConnectionError) as error:
                results["interfaces_collection"] = False
                details.append(
                    f"Loi thu thap interface: {type(error).__name__}"
                )

        if ping is not None:
            command = f"/ping address={target} count=5"

            if source is not None:
                command += f" src-address={source}"

            try:
                output = self.send_command(command)
                summaries = re.findall(
                    r"sent=(\d+)\s+received=(\d+)\s+"
                    r"packet-loss=(\d+(?:\.\d+)?)%",
                    output,
                )

                if not summaries:
                    results["ping"] = False
                    details.append("Khong doc duoc tong ket ping.")

                else:
                    sent, received, loss = summaries[-1]
                    sent = int(sent)
                    received = int(received)
                    loss = float(loss)

                    valid = (
                        sent == 5
                        and 0 <= received <= sent
                        and 0 <= loss <= 100
                    )
                    success = received * 100 / sent if sent else 0

                    results["ping"] = valid and success >= minimum
                    details.append(
                        f"Ping {target}: {success:g}%, "
                        f"required>={minimum}%"
                    )

            except (DeviceCommandError, DeviceConnectionError) as error:
                results["ping"] = False
                details.append(f"Loi ping: {type(error).__name__}")

        return VerificationResult(
            passed=bool(results) and all(results.values()),
            details=details,
            checks=results,
        )

    def _collect_section(self, collector):
        try:
            data = collector()

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

    def _read_cpu(self):
        output = self.send_command(
            ":put [/system resource get cpu-load]"
        )
        percent = int(output.strip())

        return {
            "usage_percent": percent,
            "valid": 0 <= percent <= 100,
        }

    def _read_memory(self):
        total = int(self.send_command(
            ":put [/system resource get total-memory]"
        ).strip())

        free = int(self.send_command(
            ":put [/system resource get free-memory]"
        ).strip())

        valid = total > 0 and 0 <= free <= total
        used = total - free

        return {
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "used_percent": (
                round(used * 100 / total, 2)
                if valid else None
            ),
            "valid": valid,
        }

    def _get_extra_facts(self):
        return {
            "routing_table": self._collect_section(
                lambda: self._read_rows("/ip route")
            ),
            "arp_table": self._collect_section(
                lambda: self._read_rows("/ip arp")
            ),
            "neighbors": self._collect_section(
                lambda: self._read_rows("/ip neighbor")
            ),
            "cpu": self._collect_section(self._read_cpu),
            "memory": self._collect_section(self._read_memory),
        }

    @staticmethod
    def _quote_routeros(value):
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("$", "\\$")
            .replace("\r", "\\r")
            .replace("\n", "\\n")
        )
        return f'"{escaped}"'

    def create_restore_point(self):
        """Tạo và tải bản native mã hóa, trả gói JSON có metadata và SHA256."""
        import base64
        import hashlib
        import os
        from uuid import uuid4

        from app.contracts import BackupError

        if self._connection is None:
            raise DeviceConnectionError("Chua ket noi thiet bi.")

        password = os.getenv(
            f"{self._info.credential_profile}_BACKUP_PASSWORD"
        )

        if not password:
            raise BackupError("Thieu bien moi truong BACKUP_PASSWORD.")

        remote_base = f"oop_native_{uuid4().hex}"
        remote_file = f"{remote_base}.backup"

        try:
            hostname = self.send_command(
                ":put [/system identity get name]"
            ).strip()

            version = self.send_command(
                ":put [/system resource get version]"
            ).strip()

            if not hostname or not version:
                raise BackupError("Thieu hostname hoac phien ban.")

            command = (
                f"/system backup save name={remote_base} "
                f"password={self._quote_routeros(password)} "
                "encryption=aes-sha256"
            )
            self.send_command(command)

            # Dung lai ket noi SSH da duoc Netmiko xac thuc.
            ssh_client = self._connection.remote_conn_pre

            with ssh_client.open_sftp() as sftp:
                sftp.get_channel().settimeout(60)
                size = sftp.stat(remote_file).st_size

                if size is None or not 0 < size <= 16 * 1024 * 1024:
                    raise BackupError("Kich thuoc ban sao khong hop le.")

                with sftp.open(remote_file, "rb") as remote:
                    data = remote.read(16 * 1024 * 1024 + 1)

            if len(data) != size:
                raise BackupError("Dung luong tai ve khong khop.")

            point = {
                "schema_version": 1,
                "kind": "mikrotik_native",
                "device_name": self.name,
                "management_ip": self.host,
                "hostname": hostname,
                "routeros_version": version,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "encrypted": True,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "binary_base64": base64.b64encode(data).decode("ascii"),
            }

            return json.dumps(point, ensure_ascii=False)

        except BackupError:
            raise

        except Exception as error:
            # Khong dua lenh co mat khau vao thong bao loi.
            raise BackupError(
                "Khong tao/tai duoc ban sao MikroTik: "
                f"{type(error).__name__}. "
                f"File tren router: {remote_file}"
            ) from None

    def _read_uptime_seconds(self):
        output = self.send_command("/system resource print")
        match = re.search(r"(?m)^\s*uptime:\s*(\S+)", output)

        if not match:
            raise DeviceCommandError("Khong doc duoc uptime.")

        value = match.group(1)

        if ":" in value:
            match = re.fullmatch(
                r"(?:(\d+)w)?(?:(\d+)d)?(\d+):(\d+):(\d+)",
                value,
            )
            factors = (604800, 86400, 3600, 60, 1)
        else:
            match = re.fullmatch(
                r"(?:(\d+)w)?(?:(\d+)d)?(?:(\d+)h)?"
                r"(?:(\d+)m)?(?:(\d+)s)?",
                value,
            )
            factors = (604800, 86400, 3600, 60, 1)

        if not match or not any(match.groups()):
            raise DeviceCommandError("Dinh dang uptime chua ho tro.")

        return sum(
            int(number or 0) * factor
            for number, factor in zip(match.groups(), factors)
        )
