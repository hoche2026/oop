from ipaddress import ip_address, ip_network
from copy import deepcopy
from math import isfinite


def _normalize_section(section, converter):
    if section is None:
        return {
            "status": "not_collected",
            "data": None,
            "error": None,
        }

    if not isinstance(section, dict):
        return {
            "status": "error", "data": None,
            "error": "NormalizationError: section must be dict",
        }

    result = deepcopy(section)

    if result.get("status") not in {"ok", "invalid"}:
        return result

    try:
        data = converter(result["data"])

        if result["status"] == "invalid":
            data["valid"] = False

        if not data["valid"]:
            if "usage_percent" in data:
                data["usage_percent"] = None
            if "used_percent" in data:
                data["used_percent"] = None

        result["data"] = data
        result["status"] = "ok" if data["valid"] else "invalid"

    except (KeyError, TypeError, ValueError, StopIteration) as error:
        result = {
            "status": "error",
            "data": None,
            "error": f"NormalizationError: {type(error).__name__}",
        }

    return result


def _normalize_cpu(data):
    if not isinstance(data, dict):
        raise TypeError("CPU data must be dict")

    if "usage_percent" in data:
        value = data["usage_percent"]
        window = "device_reported"
    else:
        value = data["five_seconds_percent"]
        window = "five_seconds"

    valid_number = (
        type(value) in (int, float)
        and isfinite(value)
        and 0 <= value <= 100
    )
    valid = valid_number and data.get("valid", True) is True

    return {
        "usage_percent": value if valid else None,
        "sample_window": window,
        "valid": valid,
    }


def _normalize_memory(data):
    if not isinstance(data, dict):
        raise TypeError("Memory data must be dict")

    if "pools" in data:
        pools = data["pools"]
        if not isinstance(pools, list) or not all(
            isinstance(pool, dict) and isinstance(pool.get("name"), str)
            for pool in pools
        ):
            raise TypeError("Memory pools must be named dictionaries")
        selected = next(
            pool
            for pool in pools
            if pool.get("name", "").lower() == "processor"
        )
        scope = "processor_pool"
    else:
        selected = data
        scope = "system"

    total = selected["total_bytes"]
    used = selected["used_bytes"]
    free = selected["free_bytes"]

    valid = (
        all(type(value) is int for value in (total, used, free))
        and total > 0
        and 0 <= used <= total
        and 0 <= free <= total
        and used + free == total
        and selected.get("valid", True) is True
        and data.get("valid", True) is True
    )

    return {
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "used_percent": round(used * 100 / total, 2) if valid else None,
        "scope": scope,
        "valid": valid,
    }


def normalize_facts(facts):
    """Chuẩn hóa facts đa nền tảng, giữ None và trạng thái khi dữ liệu không hợp lệ."""
    if not isinstance(facts, dict):
        raise TypeError("facts must be dict")

    result = deepcopy(facts)
    result["normalization_version"] = 2

    result["cpu"] = _normalize_section(
        facts.get("cpu"),
        _normalize_cpu,
    )
    result["memory"] = _normalize_section(
        facts.get("memory"),
        _normalize_memory,
    )
    result["routing_table"] = _normalize_table(
        facts.get("routing_table"),
        _normalize_route,
    )
    result["arp_table"] = _normalize_table(
        facts.get("arp_table"),
        _normalize_arp,
    )

    neighbor_section = facts.get("neighbors")

    if neighbor_section is None:
        neighbor_section = facts.get("cdp_neighbors")

    result["neighbors"] = _normalize_table(
        neighbor_section,
        _normalize_neighbor,
    )

    return result


def _as_list(value):
    if value is None or value == "":
        return []

    if isinstance(value, list):
        return value

    return [value]


def _optional_int(value):
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        raise ValueError("Boolean is not an integer measurement")

    return int(value)


def _normalize_mac(value):
    if value is None or str(value).lower() in {"", "incomplete"}:
        return None

    text = str(value).lower()
    compact = text.replace(":", "").replace("-", "").replace(".", "")

    if len(compact) != 12 or any(
        character not in "0123456789abcdef"
        for character in compact
    ):
        raise ValueError("Invalid MAC address")

    return ":".join(
        compact[index:index + 2]
        for index in range(0, 12, 2)
    )


def _normalize_route(row):
    if "dst-address" in row:
        destination = row["dst-address"]
    else:
        destination = f'{row["network"]}/{row["prefix_length"]}'

    destination = str(ip_network(destination, strict=False))
    protocol_detail = row.get("protocol") or None

    if protocol_detail:
        code = str(protocol_detail).split()[0].strip("*+").upper()
        protocol = {
            "C": "connected",
            "L": "local",
            "S": "static",
            "O": "ospf",
            "B": "bgp",
            "D": "eigrp",
            "R": "rip",
        }.get(code, str(protocol_detail).lower())
    else:
        protocol = None

        for flag, name in (
            ("connect", "connected"),
            ("static", "static"),
            ("ospf", "ospf"),
            ("bgp", "bgp"),
            ("rip", "rip"),
        ):
            if row.get(flag) is True:
                protocol = name
                break

    next_hops = []

    if "gateway" in row:
        for gateway in _as_list(row["gateway"]):
            address, separator, interface = str(gateway).partition("%")

            try:
                address = str(ip_address(address))
                next_hops.append({
                    "address": address,
                    "interface": interface if separator else None,
                })
            except ValueError:
                if separator:
                    raise ValueError("Invalid gateway address")

                next_hops.append({
                    "address": None,
                    "interface": str(gateway),
                })

    else:
        address = row.get("nexthop_ip") or None
        interface = row.get("nexthop_if") or None

        if address:
            address = str(ip_address(address))

        if address or interface:
            next_hops.append({
                "address": address,
                "interface": interface,
            })

    return {
        "destination": destination,
        "protocol": protocol,
        "protocol_detail": protocol_detail,
        "next_hops": next_hops,
        "distance": _optional_int(row.get("distance")),
        "metric": _optional_int(row.get("metric")),
        "routing_table": (
            row.get("routing-table") or row.get("vrf") or None
        ),
        "active": (
            row["active"]
            if type(row.get("active")) is bool else None
        ),
    }


def _normalize_arp(row):
    address = row.get("ip_address") or row.get("address")

    if not address:
        raise ValueError("Missing ARP address")

    return {
        "ip_address": str(ip_address(address)),
        "mac_address": _normalize_mac(
            row.get("mac_address") or row.get("mac-address")
        ),
        "interface": row.get("interface") or None,
        "state": row.get("status") or None,
        "complete": (
            row["complete"]
            if type(row.get("complete")) is bool else None
        ),
    }


def _normalize_neighbor(row):
    name = row.get("neighbor_name") or row.get("identity")

    if not name:
        raise ValueError("Missing neighbor name")

    address = row.get("address4") or None

    if address:
        address = str(ip_address(address))

    local_interfaces = (
        row.get("local_interface")
        if "local_interface" in row
        else row.get("interface")
    )

    return {
        "device_name": name,
        "management_ip": address,
        "local_interfaces": [
            str(value) for value in _as_list(local_interfaces)
        ],
        "remote_interface": row.get("neighbor_interface") or None,
        "platform": row.get("platform") or None,
    }


def _normalize_table(section, converter):
    if section is None:
        return {
            "status": "not_collected",
            "data": None,
            "error": None,
        }

    if not isinstance(section, dict):
        return {
            "status": "error", "data": None,
            "error": "NormalizationError: section must be dict",
        }

    result = deepcopy(section)

    if result.get("status") not in {"ok", "empty", "invalid"}:
        return result

    try:
        rows = result["data"]

        if not isinstance(rows, list) or not all(
            isinstance(row, dict) for row in rows
        ):
            raise TypeError("Table must contain dictionaries")

        result["data"] = [converter(row) for row in rows]

        if result["status"] != "invalid":
            result["status"] = "ok" if result["data"] else "empty"

    except (KeyError, TypeError, ValueError) as error:
        result = {
            "status": "error",
            "data": None,
            "error": f"NormalizationError: {type(error).__name__}",
        }

    return result
