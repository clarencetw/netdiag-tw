import importlib.util
import pathlib
import unittest
from unittest.mock import patch

MOD = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "netdiag.py"
spec = importlib.util.spec_from_file_location("netdiag", MOD)
netdiag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(netdiag)

class TestNetdiag(unittest.TestCase):
    def test_public_ips_exclude_nonpublic(self):
        fake = [
            (2, 1, 6, '', ('192.168.0.1', 443)),
            (2, 1, 6, '', ('127.0.0.1', 443)),
            (2, 1, 6, '', ('1.1.1.1', 443)),
            (10, 1, 6, '', ('::1', 443, 0, 0)),
        ]
        self.assertEqual([x[4][0] for x in netdiag.public_ips(fake)], ['1.1.1.1'])

    def test_summary_and_report_do_not_claim_isp_fault(self):
        samples = [
            {'service': 'Cloudflare', 'host': 'cloudflare.com', 'ok': True, 'http_status': 200,
             'dns_ms': 7, 'tcp_ms': 11, 'tls_ms': 14, 'http_response_ms': 50},
            {'service': 'Facebook', 'host': 'www.facebook.com', 'ok': False, 'error_stage': 'tcp'},
        ]
        raw = {'metadata': {'started':'2026-11-01T10:00:00+08:00', 'repeat':1},
               'summary': netdiag.summarize(samples)}
        report = netdiag.make_report(raw)
        self.assertIn('Facebook', report)
        self.assertIn('需與同時段其他服務', report)
        self.assertNotIn('ISP 已確認故障', report)
        self.assertEqual(raw['summary'][1]['success_ratio'], 0)

    def test_custom_host_requires_plain_dns_name(self):
        self.assertEqual(netdiag.valid_public_hostname('Example.COM'), 'example.com')
        for invalid in ('http://example.com/test', '127.0.0.1', 'site.com:443', 'bad\n.test'):
            with self.assertRaises(Exception):
                netdiag.valid_public_hostname(invalid)

    def test_dns_private_answer_blocked_without_connect(self):
        private = [(2, 1, 6, '', ('192.168.3.9', 443))]
        with patch.object(netdiag.socket, 'getaddrinfo', return_value=private):
            with patch.object(netdiag.socket, 'socket') as sock:
                response = netdiag.check_host('example.com')
                self.assertFalse(response['ok'])
                self.assertEqual(response['error_stage'], 'dns_policy')
                sock.assert_not_called()

    def test_empty_success_metrics_are_none(self):
        stats = netdiag.summarize([{'service':'X','host':'x.test','ok':False}])
        self.assertIsNone(stats[0]['stages_ms']['http_response_ms']['p50'])


    def test_probe_metadata_has_schema_not_a_release_version(self):
        self.assertFalse(hasattr(netdiag, "VERSION"))
        self.assertIn('http_response_ms', netdiag.summarize([
            {'service': 'Site','host': 'example.com', 'ok': True,
             'http_status': 200, 'http_response_ms': 23, 'elapsed_to_first_byte_ms': 80}
        ])[0]['stages_ms'])

    def test_report_distinguishes_http_response_from_packet_loss(self):
        raw = {'metadata': {'started': '2026-11-01T08:00:00+08:00'},
               'summary': netdiag.summarize([
                  {'service': 'Web', 'host': 'example.com', 'ok': True,
                   'http_status': 403, 'http_response_ms': 11}
               ])}
        report = netdiag.make_report(raw)
        self.assertIn('不是封包遺失率', report)
        self.assertIn('HTTP 回應時間', report)


    def test_mtr_host_without_public_probe_result_skips_mtr(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            output = str(pathlib.Path(tmp) / 'run.json')
            with patch.object(netdiag, 'check_host', return_value={'host': 'www.youtube.com', 'ok': False, 'error_stage': 'dns_policy'}):
                with patch.object(netdiag, 'mtr') as fake_mtr:
                    netdiag.main(['run', '--host', 'www.youtube.com', '--repeat', '1',
                                  '--pause', '0', '--mtr-host', 'www.youtube.com', '--output', output])
                    fake_mtr.assert_not_called()
                    evidence = __import__('json').loads(pathlib.Path(output).read_text())
                    self.assertIn('No validated public destination', evidence['mtr']['error'])

    def test_mtr_pins_to_observed_public_ip(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            output = str(pathlib.Path(tmp) / 'run.json')
            fake = {'host': 'www.youtube.com', 'ok': True, 'remote_ip': '1.1.1.1',
                    'http_status': 200, 'http_response_ms': 20}
            with patch.object(netdiag, 'check_host', return_value=fake):
                with patch.object(netdiag, 'mtr', return_value={'exit_code': 0}) as fake_mtr:
                    netdiag.main(['run', '--host', 'www.youtube.com', '--repeat', '1',
                                  '--pause', '0', '--mtr-host', 'www.youtube.com', '--output', output])
                    fake_mtr.assert_called_once_with('1.1.1.1', 20)

    def test_https_response_timing_does_not_include_dns_connection_setup(self):
        class FakeSocket:
            def settimeout(self, _): pass
            def connect(self, _): pass
            def close(self): pass
            def __enter__(self): return self
            def __exit__(self, *_): return False
        class FakeTls:
            calls = 0
            def settimeout(self, _): pass
            def sendall(self, data):
                assert b'Host: example.com' in data
            def recv(self, count):
                self.calls += 1
                return b'H' if self.calls == 1 else b'TTP/1.1 200 OK\r\n'
            def __enter__(self): return self
            def __exit__(self, *_): return False
        class FakeContext:
            def set_alpn_protocols(self, _): pass
            def wrap_socket(self, sock, server_hostname):
                assert server_hostname == 'example.com'
                return FakeTls()
        with patch.object(netdiag.socket, 'getaddrinfo', return_value=[
                (netdiag.socket.AF_INET, netdiag.socket.SOCK_STREAM, 6, '', ('1.1.1.1', 443))]):
            with patch.object(netdiag.socket, 'socket', return_value=FakeSocket()):
                with patch.object(netdiag.ssl, 'create_default_context', return_value=FakeContext()):
                    result = netdiag.check_host('example.com')
        self.assertTrue(result['ok'])
        self.assertEqual(result['http_status'], 200)
        self.assertEqual(result['remote_ip'], '1.1.1.1')
        self.assertIn('http_response_ms', result)
        self.assertIn('elapsed_to_first_byte_ms', result)
        self.assertGreaterEqual(result['elapsed_to_first_byte_ms'], result['http_response_ms'])

class TestSafetyAndBoundaries(unittest.TestCase):
    def test_gateway_loss_rejects_injected_or_invalid_values(self):
        for loss in ('<img src=x>', float('nan'), -1, 101, True):
            with self.assertRaises(ValueError):
                netdiag.validate_evidence({'schema_version':'1','metadata':{},'samples':[],
                                          'gateway_ping':{'icmp_loss_percent':loss}})

    def test_thread_start_failure_releases_capacity(self):
        with patch.object(netdiag.threading.Thread, 'start', side_effect=RuntimeError('no threads')):
            for _ in range(5):
                with self.assertRaisesRegex(netdiag.ResolverCapacityError, 'Cannot start'):
                    netdiag.resolve('example.com', netdiag.socket.AF_INET, 1)

    def test_dns_failure_does_not_create_a_socket(self):
        with patch.object(netdiag, 'resolve', side_effect=netdiag.socket.gaierror('no AAAA')):
            with patch.object(netdiag.socket, 'socket') as sock:
                result = netdiag.check_host('example.com', 'v6')
        self.assertEqual(result['error_stage'], 'dns')
        self.assertNotIn('dns_ms', result)
        sock.assert_not_called()

    def test_tls_certificate_failure_is_not_http_failure(self):
        from unittest.mock import MagicMock
        sock = MagicMock()
        context = MagicMock()
        context.wrap_socket.side_effect = netdiag.ssl.SSLCertVerificationError('bad certificate')
        addresses = [(netdiag.socket.AF_INET, 1, 6, '', ('1.1.1.1', 443))]
        with patch.object(netdiag, 'resolve', return_value=addresses), \
             patch.object(netdiag.socket, 'socket', return_value=sock), \
             patch.object(netdiag.ssl, 'create_default_context', return_value=context):
            result = netdiag.check_host('example.com')
        self.assertEqual(result['error_stage'], 'tls')
        self.assertEqual(result['error_type'], 'SSLCertVerificationError')
        self.assertNotIn('http_response_ms', result)

    def test_report_offline_creates_parent_and_preserves_raw(self):
        import json
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / 'input.json'
            target = pathlib.Path(tmp) / 'nested' / 'report.md'
            evidence = {'schema_version':'1','metadata':{},'samples':[]}
            source.write_text(json.dumps(evidence), encoding='utf-8')
            with patch.object(netdiag.socket, 'getaddrinfo') as dns:
                self.assertEqual(netdiag.main(['report', str(source), '--output', str(target)]), 0)
                dns.assert_not_called()
            self.assertTrue(target.exists())
            self.assertEqual(json.loads(source.read_text()), evidence)
            with self.assertRaises(SystemExit):
                netdiag.main(['report', str(source), '--output', str(source)])

    def test_non_global_multicast_and_duplicates_filtered(self):
        def addr(ip):
            return (netdiag.socket.AF_INET, 1, 6, '', (ip, 443))
        self.assertEqual(netdiag.public_ips([addr('224.0.0.1'), addr('1.1.1.1'), addr('1.1.1.1')]), [addr('1.1.1.1')])

    def test_dns_timeout_is_bounded_and_worker_can_finish(self):
        import threading
        release = threading.Event()
        def lookup(*args, **kwargs):
            release.wait(1)
            return []
        with patch.object(netdiag.socket, 'getaddrinfo', side_effect=lookup):
            try:
                with self.assertRaises(TimeoutError):
                    netdiag.resolve('example.com', netdiag.socket.AF_INET, .01)
            finally:
                release.set()

    def test_resolver_capacity_is_local_failure(self):
        with patch.object(netdiag, 'resolve', side_effect=netdiag.ResolverCapacityError('busy')):
            result = netdiag.check_host('example.com')
        self.assertEqual(result['error_stage'], 'local_resolver_capacity')

    def test_stage_metrics_include_completed_stages_of_failed_samples(self):
        summary = netdiag.summarize([
            {'service':'A','host':'a.test','ok':False,'dns_ms':12, 'error_stage':'tcp'},
            {'service':'A','host':'a.test','ok':True,'dns_ms':20,'http_status':403},
        ])[0]
        self.assertEqual(summary['stages_ms']['dns_ms']['p50'], 16)
        self.assertEqual(summary['stage_counts']['dns_ms'], 2)
        self.assertEqual(summary['success_ratio'], .5)
        self.assertEqual(summary['errors'], {'tcp':1})

    def test_output_collision_rejected_before_network(self):
        with patch.object(netdiag, 'check_host') as probe:
            with self.assertRaises(SystemExit):
                netdiag.main(['run', '--output', 'evidence.md'])
            probe.assert_not_called()

    def test_report_validates_schema_and_timing(self):
        for raw in ({}, {'schema_version':'99'}, {'schema_version':'1','metadata':{},'samples':[
            {'service':'A','host':'a.test','ok':False,'dns_ms':float('nan')}
        ]}):
            with self.assertRaises(ValueError):
                netdiag.validate_evidence(raw)

    def test_markdown_escapes_user_controlled_content(self):
        report = netdiag.make_report({'metadata':{'isp':'<script>|[x](url)\n# injected'},'samples':[]})
        self.assertNotIn('<script>', report)
        self.assertNotIn('\n# injected', report)
        self.assertNotIn('[x](url)', report)

    def test_mtr_uses_pinned_binary_family_and_ttl(self):
        import subprocess
        with patch.object(netdiag.shutil, 'which', return_value='/safe/mtr'):
            with patch.object(netdiag.subprocess, 'run', return_value=subprocess.CompletedProcess([],0,'','')) as run:
                result = netdiag.mtr('2606:4700:4700::1111', 2)
        command = run.call_args.args[0]
        self.assertEqual(command[0], '/safe/mtr')
        self.assertIn('-6', command)
        self.assertEqual(command[command.index('-m')+1], '30')
        self.assertEqual(result['max_ttl'], 30)

    def test_macos_ipv6_gateway_uses_ping6(self):
        import subprocess
        with patch.object(netdiag.platform, 'system', return_value='Darwin'):
            with patch.object(netdiag.shutil, 'which', return_value='/sbin/ping6') as which:
                with patch.object(netdiag.subprocess, 'run', return_value=subprocess.CompletedProcess([],0,'','')):
                    result = netdiag.ping('fe80::1%en0', 2)
        which.assert_called_once_with('ping6')
        self.assertEqual(result['requested_count'], 2)
        self.assertNotIn('sent', result)

if __name__ == '__main__':
    unittest.main()
