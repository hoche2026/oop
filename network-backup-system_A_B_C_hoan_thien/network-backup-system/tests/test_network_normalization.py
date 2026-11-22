import unittest

from app.normalization import normalize_facts


def section(rows):
    return {"status": "ok", "data": rows, "error": None}


class NetworkNormalizationTests(unittest.TestCase):
    def test_connected_routes_share_structure(self):
        cisco = {
            "network": "192.168.241.0",
            "prefix_length": "24",
            "protocol": "C",
            "nexthop_ip": "",
            "nexthop_if": "FastEthernet0/0",
        }
        mikrotik = {
            "dst-address": "192.168.241.0/24",
            "connect": True,
            "gateway": "ether1",
            "distance": 0,
            "active": True,
        }

        results = [
            normalize_facts({
                "routing_table": section([row])
            })["routing_table"]["data"][0]
            for row in (cisco, mikrotik)
        ]

        self.assertEqual(set(results[0]), set(results[1]))

        for route in results:
            self.assertEqual(route["destination"], "192.168.241.0/24")
            self.assertEqual(route["protocol"], "connected")
            self.assertIsNone(route["next_hops"][0]["address"])

    def test_mac_formats_are_normalized(self):
        rows = [
            {
                "ip_address": "192.168.241.131",
                "mac_address": "000c.2921.664a",
                "interface": "FastEthernet0/0",
            },
            {
                "address": "192.168.241.131",
                "mac-address": "00:0C:29:21:66:4A",
                "interface": "ether1",
            },
        ]

        result = normalize_facts({
            "arp_table": section(rows)
        })["arp_table"]["data"]

        self.assertEqual(
            result[0]["mac_address"],
            result[1]["mac_address"],
        )

    def test_neighbor_does_not_invent_management_ip(self):
        result = normalize_facts({
            "cdp_neighbors": section([{
                "neighbor_name": "R2",
                "local_interface": "FastEthernet0/0",
                "neighbor_interface": "FastEthernet0/0",
                "platform": "7206VXR",
            }]),
        })["neighbors"]["data"][0]

        self.assertEqual(result["device_name"], "R2")
        self.assertIsNone(result["management_ip"])
        self.assertIsInstance(result["local_interfaces"], list)

    def test_empty_table_remains_empty(self):
        result = normalize_facts({
            "arp_table": section([])
        })["arp_table"]

        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["data"], [])

    def test_collection_error_is_preserved(self):
        original = {
            "status": "error",
            "data": None,
            "error": "Simulated collection failure",
        }

        result = normalize_facts({
            "routing_table": original
        })["routing_table"]

        self.assertEqual(result, original)


if __name__ == "__main__":
    unittest.main()
