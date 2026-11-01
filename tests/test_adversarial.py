"""Offline counterexamples: never resolve or connect to a real destination."""
import importlib.util
import pathlib
import socket
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "netdiag_adversarial", pathlib.Path(__file__).resolve().parents[1] / "scripts/netdiag.py"
)
netdiag = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(netdiag)


class FakeSocket:
    def settimeout(self, _): pass
    def connect(self, _): pass
    def close(self): pass
    def __enter__(self): return self
    def __exit__(self, *_): return False


class FakeTLS(FakeSocket):
    def __init__(self, response):
        self.response = response

    def sendall(self, data):
        assert data.startswith(b"GET / HTTP/1.1\r\n")

    def recv(self, count):
        chunk, self.response = self.response[:count], self.response[count:]
        return chunk


class FakeContext:
    def __init__(self, response): self.response = response
    def set_alpn_protocols(self, _): pass
    def wrap_socket(self, sock, server_hostname): return FakeTLS(self.response)


class AdversarialNetworkTests(unittest.TestCase):
    def probe(self, response, tls=None):
        answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 443))]
        context = FakeContext(response)
        if tls is not None:
            context.wrap_socket = lambda sock, server_hostname: tls
        with patch.object(netdiag.socket, "getaddrinfo", return_value=answers), \
             patch.object(netdiag.socket, "socket", return_value=FakeSocket()), \
             patch.object(netdiag.ssl, "create_default_context", return_value=context):
            return netdiag.check_host("example.com")

    def test_eof_is_not_a_first_response_byte(self):
        result = self.probe(b"")
        self.assertFalse(result["ok"])
        self.assertNotIn("http_response_ms", result)
        self.assertNotIn("elapsed_to_first_byte_ms", result)

    def test_invalid_or_incomplete_status_lines_do_not_prove_http_response(self):
        for response in (b"HTTP/1.1 999 Invalid\r\n", b"HTTP/9 200 OK\r\n",
                         b"HTTP/1.1 200 OK", b"garbage\r\n"):
            with self.subTest(response=response):
                self.assertFalse(self.probe(response)["ok"])

    def test_informational_response_is_not_a_completed_http_exchange(self):
        for code in (100, 103):
            with self.subTest(code=code):
                result = self.probe(f"HTTP/1.1 {code} Interim\r\n\r\n".encode())
                self.assertFalse(result["ok"])
                self.assertEqual(result["error_stage"], "http")

    def test_early_hints_then_final_response_across_chunk_boundaries(self):
        response = (b"HTTP/1.1 103 Early Hints\r\nLink: </asset>\r\n\r\n"
                    b"HTTP/1.1 200 OK\r\n")
        for chunk_size in (1, 7, 512):
            class ChunkedTLS(FakeTLS):
                def recv(self, count):
                    return super().recv(min(count, chunk_size))
            with self.subTest(chunk_size=chunk_size):
                result = self.probe(response, tls=ChunkedTLS(response))
                self.assertTrue(result["ok"])
                self.assertEqual(result["http_status"], 200)
                self.assertEqual(result["informational_statuses"], [103])

    def test_informational_headers_share_one_total_byte_cap(self):
        for response in (
            b"HTTP/1.1 103 Hints\r\nX: " + b"a" * 4096 + b"\r\n\r\nHTTP/1.1 200 OK\r\n",
            b"HTTP/1.1 103 Hints\r\n\r\n" * 220 + b"HTTP/1.1 200 OK\r\n",
        ):
            tls = FakeTLS(response)
            result = self.probe(response, tls=tls)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error_stage"], "http")
            self.assertLessEqual(len(response) - len(tls.response), 4096)
            self.assertTrue(tls.response)

    def test_switching_protocols_is_not_supported_https_success(self):
        result = self.probe(b"HTTP/1.1 101 Switching Protocols\r\n\r\n")
        self.assertFalse(result["ok"])
        self.assertEqual(result["http_status"], 101)
        self.assertEqual(result["error_stage"], "http")
        self.assertEqual(result["error_type"], "UnsupportedProtocolSwitch")

    def test_slow_drip_cannot_reset_the_entire_http_deadline(self):
        clock = [0.0]
        calls = []

        class SlowTLS(FakeTLS):
            def recv(self, count):
                calls.append(count)
                clock[0] += 0.6
                return super().recv(1)

        class SlowContext(FakeContext):
            def wrap_socket(self, sock, server_hostname):
                return SlowTLS(self.response)

        answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 443))]
        with patch.object(netdiag.socket, "getaddrinfo", return_value=answers), \
             patch.object(netdiag.socket, "socket", return_value=FakeSocket()), \
             patch.object(netdiag.ssl, "create_default_context", return_value=SlowContext(b"HTTP/1.1 200 OK\r\n")), \
             patch.object(netdiag.time, "monotonic", side_effect=lambda: clock[0]):
            result = netdiag.check_host("example.com", timeout=1.0)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_stage"], "http")
        self.assertEqual(result["error_type"], "TimeoutError")
        self.assertLessEqual(len(calls), 2)

    def test_http_denial_still_proves_an_http_response(self):
        result = self.probe(b"HTTP/1.1 403 Forbidden\r\n\r\n")
        self.assertTrue(result["ok"])
        self.assertEqual(result["http_status"], 403)

    def test_ipv6_socket_unavailable_is_evidence_not_a_crash(self):
        answers = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700::1111", 443, 0, 0))]
        with patch.object(netdiag.socket, "getaddrinfo", return_value=answers), \
             patch.object(netdiag.socket, "socket", side_effect=OSError("Address family unavailable")):
            result = netdiag.check_host("example.com", family="v6")
        self.assertFalse(result["ok"])
        self.assertIn("error_stage", result)

    def test_empty_report_does_not_claim_success(self):
        report = netdiag.make_report({"metadata": {}, "samples": [], "summary": []})
        self.assertNotIn("本輪所有目標都有 HTTP 回應", report)

    def test_report_uses_samples_over_stale_summary(self):
        sample = {"service": "Control", "host": "example.com", "ok": False,
                  "error_stage": "tcp"}
        stale = netdiag.summarize([dict(sample, ok=True, http_status=200, http_response_ms=123)])
        report = netdiag.make_report({"metadata": {}, "samples": [sample], "summary": stale})
        self.assertIn("0/1", report)
        self.assertNotIn("123.0 / 123.0", report)


if __name__ == "__main__":
    unittest.main()
