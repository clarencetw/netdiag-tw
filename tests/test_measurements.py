"""Deterministic timing and artifact contracts; no network or external tools."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("netdiag_metrics", ROOT / "scripts/netdiag.py")
netdiag = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(netdiag)


class MeasurementContracts(unittest.TestCase):
    def test_exact_timing_boundaries_include_local_setup_and_exclude_send_from_http_wait(self):
        clock = [0.0]

        class Socket:
            def settimeout(self, _): pass
            def connect(self, _): clock[0] += .020
            def __enter__(self): return self
            def __exit__(self, *_): pass

        class TLS(Socket):
            data = b"HTTP/1.1 200 OK\r\n"
            def sendall(self, _): clock[0] += .050
            def recv(self, count):
                if count == 1:
                    clock[0] += .060
                value, self.data = self.data[:count], self.data[count:]
                return value

        class Context:
            def set_alpn_protocols(self, _): pass
            def wrap_socket(self, *_args, **_kwargs):
                clock[0] += .040
                return TLS()

        def resolver(*_):
            clock[0] += .010
            return [(netdiag.socket.AF_INET, 1, 6, '', ('1.1.1.1', 443))]

        def context():
            clock[0] += .030
            return Context()

        with patch.object(netdiag, 'resolve', side_effect=resolver), \
             patch.object(netdiag.socket, 'socket', return_value=Socket()), \
             patch.object(netdiag.ssl, 'create_default_context', side_effect=context), \
             patch.object(netdiag.time, 'monotonic', side_effect=lambda: clock[0]):
            result = netdiag.check_host('example.com')
        self.assertTrue(result['ok'])
        self.assertEqual([result[k] for k in ('dns_ms', 'tcp_ms', 'tls_ms', 'http_response_ms', 'elapsed_to_first_byte_ms')],
                         [10.0, 20.0, 40.0, 60.0, 210.0])

    def test_tcp_attempts_are_capped_and_preserve_failure_reason(self):
        import errno
        addresses = [(netdiag.socket.AF_INET, 1, 6, '', (f'1.1.1.{i}', 443)) for i in range(1, 7)]
        with patch.object(netdiag, 'resolve', return_value=addresses), \
             patch.object(netdiag.socket, 'socket', side_effect=OSError(errno.ENETUNREACH, 'network unreachable')) as sock:
            result = netdiag.check_host('example.com')
        self.assertEqual(sock.call_count, 4)
        self.assertEqual(result['error_stage'], 'tcp')
        self.assertEqual(result['tcp_attempts'][0]['errno_name'], 'ENETUNREACH')

    def test_nearest_rank_p95_and_even_median(self):
        self.assertEqual(netdiag.quantiles(list(range(1, 21))), {'p50': 10.5, 'p95': 19})

    def test_checked_in_synthetic_evidence_and_report_match(self):
        raw = json.loads((ROOT / 'examples/SYNTHETIC-RESULT.json').read_text(encoding='utf-8'))
        netdiag.validate_evidence(raw)
        self.assertTrue(raw['synthetic'])
        self.assertEqual(raw['summary'], netdiag.summarize(raw['samples']))
        self.assertEqual((ROOT / 'examples/SYNTHETIC-REPORT.md').read_text(encoding='utf-8'), netdiag.make_report(raw))

    def test_windows_ping_does_not_invent_loss_from_localized_output(self):
        with patch.object(netdiag.platform, 'system', return_value='Windows'), \
             patch.object(netdiag.shutil, 'which', return_value='ping.exe'), \
             patch.object(netdiag.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '已收到 = 2', '')) as run:
            result = netdiag.ping('192.168.1.1', 2)
        self.assertEqual(run.call_args.args[0], ['ping.exe', '-n', '2', '-w', '1000', '192.168.1.1'])
        self.assertIsNone(result['icmp_loss_percent'])


if __name__ == '__main__':
    unittest.main()
