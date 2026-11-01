# NetDiag TW — 台灣網路診斷 AI Skill

網路很慢、Facebook／YouTube 卡頓？這個專案在你自己的電腦上蒐集連線證據，讓 AI 協助縮小問題範圍，並整理成可向 ISP 報修的紀錄。

> **開發測試中（Early Development）。** 目前只做 DNS／TCP／TLS／HTTPS 入口測試與報告，**不能確認 ISP、Router 或海纜故障**。

English: a local-first Agent Skill and stdlib-only Python probe for Taiwan broadband troubleshooting. Early community-testing project, not a certified measurement service.

## 安裝（AI Agent）

```bash
# Claude Code
git clone https://github.com/clarencetw/netdiag-tw.git ~/.claude/skills/netdiag-tw
# Codex
git clone https://github.com/clarencetw/netdiag-tw.git ~/.agents/skills/netdiag-tw
```

新對話中說：「我在台灣用固網，晚上 YouTube 常卡。請用 netdiag-tw，先確認症狀並列出測試範圍，我同意後再執行。」

使用者不必親手輸入 Python 指令，本機 AI 可代為執行；內建量測仍需要 Python 3.10+（只用標準函式庫）與本機命令權限。Skill 不會自動安裝 Python；缺少環境仍可問診，但不能假稱已有實測。雲端 AI 的連線結果不能當成本機固網結果。

## 手動使用

先 Clone 並進入專案目錄，確認 `python3 --version` 至少為 3.10。以下連網指令須先同意測試範圍；`--access` 請填實際狀態，不確定時用 `unknown`。

```bash
python3 scripts/netdiag.py plan                      # 不連網，列出 preset
python3 scripts/netdiag.py run --preset diagnose --repeat 5 --access unknown --output results/diagnose.json
python3 scripts/netdiag.py report results/diagnose.json --output results/report.md
```

Windows 請用 `py -3`，命令寫成一行。

| 選項 | 說明 |
|---|---|
| `--preset` | `diagnose`（建議：多類網站入口，12 站）、`basic`、`taiwan`（台灣服務網站 8 站）、`region`（其他市場網站）、`social`、`video`、`work`、`game`、`ai`、`developer` |
| `--host` | 自訂公開網域，最多五個 |
| `--family v4\|v6` | 分別測 IPv4／IPv6 |
| `--gateway` / `--mtr-host` | 選用 ping／TCP/443 MTR（需自行安裝 `mtr`，權限要求依安裝方式而定，不自動提權） |

每個樣本最多一次系統解析呼叫、四次 TCP 嘗試、一次 TLS 握手與一次 HTTPS GET；前段失敗不會送出 GET，不跟隨轉址、不測影片。每次最多 12 站，GET 上限 = 站數 × `--repeat`。上述 `diagnose --repeat 5` 最多 60 次 GET、240 次 TCP 嘗試及 60 次解析呼叫；DNS 封包與 TCP 重傳量由 OS 決定。請依症狀先選最少必要目標。

分組僅描述網站用途／服務市場，不代表伺服器所在地、近端距離或是否走國際線路。分組延遲不能用來直接判定國際出口問題。選用 MTR 另有流量：最多 30 跳，預設 20 cycles 約最多 600 個探測位置，不等於精確封包數，需另行授權。

## 限制

- HTTPS 成功率**不是**封包遺失率；測網站入口不等於測影片 CDN。
- traceroute、BGP、地圖都無法判定實際海纜；中間 hop Loss 不等於故障。
- 結果含 IP 與 ISP 資訊，探針只存本機（`results/` 已被 Git 忽略），目前沒有自動遮罩。分享或提供給雲端 AI 前請人工檢查；Git 忽略不是隱私過濾器。
- 探針不使用 HTTP Proxy／瀏覽器 Proxy；VPN 與系統路由仍影響結果。不要為了測試而修改 DNS、路由器或防火牆。
- [CI](https://github.com/clarencetw/netdiag-tw/actions/workflows/test.yml) 是跨平台離線測試，不能代表各平台真實固網品質已驗證；新增目標也未逐站實測。
- 規劃中、尚無程式：NextTrace、Globalping、RIPE Atlas、海纜公告比對、播放器數據。

## 文件

[報修與申訴流程](references/taiwan-isp-complaint.md) · [指標定義](docs/MEASUREMENTS.md) · [來源](references/sources.md) · [參與測試](CONTRIBUTING.md) · [MIT 授權](LICENSE)
