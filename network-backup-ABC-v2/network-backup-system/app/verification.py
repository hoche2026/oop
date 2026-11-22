"""Xác minh mở rộng; kết quả có tên tiêu chí, không chứa cấu hình/bí mật."""
from ipaddress import IPv4Address, IPv4Network
import re

from app.comparison import comparison_lines
from app.contracts import VerificationError, VerificationResult

BASIC = {'interfaces', 'ping'}
COMMON = {'config_match', 'config_lines', 'config_absent'}
CISCO = {'interface_descriptions', 'ospf_neighbors', 'ospf_routes'}
MIKROTIK = {'interface_comments'}


def validate_extended(checks, supported):
    """Kiểm tra tên, kiểu dữ liệu và giá trị checks trước khi gửi lệnh."""
    if not isinstance(checks, dict) or not checks or set(checks) - (BASIC | COMMON | supported):
        raise VerificationError('Checks rong hoac co tieu chi chua ho tro.')
    if 'config_match' in checks and checks['config_match'] is not True:
        raise VerificationError('config_match chi nhan true.')
    for key in ('config_lines', 'config_absent', 'ospf_neighbors', 'ospf_routes'):
        if key not in checks:
            continue
        value = checks[key]
        if (not isinstance(value, list) or not value
                or any(not isinstance(x, str) or not x.strip() or '\n' in x or '\r' in x for x in value)):
            raise VerificationError('Danh sach checks khong hop le.')
        if len(set(value)) != len(value):
            raise VerificationError('Checks khong duoc lap.')
        try:
            if key == 'ospf_neighbors':
                for item in value:
                    IPv4Address(item)
            if key == 'ospf_routes':
                for item in value:
                    IPv4Network(item, strict=True)
        except ValueError as exc:
            raise VerificationError('Dia chi OSPF khong hop le.') from exc
    for key in ('interface_descriptions', 'interface_comments'):
        if key not in checks:
            continue
        if not isinstance(checks[key], dict) or not checks[key]:
            raise VerificationError(
                'Checks interface phai la mapping khong rong.')
        for name, value in checks[key].items():
            if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9/_.:-]*', name)
                    or not isinstance(value, str) or '\n' in value or '\r' in value):
                raise VerificationError('Ten/gia tri interface khong hop le.')


def required_criteria(checks):
    """Cùng schema khóa kết quả cho cả A/B/C, không suy ra đạt từ dict không rỗng."""
    keys = {f'{name}.{field}' for name, values in checks.get('interfaces', {}).items()
            for field in values}
    if checks.get('ping') is not None:
        keys.add('ping')
    if checks.get('config_match') is True:
        keys.add('config_match')
    for key in ('config_lines', 'config_absent', 'ospf_neighbors', 'ospf_routes'):
        keys.update(f'{key}.{index}' for index,
                    _ in enumerate(checks.get(key, [])))
    for key in ('interface_descriptions', 'interface_comments'):
        keys.update(f'{key}.{name}' for name in checks.get(key, {}))
    return keys


def verify_extended(device, config_text, checks, basic_verify, platform):
    """Kết hợp xác minh cơ bản với checks cấu hình và giao thức theo nền tảng."""
    supported = CISCO if platform == 'cisco_ios' else MIKROTIK
    validate_extended(checks, supported)
    if not isinstance(config_text, str):
        raise VerificationError('config_text phai la chuoi.')
    basic = {key: value for key, value in checks.items() if key in BASIC}
    initial = basic_verify(
        config_text, basic) if basic else VerificationResult(True, [], {})
    results = dict(initial.checks)
    details = list(initial.details)

    def collect(key, callback):
        """Thu một tiêu chí, chuyển lỗi I/O thành kết quả kiểm tra thất bại."""
        try:
            passed = bool(callback())
        except Exception as exc:
            passed = False
            details.append(f'{key}: collection_error={type(exc).__name__}')
        results[key] = passed
        details.append(f'{key}: {"PASS" if passed else "FAIL"}')

    need_config = any(key in checks for key in COMMON |
                      {'interface_descriptions'})
    running = None
    if need_config:
        try:
            running = device.backup_config()
        except Exception:
            running = None
    if checks.get('config_match') is True:
        collect('config_match', lambda: running is not None
                and comparison_lines(config_text) == comparison_lines(running))
    for key, expected_present in (('config_lines', True), ('config_absent', False)):
        lines = {line.strip() for line in running.splitlines()
                 } if running is not None else set()
        for index, line in enumerate(checks.get(key, [])):
            collect(f'{key}.{index}', lambda line=line, want=expected_present:
                    running is not None and ((line.strip() in lines) == want))
    if platform == 'cisco_ios':
        for name, value in checks.get('interface_descriptions', {}).items():
            def description(name=name, value=value):
                """Đối chiếu description trong đúng stanza interface Cisco."""
                if running is None:
                    return False
                stanza = re.search(r'^interface ' + re.escape(name)
                                   + r'\s*\n((?:[ \t].*\n?)*)', running, re.MULTILINE)
                if not stanza:
                    return False
                match = re.search(r'^\s+description(?: (.*))?$',
                                  stanza[1], re.MULTILINE)
                return (match.group(1) or '') == value if match else value == ''
            collect(f'interface_descriptions.{name}', description)
        neighbor_output = None
        if checks.get('ospf_neighbors'):
            try:
                neighbor_output = device.send_command('show ip ospf neighbor')
            except Exception:
                pass
        for index, router_id in enumerate(checks.get('ospf_neighbors', [])):
            collect(f'ospf_neighbors.{index}', lambda router_id=router_id:
                    neighbor_output is not None and any(
                        re.match(r'^\s*' + re.escape(router_id) + r'\s+', line)
                        and re.search(r'\bFULL(?:/\S*)?\b', line)
                        for line in neighbor_output.splitlines()))
        for index, prefix in enumerate(checks.get('ospf_routes', [])):
            network = IPv4Network(prefix)

            def route(network=network):
                """Kiểm tra prefix chính xác được học qua OSPF."""
                output = device.send_command(
                    f'show ip route {network.network_address} {network.netmask}')
                return (re.search(r'Routing entry for\s+' + re.escape(str(network)) + r'(?:\s|$)', output)
                        and re.search(r'Known via "ospf \d+"', output))
            collect(f'ospf_routes.{index}', route)
    else:
        rows = None
        if checks.get('interface_comments'):
            try:
                rows = {row['name']: row.get('comment', '')
                        for row in device._read_rows('/interface')}
            except Exception:
                pass
        for name, value in checks.get('interface_comments', {}).items():
            collect(f'interface_comments.{name}', lambda name=name, value=value:
                    rows is not None and name in rows and rows[name] == value)
    return VerificationResult(bool(results) and all(results.values()), details, results)
