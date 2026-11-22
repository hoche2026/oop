import unittest

from app.normalization import normalize_facts


class NormalizationTests(unittest.TestCase):
    def test_invalid_cpu_is_not_published_as_valid_value(self):
        original = {
            "cpu": {
                "status": "invalid",
                "data": {
                    "five_seconds_percent": 0,
                    "valid": False,
                },
                "error": None,
            },
        }

        result = normalize_facts(original)

        self.assertEqual(result["cpu"]["status"], "invalid")
        self.assertIsNone(result["cpu"]["data"]["usage_percent"])
        self.assertEqual(
            original["cpu"]["data"]["five_seconds_percent"],
            0,
        )

    def test_cisco_memory_uses_processor_pool_only(self):
        original = {
            "memory": {
                "status": "ok",
                "data": {
                    "valid": True,
                    "pools": [
                        {
                            "name": "Processor",
                            "total_bytes": 100,
                            "used_bytes": 40,
                            "free_bytes": 60,
                            "valid": True,
                        },
                        {
                            "name": "I/O",
                            "total_bytes": 50,
                            "used_bytes": 10,
                            "free_bytes": 40,
                            "valid": True,
                        },
                    ],
                },
                "error": None,
            },
        }

        result = normalize_facts(original)["memory"]["data"]

        self.assertEqual(result["total_bytes"], 100)
        self.assertEqual(result["used_percent"], 40)
        self.assertEqual(result["scope"], "processor_pool")

    def test_inconsistent_memory_is_invalid(self):
        original = {
            "memory": {
                "status": "ok",
                "data": {
                    "total_bytes": 100,
                    "used_bytes": 80,
                    "free_bytes": 60,
                    "valid": True,
                },
                "error": None,
            },
        }

        result = normalize_facts(original)["memory"]

        self.assertEqual(result["status"], "invalid")
        self.assertIsNone(result["data"]["used_percent"])


if __name__ == "__main__":
    unittest.main()
