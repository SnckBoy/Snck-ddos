import asyncio
import unittest

import command_center as cc


class TargetValidationTests(unittest.TestCase):
    def setUp(self):
        cc.ALLOWED_HOSTS.add("status.example.com")

    def test_loopback_local_dev_port_is_allowed(self):
        self.assertEqual(
            cc.validate_target("http://127.0.0.1:8000/health"),
            "http://127.0.0.1:8000/health",
        )

    def test_exact_allowlisted_public_host_is_allowed(self):
        self.assertEqual(
            cc.validate_target("https://status.example.com/health"),
            "https://status.example.com/health",
        )

    def test_unknown_host_is_rejected(self):
        with self.assertRaises(cc.HTTPException) as error:
            cc.validate_target("https://not-allowed.example/health")
        self.assertEqual(error.exception.status_code, 403)

    def test_public_nonstandard_port_is_rejected(self):
        with self.assertRaises(cc.HTTPException) as error:
            cc.validate_target("https://status.example.com:8443/health")
        self.assertEqual(error.exception.status_code, 400)

    def test_embedded_credentials_are_rejected(self):
        with self.assertRaises(cc.HTTPException):
            cc.validate_target("https://user:pass@status.example.com/health")


class ResolverTests(unittest.TestCase):
    def test_loopback_ip_is_allowed_for_local_testing(self):
        result = asyncio.run(cc.SafeResolver().resolve("127.0.0.1", 8000))
        self.assertEqual(result[0]["host"], "127.0.0.1")

    def test_public_ip_is_allowed_by_resolver(self):
        result = asyncio.run(cc.SafeResolver().resolve("8.8.8.8", 443))
        self.assertEqual(result[0]["host"], "8.8.8.8")

    def test_documentation_ip_is_rejected(self):
        with self.assertRaises(OSError):
            asyncio.run(cc.SafeResolver().resolve("192.0.2.1", 80))


class ConfigLimitTests(unittest.TestCase):
    def test_rate_worker_and_duration_limits(self):
        with self.assertRaises(Exception):
            cc.TestConfig(target="http://localhost/health", rate=11)
        with self.assertRaises(Exception):
            cc.TestConfig(target="http://localhost/health", workers=6)
        with self.assertRaises(Exception):
            cc.TestConfig(target="http://localhost/health", duration=61)

    def test_only_get_and_head_are_allowed(self):
        with self.assertRaises(Exception):
            cc.TestConfig(target="http://localhost/health", method="POST")


if __name__ == "__main__":
    unittest.main()
