# NetDiag TW — 台灣網路診斷 AI Skill

**網路很慢、Facebook／YouTube 卡頓、晚上連線不穩？** 這個開源專案希望協助使用者在自己的電腦上蒐集網路連線測試資料，讓 AI 協助縮小問題範圍，整理出可以向 ISP 報修的紀錄。

> **目前狀態：開發測試中（Early development）。** 已可執行基本 HTTPS 入口測試及產生 JSON／Markdown 報告，但**不能自動確認 ISP、單一 Router 或海纜故障**。請協助在不同作業系統和固網環境測試，歡迎提出 Issue。

English: A local-first Agent Skill and Python probe for Taiwan broadband troubleshooting. It collects bounded DNS, TCP, TLS and HTTPS reachability evidence, then helps prepare an ISP-friendly incident report. This is an early community-testing project, not a certified network measurement service.

## 我需要自己跑 Python 嗎？

**使用本機 AI Agent 時，不必親手輸入 Python 指令；目前內建量測仍需要本機有 Python 3.10+。** AI 可以在確認環境、列出測試範圍並取得同意後代為執行。只使用標準函式庫，不需安裝 pip 套件。

- 只問診、解讀既有資料或整理報修文字：不需要 Python；但沒有量測就不能宣稱已驗證連線。
- 請本機 AI 執行內建量測：需要 Python，以及 AI 在這台電腦執行命令的權限。
- 自己操作、不使用 AI：可使用後面的 Python CLI 指令。

安裝 Skill 不會自動安裝 Python，也不會自動開始網路測試。Skill 是給 AI 的操作指引，不是內附執行環境的 App。缺少 Python 時，AI 應先說明並繼續問診；不得自行安裝或改用雲端量測冒充本機結果。免安裝 Python 的打包程式仍在規劃中。

## 請 AI 幫你診斷（建議入口）

專案根目錄就是符合 [Agent Skills](https://agentskills.io/specification) 的 Skill 資料夾，包含 `SKILL.md`、`scripts/` 和 `references/`。

**Codex（使用者層級）**，目錄依 [Codex 官方 Skills 說明](https://developers.openai.com/codex/skills)。

```bash
mkdir -p ~/.agents/skills
git clone https://github.com/clarencetw/netdiag-tw.git ~/.agents/skills/netdiag-tw
```

**Claude Code（使用者層級）**

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/clarencetw/netdiag-tw.git ~/.claude/skills/netdiag-tw
```

完成安裝後從新對話啟用技能，並嘗試：

> 我在台灣使用固網，最近晚上 YouTube 影片常卡住。請使用 netdiag-tw Skill，先確認我的網路環境與症狀，列出將執行的本機測試，得到我的同意後再進行。區分已觀察到的事實和推論，最後產生一份 ISP 報修文字。不能從單一 Traceroute hop 推定故障。

若 AI 執行環境是雲端而非你的本機，**不要將雲端量測結果稱為家用固網結果**；應改為指引使用者在本機執行測量、再分析輸出資料。

## 目前做得到的事

| 功能 | 狀態 | 說明 |
| --- | --- | --- |
| Agent Skill (`SKILL.md`) | 可試用 | 指導 AI 問診、蒐證、交叉檢查、產生報修說明 |
| DNS / TCP / TLS / HTTPS | 可試用 | Python 3.10+，只測網站入口的 HTTPS/1.1，不測完整頁面 |
| IPv4 / IPv6 對照 | 可試用 | 各自量測，不模擬瀏覽器 Happy Eyeballs |
| HTTP 回應時間分位數 | 可試用 | GET 送出後至首位元組，不含 DNS/TCP/TLS；不是影片起播速度 |
| JSON 原始資料、Markdown 報告 | 可試用 | 儲存在使用者本機，預設不上傳 |
| Gateway Ping／MTR TCP/443 | 選用 | 需先確認閘道；MTR 必須自行安裝，ICMP hop Loss 不等於資料轉送丟包 |
| NextTrace MCP、Globalping、RIPE Atlas | 規劃中 | 目前只有整合設計，**尚無程式 Adapter** |
| 海纜事件比對、影音播放器數據、GUI | 規劃中 | 不能從 Traceroute 單獨推斷實體海纜 |

**重要限制：** HTTPS 成功率不等於封包遺失率；測試 YouTube 網站入口不等於測到實際影片 CDN／緩衝效能。`http_response_ms` 是 HTTP GET 完成送出後至首位元組的等待時間；`elapsed_to_first_byte_ms` 另含 DNS、TCP 和 TLS。

## 手動 CLI（不用 AI 也可以）

需要 Python 3.10+，只使用標準函式庫，不需 `pip install`。先用 `python3 --version` 確認版本。

使用 macOS 或 Linux：

```bash
git clone https://github.com/clarencetw/netdiag-tw.git
cd netdiag-tw

# 看有哪些檢測目標，不連網
python3 scripts/netdiag.py plan

# 取得使用者同意後，從「有問題的固網」實際測量
python3 scripts/netdiag.py run \
  --host www.youtube.com \
  --family v4 \
  --repeat 5 \
  --access ethernet \
  --output results/youtube-v4.json
```

`results/` 已加入 `.gitignore`，避免不小心將測試資料提交至 GitHub。結果仍可能含有 ISP、主機平台、解析的 IP 與網路拓樸資訊；**分享之前請人工檢查並遮罩**。

Windows PowerShell 使用 `py -3`（先安裝 Python 3.10+）；多行 Bash 的 `\` 不能直接貼入 PowerShell，請將命令合併成一行。跨平台離線 CI 的最新結果見 [GitHub Actions](https://github.com/clarencetw/netdiag-tw/actions/workflows/test.yml)；本機離線測試與各平台真實網路驗證須分開記錄。本次已在 Mac／Python 3.14.7 通過 40 項離線測試，以及經授權的 18 次 IPv4／IPv6 HTTPS 入口量測；接入方式與 VPN 狀態未確認，這不代表其他平台已實測。

Windows PowerShell 可直接使用以下單行命令（先檢查版本，再授權連網）：

```powershell
py -3 --version
py -3 scripts/netdiag.py plan
py -3 scripts/netdiag.py run --host www.youtube.com --family v4 --repeat 3 --access unknown --output results/youtube-v4.json
```

測試整組網站入口：

```bash
python3 scripts/netdiag.py run --preset basic --repeat 3 --access ethernet --output results/basic.json
```

每個樣本進行一次系統解析、最多四個 IP 的 TCP 連線嘗試，TCP 成功後最多一次 TLS 握手與一次 HTTPS GET；不跟隨重新導向、不測影片、不下載完整網頁。`basic --repeat 3` 是 15 個樣本，最多 60 次 TCP 嘗試、15 次 HTTPS GET。DNS 實際封包數與 TCP 重傳由作業系統決定，不能用樣本數當成封包數。

比較 IPv6：

```bash
python3 scripts/netdiag.py run --host www.youtube.com --family v6 --repeat 5 --access ethernet --output results/youtube-v6.json
```

選用 TCP/443 MTR（必須另外安裝 mtr，且另行取得使用者同意）：

下面的指令有 30 個 HTTPS 樣本，另加 MTR；MTR 的 cycle 是每跳量測輪數，不是總封包數。程式限制最多 30 跳，預設 20 cycles 約有最多 600 個探測位置；這是工具探測量估算，不是包含 TCP 重傳等行為的精確線上封包總數。先完成基本 HTTPS 測試，有路由調查需求才使用。Windows 不保證有相容的原生 `mtr`；未安裝、權限不足或工具失敗都應記為未完成，不能當成路由故障。

```bash
python3 scripts/netdiag.py run --preset video --repeat 10 \
  --mtr-host www.youtube.com --output results/video-with-mtr.json
```

從已有的 JSON 重新產生報告（不連網）：

```bash
python3 scripts/netdiag.py report results/youtube-v4.json --output results/youtube-report.md
```

## 在自己的 Mac 上測試

1. 可請本機 AI 代為執行；若手動操作，開啟「終端機」，進入專案目錄，確認 Python 3.10+ 並執行 `plan`。開發用單元測試見 `CONTRIBUTING.md`。
2. 記錄有線／Wi-Fi、VPN 是否啟用、症狀、發生時間與 ISP。`--access` 只是自填標籤，程式不會驗證目前真的使用有線。請填實際狀態。
3. 先測同三個入口的 IPv4：

   ```bash
   python3 scripts/netdiag.py run --host cloudflare.com --host www.youtube.com --host www.facebook.com --family v4 --repeat 3 --pause 1 --access unknown --output results/mac-v4.json
   ```

   最多 9 次 HTTPS GET、36 次 TCP 嘗試。檢查 JSON 與同名 Markdown；再經同意，以 `--family v6 --output results/mac-v6.json` 重複同組測試，另增同樣上限。IPv6 無地址或無路由是需要保留的結果，不代表 ISP 故障。
4. 在問題時段與非問題時段各留下獨立檔案，避免覆寫。少量樣本只能描述本次觀察，不能估算整晚品質；YouTube／Facebook 入口正常也不能排除實際影片 CDN 問題。
5. 分享前手動檢查並遮罩兩種輸出，依報告範本補實際症狀，再交給 ISP；不要把未填寫的占位文字當成已驗證事實。

程式使用直接 socket 連線，不遵守 `HTTP_PROXY`／`HTTPS_PROXY` 或瀏覽器 Proxy 設定；VPN、系統路由與本機安全軟體仍會影響結果。不要為執行測試而自行改 DNS、防火牆或路由器設定。DNS 時間是系統解析器耗時，可能包含快取，並非 DNS 伺服器的純網路 RTT。`--timeout` 分別限制 DNS 等待、每個 TCP 嘗試、TLS 與整個 HTTP 階段；不是整輪測試的總時限。單一樣本最多約為七倍 timeout 加本機開銷。DNS 等待逾時不會取消作業系統底層解析，最多保留四個未完成的解析工作。

本機保存不等於匿名：目的服務會看到出口 IP；DNS 解析器會看到查詢。程式不查詢使用者公網 IP，但可選 ping／MTR 及錯誤內容可能含內網位址與拓樸，ISP、方案及自訂 hostname 也可能識別使用者。目前沒有自動遮罩功能。

## 這個專案希望幫助誰？

- 一般固網使用者：保留具體的症狀、發生時間和測試紀錄，讓報修更清楚。
- 網路工程師：使用標準化輸出快速評估 DNS、IP family、TCP/TLS、服務端或路由可疑方向。
- ISP/客服：從一致格式的故障紀錄開始排查，減少沒有條件、時間或測試環境的描述。

## 開發方向

1. 改善 macOS、Linux、Windows 的相容性與錯誤處理，確認數據指標定義。
2. 整合 NextTrace、Globalping、RIPE Atlas，以不同探針來源交叉驗證。
3. 查詢台灣海纜官方公告，只做相關背景事件，不直接認定物理傳輸路徑。
4. 加入使用者授權下的瀏覽器／影片播放統計、長時間量測，以及分享前隱私遮罩。
5. 整理可持續改進的 ISP 報修格式和更多真實案例。
6. 評估附帶 runtime 的簽章執行檔，讓使用者不必另裝 Python；先完成跨平台驗證，不以自動下載安裝取代使用者同意。

量測起訖、分母、分位數與錯誤限制見 [`docs/MEASUREMENTS.md`](docs/MEASUREMENTS.md)；公開準備清單見 [`docs/PUBLICATION.md`](docs/PUBLICATION.md)。

完整技術設計見 [`docs/DESIGN.md`](docs/DESIGN.md)，來源與限制見 [`references/sources.md`](references/sources.md)。

## 參與測試與回報

歡迎開 [GitHub Issues](https://github.com/clarencetw/netdiag-tw/issues) 告訴我：你的作業系統、是否有線或 Wi-Fi、使用哪個檢測指令、預期和實際結果，以及**遮罩後**的必要紀錄。請勿貼上公網／內網 IP、完整 MTR 拓樸、HAR、Cookie、Token、帳號或私人網址。詳細方式見 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## 授權

[MIT License](LICENSE)。本專案沒有隨附 NextTrace、MTR、Trippy 等第三方工具；安裝與使用請遵守其各自的授權和服務條款。
