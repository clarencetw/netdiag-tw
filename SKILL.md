---
name: netdiag-tw
description: 在台灣協助使用者診斷固網、Wi-Fi、網站與影音卡頓。蒐集本機 DNS/HTTPS 與選用 MTR 證據；需要時另外經授權查閱公開量測與海纜公告，區分可能故障範圍，產生可向 ISP 報修的繁體中文報告。當使用者說網路很慢、Facebook/YouTube/Netflix 卡、封包遺失、夜間斷線、想查路由或海纜時使用。
license: MIT
compatibility: Python 3.10+; macOS/Linux/Windows; optional system mtr for TCP/443 route checks
---

# NetDiag TW — 證據優先的固網診斷（開發測試中）

> 使用繁體中文。不要把本 Skill 當成執法認證、海纜故障判定或 ISP 責任鑑定。實測資料一定要從使用者的實際連線環境執行，不可把 AI 執行環境的測試冒充成使用者家中的結果。

## 先確認要解決的問題

1. 記錄具體症狀：服務與動作（例如 YouTube 1080p 每 30 秒停頓），頻率、時段、起始時間、地區（可粗略）、有線或 Wi-Fi、VPN/Proxy、IPv4/IPv6、ISP、申辦速率、是否只有一台設備。避免要求真實姓名、帳號、密碼、住址或分享私密 URL。
2. 根據症狀，只選必要測試。資料不足時先問最有鑑別力的一題，不能先預設是 ISP 或海纜。
3. 當工作環境無法執行使用者本機命令時，清楚說明無法直接觀察使用者的固網，改提供本機執行步驟。不應聲稱遠端 Globalping、AI 主機或其他雲端測試是使用者自己的線路結果。

## 執行條件檢查

使用者不必手動輸入 Python；可由具本機命令權限的 Agent 代為操作。先確認執行位置確實是使用者要診斷的網路、可使用本機 shell，並以 `python3 --version`（Windows 可用 `py -3 --version`）確認 Python 3.10+。探針只用標準函式庫，不需 pip 套件。不要假設 macOS／Windows 已預裝合適版本。

缺少 runtime 或本機命令權限時，說明內建自動量測暫不可執行，繼續問診、解讀已有且經同意分享的資料，或提供本機操作指引。不得自行安裝 Python／套件、改成未驗證的替代探針，或把雲端結果當成本機結果。安裝 Skill 本身不會安裝 runtime。

## 執行前的範圍與同意

先完整閱讀 CLI 說明，列出目標、IP family、每站樣本數、HTTPS 請求上限，以及可選 ping／MTR 的額外流量，得到使用者同意後才連網。`plan` 與單元測試不連網。每個 HTTPS 樣本有一次系統解析、最多四次 TCP 嘗試、最多一次 HTTPS GET；DNS 封包數及 TCP 重傳不可由樣本數精確推算。MTR cycle 是每跳輪數，不能當成總封包數；程式最多 30 跳，預設 20 cycles 約最多 600 個探測位置，實際線上封包數還受工具與作業系統行為影響。外部探針、瀏覽器影片、速度測試與官方網站查詢也是額外連網工作，須納入授權範圍。

本原型只自動執行 HTTPS、選用 gateway ping／MTR 及本機報告；NextTrace、Globalping、RIPE Atlas、海纜資料和播放器整合仍是 Roadmap。以下進階流程是人工／Agent 指引，不代表已有 Adapter。不得修改 DNS、路由器、防火牆或其他系統網路配置，不得自動提權或安裝工具。

## 檢測流程（每一層都有停止條件）

A. **本地設備與 LAN**：優先有線重測，檢查 Wi-Fi、乙太網路協商、路由器負載和同 LAN 基準。必要時用使用者確認過的閘道 IP 進行有界 ping；路由器可能限制 ICMP。若只有 Wi-Fi 出問題，不用先調查海纜。

B. **DNS / IP family**：檢查 OS 實際 DNS 設定、系統解析結果，對同一 hostname 分別做 IPv4/IPv6 測試。`dig` 不一定等於系統或瀏覽器 resolver（DoH、split-DNS、VPN）。記錄解析得到的 IP、時間、測試地點，不要硬編 IP。

C. **HTTPS 入口**：`scripts/netdiag.py` 提供保守的 DNS、TCP、TLS、HTTP status 與 HTTP 回應時間（GET 完成送出到第一個位元組，不含建連）。它只測首頁 HTTPS/1.1，不代表完整頁面載入、HTTP/3 或影片/CDN 體驗；403/302/405 都可能代表網站有回應，不能單獨解讀成 ISP 壞掉。

D. **路由與 ICMP**：若已經縮小故障範圍，再用 `mtr`、NextTrace 或 Trippy。若環境已有 NextTrace MCP，先查看當前工具清單與能力說明，不假設特定工具名稱存在，選最小測試工具。TCP/443 與 ICMP/UDP 可能走不同 ECMP 路徑。中繼跳 Loss、* 和 RTT 高，若未延續至目的地，**不能**判定該跳故障；即使延續，仍需端到端 TCP/應用層與其他時段交叉驗證。

E. **實際服務體驗**：影片應記錄播放器統計、起播時間、緩衝、重緩衝次數及影音 CDN URL（輸出前務必刪除 token/query）；網站要區分 DNS/TCP/TLS/TTFB、DOM、LCP 與資源下載；一般首頁 HTTP 測試不代表 Facebook 動態牆或 YouTube 影片體驗。

F. **外部觀測**：Globalping 是其他網路到指定目的地的量測；RIPE Atlas 可提供公共量測和有 Credits 的自訂測試。**他國節點連到 Facebook ≠ Facebook 伺服器回連到使用者家中**。只有控制、授權的目的端設備或代表性探針才能採集另一方向的觀測，不得假稱精確「回程」。

G. **海纜**：先查數發部海纜障礙公告日期、海纜、替代路由，再看 TeleGeography/民間地圖。Traceroute IP 地理位置、BGP AS path、海纜拓樸皆不足以識別實際物理載流海纜。只用「有相符的背景事件／尚待確認」的措辭，禁止直接下海纜造成特定使用者卡頓的結論。

## 使用本機原型

在 `netdiag-tw` skill 目錄執行：

```bash
python3 scripts/netdiag.py plan
python3 scripts/netdiag.py run --host example.com --repeat 5 --output results/custom.json
python3 scripts/netdiag.py run --preset basic --repeat 3 --access ethernet --isp '使用者自填' --plan '使用者自填' --output results/netdiag-result.json
python3 scripts/netdiag.py run --preset video --repeat 10 --family v4 --mtr-host www.youtube.com --output results/peak-video-v4.json
python3 scripts/netdiag.py report results/netdiag-result.json --output results/complaint.md
```

可選 `--gateway 192.168.1.1`（**先確認**閘道）、`--family v6`、`--mtr-host`。不會自動裝套件、修改 DNS 或執行掃描；輸出只留在本機。Windows 使用 `py -3`；macOS/Linux 可使用 `python3`。`mtr` 是可選外部工具、未裝就回報未執行。原型的 `--family auto` 不是瀏覽器 Happy Eyeballs。

直接 socket 不使用 `HTTP_PROXY`／`HTTPS_PROXY` 或瀏覽器 Proxy；VPN 與系統路由仍會影響結果。`--access` 是自填資料，不能據此宣稱已驗證有線。系統 DNS 解析可能命中快取，不等於線上 DNS RTT。不要要求使用者修改設定來讓測試通過。

**先告知執行者**：這些操作會向第三方服務產生有限的 HTTPS 請求，並有可能讓目的服務看到使用者的網路出口 IP。若使用者不允許，僅提供操作建議，不執行。目前沒有自動隱私遮罩；JSON、Markdown、ping／MTR、錯誤內容與自填欄位都必須人工檢查。讀取原始報告給雲端 AI 也可能構成資料外傳，須先告知並取得同意。

## 輸出品質規則

入口取得 HTTP 回應的成功率不是網路封包遺失率。每個結論都區分：`observed`（原始數據）、`inferred`（推論）、`unknown`（無資料），附上量測時間、探針位置、目標 hostname/IP、IP family、協定、取樣次數、資料來源與測試限制。判斷可信度只能根據證據，不能依語氣或 LLM 自信程度。

- `LAN 疑似問題`：同一時段**有線**設備與同 LAN 目的端出現相符問題，且測試夠充分；路由器的 ICMP Loss 單獨不能證明。
- `特定網站/服務或路由疑似問題`：控制網站正常、特定服務重複失敗；仍需區分 DNS、CDN、應用程式及服務端。
- `上游/ISP 路由疑似問題`：多目標、多設備同時失敗，本地 LAN 基準正常，必要時其他接入線路與公開探針交叉驗證；不能直接指認某個 ASN、海纜或單一 hop 的責任。
- `尚無法定位`：缺少足夠數據時的正常輸出，不應硬選根因。

執行兩次評論：先由網路工程視角提出最可能的故障範圍；再用反方視角列出至少兩個其他解釋，以及最小成本的下一個可驗證測試。若平台支援獨立子 Agent，可分工後交叉審查；不支援則順序執行，不宣稱用了多個 Agent。

### 報告

- 第一頁：使用者症狀、影響時間、結果摘要、是否有線重測、可信度。
- 證據表：DNS / TCP / TLS / TTFB、HTTP 回應、可用的 ping / MTR、IPv4/IPv6、同時段控制組。
- 限制：哪些資料沒有測到，不可誤解的 ICMP/海纜/路由現象。
- 報修文字：只說可驗證的事實、請求線路／互連檢查、請對方建立障礙單並提供案件編號。
- 官方客服電話與申訴流程需使用**當次查證**的 ISP/主管機關來源，不要記憶或猜測號碼。

## 參考資料（使用前檢查時間、適用範圍）

指標定義參見 `docs/MEASUREMENTS.md`，來源參見 `references/sources.md`，海纜和官方電話必須查當下最新版本。勿把內容複製到第三方服務前自動上傳完整來源 IP、內網拓樸、HAR cookies、簽章 URL 或帳號資訊。
