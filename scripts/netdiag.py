#!/usr/bin/env python3
"""Local, bounded, evidence-first HTTPS network checks. Python 3.10+, stdlib only.

This is a starter probe, NOT a speed test, browser benchmark, video playback
measurement or proof of ISP/submarine-cable failure.
"""
from __future__ import annotations

import argparse
import datetime as dt
import errno
import ipaddress
import json
import math
from pathlib import Path
import platform
import re
import shutil
import socket
import ssl
import statistics
import queue
import threading
import subprocess
import sys
import time
from typing import Any

USER_AGENT = "netdiag-tw"
PRESETS: dict[str, list[tuple[str, str]]] = {
    "basic": [
        ("Cloudflare", "cloudflare.com"),
        ("Google", "www.google.com"),
        ("Facebook", "www.facebook.com"),
        ("YouTube", "www.youtube.com"),
        ("Netflix", "www.netflix.com"),
    ],
    "social": [
        ("Facebook", "www.facebook.com"),
        ("Instagram", "www.instagram.com"),
        ("Threads", "www.threads.net"),
        ("X", "x.com"),
    ],
    "video": [
        ("YouTube", "www.youtube.com"),
        ("Netflix", "www.netflix.com"),
        ("Twitch", "www.twitch.tv"),
    ],
    "developer": [
        ("GitHub", "github.com"),
        ("Cloudflare", "cloudflare.com"),
        ("Google", "www.google.com"),
    ],
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


# Timed-out OS resolver calls cannot be cancelled. Bound their number and use
# daemon workers so an unavailable resolver cannot prevent process exit.
_RESOLVER_SLOTS = threading.BoundedSemaphore(4)


class ResolverCapacityError(OSError):
    """Local capacity exhausted by timed-out system lookups."""


def resolve(host: str, af: int, timeout: float) -> list[tuple]:
    if not _RESOLVER_SLOTS.acquire(blocking=False):
        raise ResolverCapacityError("Resolver worker limit reached after pending lookups")
    results: queue.Queue = queue.Queue(maxsize=1)

    def worker():
        try:
            results.put((True, socket.getaddrinfo(host, 443, family=af, type=socket.SOCK_STREAM)))
        except Exception as exc:
            results.put((False, exc))
        finally:
            _RESOLVER_SLOTS.release()

    try:
        threading.Thread(target=worker, daemon=True).start()
    except RuntimeError as exc:
        _RESOLVER_SLOTS.release()
        raise ResolverCapacityError("Cannot start resolver worker") from exc
    try:
        ok, value = results.get(timeout=timeout)
    except queue.Empty as exc:
        raise TimeoutError("System resolver exceeded timeout; its OS lookup may still finish in background") from exc
    if not ok:
        raise value
    return value


def public_ips(addrs: list[tuple]) -> list[tuple]:
    """Use only unique global unicast addresses, never local/multicast targets."""
    result, seen = [], set()
    for item in addrs:
        try:
            ip = ipaddress.ip_address(item[4][0])
            if (item[0] in (socket.AF_INET, socket.AF_INET6) and ip.is_global
                    and not (ip.is_multicast or ip.is_reserved or ip.is_unspecified)
                    and (item[0], str(ip)) not in seen):
                seen.add((item[0], str(ip)))
                result.append(item)
        except (ValueError, IndexError):
            pass
    return result


def check_host(host: str, family: str = "auto", timeout: float = 5.0) -> dict[str, Any]:
    """One system lookup, up to four TCP attempts, verified TLS, one root GET.

    timeout bounds DNS wait, each TCP attempt, TLS, and the whole HTTP phase.
    No redirects are followed; at most 4096 response bytes are consumed.
    """
    host = valid_public_hostname(host)
    started = time.monotonic()
    result: dict[str, Any] = {
        "host": host, "at": now_iso(), "requested_family": family,
        "scope": "HTTPS/1.1 root-path reachability; not real page load, CDN video, or browser playback",
        "ok": False, "tcp_attempts": [],
    }
    af = {"auto": socket.AF_UNSPEC, "v4": socket.AF_INET, "v6": socket.AF_INET6}[family]
    try:
        answers = resolve(host, af, timeout)
        result["dns_ms"] = round((time.monotonic() - started) * 1000, 1)
        addrs = public_ips(answers)
        if not answers:
            result.update(error_stage="dns", error_type="NoAddress", error="No address for requested family")
            return result
        if not addrs:
            result.update(error_stage="dns_policy", error="DNS did not provide a publicly routable unicast address")
            return result
    except ResolverCapacityError as exc:
        result.update(error_stage="local_resolver_capacity", error_type=type(exc).__name__, error=str(exc))
        return result
    except (OSError, UnicodeError) as exc:
        result.update(error_stage="dns", error_type=type(exc).__name__, error=str(exc))
        return result

    for family_num, socktype, proto, _canon, sockaddr in addrs[:4]:
        s = None
        t0 = time.monotonic()
        attempt = {"ip": sockaddr[0], "ip_family": "IPv6" if family_num == socket.AF_INET6 else "IPv4"}
        result["tcp_attempts"].append(attempt)
        try:
            s = socket.socket(family_num, socktype, proto)
            s.settimeout(timeout)
            s.connect(sockaddr)
            result["tcp_ms"] = round((time.monotonic() - t0) * 1000, 1)
            attempt.update(ok=True, elapsed_ms=result["tcp_ms"])
            result.update(remote_ip=sockaddr[0], ip_family=attempt["ip_family"])
            break
        except OSError as exc:
            attempt.update(ok=False, error_type=type(exc).__name__,
                           errno=exc.errno, errno_name=errno.errorcode.get(exc.errno),
                           winerror=getattr(exc, "winerror", None),
                           elapsed_ms=round((time.monotonic() - t0) * 1000, 1))
            if s is not None:
                s.close()
    else:
        result.update(error_stage="tcp", error_type="ConnectionFailed", error="All bounded TCP attempts failed")
        return result

    stage = "tls"
    with s:
        try:
            ctx = ssl.create_default_context()
            ctx.set_alpn_protocols(["http/1.1"])
            t1 = time.monotonic()
            with ctx.wrap_socket(s, server_hostname=host) as wrapped:
                result["tls_ms"] = round((time.monotonic() - t1) * 1000, 1)
                stage = "http"
                deadline = time.monotonic() + timeout

                def remaining():
                    left = deadline - time.monotonic()
                    if left <= 0:
                        raise TimeoutError("HTTP phase deadline exceeded")
                    wrapped.settimeout(left)

                remaining()
                data = f"GET / HTTP/1.1\r\nHost: {host}\r\nUser-Agent: {USER_AGENT}\r\nAccept: */*\r\nConnection: close\r\n\r\n"
                wrapped.sendall(data.encode("ascii"))
                request_sent = time.monotonic()
                remaining()
                first_byte = wrapped.recv(1)
                if not first_byte:
                    raise OSError("EOF before first HTTP response byte")
                received = time.monotonic()
                result["http_response_ms"] = round((received - request_sent) * 1000, 1)
                result["elapsed_to_first_byte_ms"] = round((received - started) * 1000, 1)
                buffer = bytearray(first_byte)
                consumed = 1
                informational = []

                def read_until(marker):
                    nonlocal consumed
                    while marker not in buffer and consumed < 4096:
                        remaining()
                        chunk = wrapped.recv(min(512, 4096 - consumed))
                        if not chunk:
                            return False
                        buffer.extend(chunk)
                        consumed += len(chunk)
                    return marker in buffer

                while read_until(b"\r\n"):
                    status_line = bytes(buffer).split(b"\r\n", 1)[0]
                    match = re.fullmatch(rb"HTTP/1\.[01] ([1-5][0-9]{2})(?: [^\r\n]*)?", status_line)
                    if not match:
                        break
                    status = int(match.group(1))
                    result["http_status"] = status
                    if status >= 200:
                        result["ok"] = True
                        break
                    if status == 101:
                        result.update(error_type="UnsupportedProtocolSwitch", error="HTTP 101 protocol switching is not measured")
                        break
                    informational.append(status)
                    if not read_until(b"\r\n\r\n"):
                        break
                    end = buffer.index(b"\r\n\r\n") + 4
                    del buffer[:end]
                if informational:
                    result["informational_statuses"] = informational
                if not result["ok"]:
                    result["error_stage"] = "http"
                    result.setdefault("error_type", "InvalidStatusLine")
                    result.setdefault("error", "No complete final HTTP/1.x status line within 4096 response bytes")

        except (OSError, ssl.SSLError) as exc:
            result.update(error_stage=stage, error_type=type(exc).__name__, error=str(exc))
    return result


def valid_public_hostname(value: str) -> str:
    """Only domain names, never IPs, URLs, ports, or query strings."""
    if len(value) > 253 or not re.fullmatch(
        r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}", value
    ):
        raise argparse.ArgumentTypeError("Supply a public DNS hostname (no URL path, port, or IP)")
    return value.lower()


def safe_gateway(value: str) -> str:
    ip = ipaddress.ip_address(value)
    if ip.is_loopback or ip.is_multicast or ip.is_unspecified:
        raise argparse.ArgumentTypeError("Gateway must be a valid unicast address")
    return value


def ping(target: str, count: int) -> dict[str, Any]:
    """A manually selected gateway only; ICMP drops may reflect rate limiting."""
    is_win = platform.system().lower() == "windows"
    ping_name = "ping6" if platform.system() == "Darwin" and ipaddress.ip_address(target).version == 6 else "ping"
    binary = shutil.which(ping_name)
    if not binary:
        return {"target": target, "error": "ping executable is unavailable"}
    cmd = [binary, "-n", str(count), "-w", "1000", target] if is_win else [binary, "-c", str(count), target]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=min(count * 3 + 8, 120), check=False)
        raw = p.stdout[-12000:] + p.stderr[-2000:]
        # macOS/Linux English-statistics is common; avoid parsing localized
        # Windows summaries and therefore avoid inferring loss on those systems.
        loss_match = re.search(r"([0-9]+(?:\.[0-9]+)?)%\s+packet loss", raw, re.I)
        return {"target": target, "requested_count": count, "exit_code": p.returncode,
                "icmp_loss_percent": float(loss_match.group(1)) if loss_match else None,
                "raw": raw}
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"target": target, "error": f"{type(exc).__name__}: {exc}"}


def mtr(host: str, cycles: int) -> dict[str, Any]:
    binary = shutil.which("mtr")
    if not binary:
        return {"target": host, "error": "mtr is not installed; no automatic installation performed"}
    # Do not use positional target from user-provided free-form shell input.
    cmd = [binary, "-6" if ipaddress.ip_address(host).version == 6 else "-4",
           "-n", "-r", "-w", "-c", str(cycles), "-m", "30", "-T", "-P", "443", host]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=min(cycles * 3 + 30, 150), check=False)
        return {"target": host, "exit_code": p.returncode,
                "requested_cycles": cycles, "max_ttl": 30,
                "probe_type": "TCP/443 hop probing; ICMP time-exceeded may be suppressed",
                "raw": (p.stdout[-16000:] + p.stderr[-2000:])}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"target": host, "error": f"{type(exc).__name__}: {exc}"}


def quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"p50": None, "p95": None}
    nums = sorted(values)
    return {"p50": round(statistics.median(nums), 1),
            "p95": round(nums[max(0, math.ceil(0.95 * len(nums)) - 1)], 1)}


def summarize(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for name, host in dict.fromkeys((s["service"], s["host"]) for s in samples):
        current = [s for s in samples if s["service"] == name and s["host"] == host]
        success = [s for s in current if s.get("ok")]
        stages = {k: quantiles([float(s[k]) for s in current if isinstance(s.get(k), (int, float)) and not isinstance(s[k], bool) and math.isfinite(s[k]) and s[k] >= 0])
                  for k in ("dns_ms", "tcp_ms", "tls_ms", "http_response_ms", "elapsed_to_first_byte_ms")}
        output.append({"service": name, "host": host, "samples": len(current),
                       "https_responses": len(success), "success_ratio": round(len(success)/len(current), 3),
                       "stages_ms": stages,
                       "stage_counts": {k: sum(isinstance(s.get(k), (int, float)) and not isinstance(s[k], bool) and math.isfinite(s[k]) and s[k] >= 0 for s in current) for k in stages},
                       "errors": {stage: sum(s.get("error_stage") == stage for s in current) for stage in sorted({s["error_stage"] for s in current if s.get("error_stage")})},
                       "statuses": sorted({s["http_status"] for s in success if s.get("http_status")})})
    return output


def markdown_text(value: Any) -> str:
    value = str(value).replace("\r", " ").replace("\n", " ")
    return "".join(f"&#{ord(c)};" if c in "&<>|`[]*_\\" else c for c in value)


def make_report(raw: dict[str, Any]) -> str:
    meta = {k: markdown_text(v) for k, v in raw.get("metadata", {}).items()}
    summary = summarize(raw["samples"]) if "samples" in raw else raw.get("summary", [])
    lines = [
        "# 台灣固網診斷紀錄", "",
        f"- 量測時間：{meta.get('started', '未知')}",
        f"- ISP：{meta.get('isp') or '未填寫'}；申辦速率：{meta.get('plan') or '未填寫'}",
        f"- 連線方式：{meta.get('access') or '未填寫'}；使用環境：{meta.get('platform', '未知')}",
        f"- Address family：{meta.get('family', '未知')}；每站測試：{meta.get('repeat', '未知')} 次", "",
        "## HTTPS 入口可達性（不是完整網頁／影片效能）", "",
        "| 服務 | 網站 | 取得 HTTP 回應 | HTTP 狀態碼 | HTTP 回應時間 p50 / p95 (ms) |", "|---|---|---:|---|---:|",
    ]
    for s in summary:
        latency = s.get("stages_ms", {}).get("http_response_ms", {})
        p50, p95 = latency.get("p50"), latency.get("p95")
        timing = f"{p50} / {p95}" if p50 is not None else "無"
        statuses = ", ".join(str(code) for code in s.get("statuses", [])) or "無"
        lines.append(f"| {markdown_text(s['service'])} | {markdown_text(s['host'])} | {s['https_responses']}/{s['samples']} | {statuses} | {timing} |")
    lines.extend(["", "### 分階段量測（各階段有數值的樣本；不是只取 HTTPS 成功樣本）", "",
                  "| 服務 | 指標 | 有效樣本 | p50 / p95 (ms) |", "|---|---|---:|---:|"])
    error_lines = []
    for item in summary:
        for stage, values in item.get("stages_ms", {}).items():
            timing = f"{values['p50']} / {values['p95']}" if values.get('p50') is not None else "無"
            lines.append(f"| {markdown_text(item['service'])} | {stage} | {item.get('stage_counts', {}).get(stage, '未知')} | {timing} |")
        errors = item.get("errors", {})
        if errors:
            error_lines.append("\n失敗階段（" + markdown_text(item["service"]) + "）：" +
                         "、".join(f"{markdown_text(k)}={v}" for k, v in errors.items()) + "\n")
    lines.extend(error_lines)
    lines.extend(["", "## 客觀觀察與限制", ""])
    failing = [s for s in summary if s["https_responses"] < s["samples"]]
    if failing:
        lines.append("- 有 HTTPS 入口測試未取得有效最終 HTTP 狀態列：" + "、".join(markdown_text(s["service"]) for s in failing) + "。需與同時段其他服務、不同連線方式和 DNS/路由資料交叉驗證。")
    elif summary:
        lines.append("- 本輪所有目標都有 HTTP 回應；這不代表影片播放、下載速度、其他 CDN 或尖峰時段沒有問題。")
    if not summary:
        lines.append("- 沒有測量樣本，無法判斷連線狀態。")
    if any(s["samples"] < 10 for s in summary):
        lines.append("- 單站樣本少於 10 次，不能憑此推斷間歇性掉封包或 ISP 故障。")
    gateway = raw.get("gateway_ping")
    if gateway:
        lines.append(f"- 使用者指定閘道 ICMP 測試：{markdown_text(gateway.get('target') or '?')}；遺失比例：{markdown_text(gateway.get('icmp_loss_percent')) if gateway.get('icmp_loss_percent') is not None else '無法解析'}%。Router 可能限制 ICMP 回應。")
    if raw.get("mtr"):
        if raw["mtr"].get("exit_code") == 0:
            lines.append("- 已記錄 MTR TCP/443 路由；中間跳回應遺失不能直接判定是實際轉送封包遺失。原始輸出在 JSON。")
        else:
            lines.append("- MTR 未成功完成，請檢查是否安裝工具、平台權限及對方防火牆；不可使用這份 MTR 認定路由異常。")
    lines.extend(["- HTTP 回應時間是送出 HTTP/1.1 GET 後到收到第一個回應位元組，不含 DNS/TCP/TLS；`elapsed_to_first_byte_ms` 才包含整體建連過程。",
                  "- 首位元組可能屬於 1xx 暫時回應；各階段依有值樣本計算，請一起看有效樣本數、狀態碼與失敗數。",
                  "- DNS 計時含系統解析與快取；各網站依序測量，不是同時控制組。探針不使用瀏覽器或環境變數 HTTP Proxy；VPN 路由仍適用。",
                  "- HTTPS 回應成功率是完整最終 HTTP 狀態列取得比例（200–599；只有 1xx 不算完成），**不是封包遺失率**；403、302 等回應也算有回應。",
                  "- 本工具只測 HTTPS/1.1 首次連線；不代表瀏覽器（HTTP/2、HTTP/3、QUIC）、影片播放啟動、影片緩衝或整頁載入時間。",
                  "- IPv4/IPv6 自動模式沒有模擬瀏覽器 Happy Eyeballs；結果受 DNS、IP、Anycast、CDN、TLS 與服務端回應影響。",
                  "- 沒有實際來回路由或海纜載流證據時，不要宣稱某條海纜、某個中繼路由器或 ISP 必然有故障。",
                  "", "## 建議補充測試", "",
                  "- 用有線網路重測，並與 Wi-Fi 對比；避開 VPN/Proxy，記錄是否使用。",
                  "- 問題發生當下與非尖峰時段各測一次；記錄時間、測試時長、受影響應用與操作。",
                  "- 選定同一目的地，分別比較 IPv4 / IPv6、TCP/443 MTR 和應用實際體驗。",
                  "- 影片卡頓時保留播放器統計（如 YouTube Stats for Nerds）與出問題的實際時間。",
                  "- 必要時使用 Cloudflare Speed / FAST.com 的 Unloaded/Loaded Latency 與吞吐量作輔助比較。",
                  "", "## 建議向 ISP 報修的文字", "",
                  "您好，我使用貴公司的固網服務，在【日期時間】連線【服務】時發生【實際症狀】。",
                  "已於【有線/無線】環境測試，在【測量時段】依序對照【服務與結果】；附件包含 HTTPS 測試紀錄，其他路由與播放器證據如有也一併附上。",
                  "請協助確認線路品質、連線記錄及相關路由／互連品質，並提供障礙案件編號和後續回覆方式。",
                  "", "_產出的內容是診斷線索，不是故障責任鑑定或具法律認證的測速報告。_", ""])
    if raw.get("synthetic"):
        lines[:0] = ["> **虛構示範數據，沒有測試任何真實固網。**", ""]
    return "\n".join(lines)


def validate_evidence(raw: Any) -> None:
    """Reject malformed inputs; never trust cached summaries over samples."""
    if not isinstance(raw, dict) or raw.get("schema_version") != "1":
        raise ValueError("Expected schema_version 1")
    if not isinstance(raw.get("metadata"), dict) or not isinstance(raw.get("samples"), list):
        raise ValueError("Expected metadata object and samples array")
    for sample in raw["samples"]:
        if (not isinstance(sample, dict) or not isinstance(sample.get("service"), str)
                or not isinstance(sample.get("host"), str) or type(sample.get("ok")) is not bool):
            raise ValueError("Invalid sample identity or ok flag")
        if sample["ok"] and (type(sample.get("http_status")) is not int or not 200 <= sample["http_status"] <= 599):
            raise ValueError("Successful sample needs a final HTTP status")
        for key, value in sample.items():
            if key.endswith("_ms") and (type(value) not in (float, int) or not math.isfinite(value) or value < 0):
                raise ValueError("Timing values must be finite nonnegative numbers")
        if "error_stage" in sample and not isinstance(sample["error_stage"], str):
            raise ValueError("Invalid error stage")
    for key in ("mtr", "gateway_ping"):
        if key in raw and not isinstance(raw[key], dict):
            raise ValueError(f"Expected {key} object")
    loss = raw.get("gateway_ping", {}).get("icmp_loss_percent")
    if loss is not None and (type(loss) not in (int, float) or not math.isfinite(loss) or not 0 <= loss <= 100):
        raise ValueError("ICMP loss must be a finite percentage")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="NetDiag TW: bounded HTTPS entry probes + evidence report")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("plan", help="Show presets and safe test scope; does not access network")
    run = sub.add_parser("run", help="Perform local tests; writes results locally only")
    run.add_argument("--preset", choices=sorted(PRESETS), default="basic")
    run.add_argument("--repeat", type=int, default=3, help="1..20 samples per host")
    run.add_argument("--host", action="append", type=valid_public_hostname, help="Optional custom public hostname; up to five (overrides preset)")
    run.add_argument("--family", choices=["auto", "v4", "v6"], default="auto")
    run.add_argument("--timeout", type=float, default=5.0)
    run.add_argument("--pause", type=float, default=0.5)
    run.add_argument("--gateway", type=safe_gateway, help="Optional explicit gateway for ping")
    run.add_argument("--ping-count", type=int, default=20)
    run.add_argument("--mtr-host", type=valid_public_hostname, help="Optional host from selected preset or --host for TCP/443 MTR")
    run.add_argument("--mtr-cycles", type=int, default=20)
    run.add_argument("--isp", default="")
    run.add_argument("--plan", default="")
    run.add_argument("--access", choices=["ethernet", "wifi", "unknown"], default="unknown")
    run.add_argument("--output", default="netdiag-result.json")
    report = sub.add_parser("report", help="Generate report from existing JSON (offline)")
    report.add_argument("input")
    report.add_argument("--output", default="netdiag-report.md")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "plan":
        print("No network action will be taken. Presets only test HTTPS entry endpoints, not video streams.")
        for name, entries in PRESETS.items():
            print(f"  {name}: " + ", ".join(host for _, host in entries))
        print("Run: python3 scripts/netdiag.py run --preset basic --repeat 3 --access ethernet")
        return 0
    if args.command == "report":
        if Path(args.input).resolve() == Path(args.output).resolve():
            raise SystemExit("Report output must differ from input JSON")
        try:
            raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
            validate_evidence(raw)
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(make_report(raw), encoding="utf-8")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise SystemExit(f"Cannot create report: {exc}") from exc
        print(f"Report written: {args.output}")
        return 0
    if not (1 <= args.repeat <= 20 and 1 <= args.ping_count <= 60 and 1 <= args.mtr_cycles <= 60 and
            1.0 <= args.timeout <= 15.0 and 0 <= args.pause <= 10):
        raise SystemExit("Out-of-range probe parameters")
    if args.host and len(args.host) > 5:
        raise SystemExit("At most five custom hostnames are allowed")
    entries = [(f"Custom {i+1}", host) for i, host in enumerate(args.host)] if args.host else PRESETS[args.preset]
    if args.mtr_host and args.mtr_host not in [host for _label, host in entries]:
        raise SystemExit("--mtr-host must be one of the hosts selected for this run")
    if Path(args.output).suffix.lower() != ".json":
        raise SystemExit("--output must end in .json (a separate .md report is written)")
    raw: dict[str, Any] = {"schema_version": "1", "metadata": {
        "started": now_iso(), "platform": f"{platform.system()} {platform.release()}",
        "isp": args.isp, "plan": args.plan, "access": args.access, "family": args.family,
        "timeout_seconds": args.timeout, "pause_seconds": args.pause,
        "resolver": "system getaddrinfo; cache may apply; not browser DoH; timed-out OS lookups may finish in background",
        "proxy": "direct sockets; environment HTTP proxies are not used; VPN routing still applies",
        "preset": "custom" if args.host else args.preset, "repeat": args.repeat, "method": "local_stdlib_https_entrance",
    }, "samples": []}
    print(f"Running on THIS device/network. {len(entries)} hosts x {args.repeat} probes")
    for service, host in entries:
        for index in range(args.repeat):
            result = check_host(host, args.family, args.timeout)
            result.update(service=service, sequence=index+1)
            raw["samples"].append(result)
            print(f"{service} [{index + 1}/{args.repeat}]: HTTPS={'ok' if result['ok'] else 'failed'}, {result.get('http_response_ms', '無')} ms")
            if args.pause and (index < args.repeat-1 or host != entries[-1][1]):
                time.sleep(args.pause)
    raw["summary"] = summarize(raw["samples"])
    if args.gateway:
        print(f"Testing explicitly provided gateway: {args.gateway}")
        raw["gateway_ping"] = ping(args.gateway, args.ping_count)
    if args.mtr_host:
        # Pin optional MTR to a public destination IP actually reached by the
        # bounded HTTPS probe. This avoids resolving the hostname a second
        # time to a non-public address and makes the comparison auditable.
        matching_ips = [sample.get("remote_ip") for sample in raw["samples"]
                        if sample.get("host") == args.mtr_host and sample.get("remote_ip")]
        if matching_ips:
            tested_ip = matching_ips[-1]
            print(f"Testing optional MTR: {args.mtr_host} ({tested_ip})")
            raw["mtr"] = mtr(tested_ip, args.mtr_cycles)
            raw["mtr"]["target_hostname"] = args.mtr_host
            raw["mtr"]["destination_ip"] = tested_ip
        else:
            raw["mtr"] = {"target_hostname": args.mtr_host,
                          "error": "No validated public destination from HTTPS probing; MTR not executed"}
    raw["metadata"]["finished"] = now_iso()
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = dest.with_suffix(".md")
    markdown_path.write_text(make_report(raw), encoding="utf-8")
    print(f"Raw evidence: {dest}\nReadable report: {markdown_path}\nNo results were uploaded by this script.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
