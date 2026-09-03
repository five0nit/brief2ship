import socket
import unittest

from brief2ship.errors import PolicyError
from brief2ship.safety import normalize_url, same_origin, validate_url


def resolver(*addresses: str):
    def inner(host, port, type=socket.SOCK_STREAM):  # noqa: A002, ARG001
        return [(socket.AF_INET6 if ":" in value else socket.AF_INET, type, 6, "", (value, port)) for value in addresses]

    return inner


class SafetyTests(unittest.TestCase):
    def test_normalizes_case_default_port_fragment_and_empty_path(self):
        self.assertEqual("https://example.com/?a=1", normalize_url(" HTTPS://Example.COM:443?a=1#x "))

    def test_normalizes_idna_host_and_unicode_path_for_http_transport(self):
        self.assertEqual(
            "https://xn--bcher-kva.example/%C3%BCber?q=%E2%9C%93",
            normalize_url("https://bücher.example/über?q=✓"),
        )

    def test_public_dns_target_allowed(self):
        result = validate_url("https://example.com/a", resolver=resolver("93.184.216.34"))
        self.assertEqual("https://example.com/a", result)

    def test_credentials_rejected(self):
        with self.assertRaisesRegex(PolicyError, "credentials"):
            validate_url("https://user:pass@example.com", resolver=resolver("93.184.216.34"))

    def test_non_http_scheme_rejected(self):
        with self.assertRaisesRegex(PolicyError, "only http"):
            validate_url("file:///etc/passwd")

    def test_zero_and_out_of_range_ports_rejected(self):
        for url in ("https://example.com:0/", "https://example.com:65536/"):
            with self.subTest(url=url), self.assertRaises(PolicyError):
                validate_url(url, resolver=resolver("93.184.216.34"))

    def test_local_names_rejected(self):
        for url in ("http://localhost", "http://thing.local", "http://api.localhost"):
            with self.subTest(url=url), self.assertRaises(PolicyError):
                validate_url(url)

    def test_non_public_literal_addresses_rejected(self):
        for value in ("127.0.0.1", "10.0.0.1", "169.254.1.1", "0.0.0.0", "224.0.0.1", "192.0.2.1", "::1", "fe80::1"):
            host = f"[{value}]" if ":" in value else value
            with self.subTest(value=value), self.assertRaises(PolicyError):
                validate_url(f"http://{host}/")

    def test_mixed_dns_answer_fails_closed(self):
        with self.assertRaisesRegex(PolicyError, "blocked address"):
            validate_url("https://example.com", resolver=resolver("93.184.216.34", "127.0.0.1"))

    def test_private_target_requires_explicit_override(self):
        self.assertEqual("http://127.0.0.1/", validate_url("http://127.0.0.1", allow_private=True))

    def test_same_origin_normalizes_default_ports(self):
        self.assertTrue(same_origin("https://example.com/a", "https://example.com:443/b"))
        self.assertFalse(same_origin("https://example.com", "http://example.com"))


if __name__ == "__main__":
    unittest.main()
