# NetDiag TW：台灣固網診斷 AI Skill 的產品設計與技術決策（2026-11-01）

## 決策

**值得做：先開源一個可跨 Agent 使用的證據蒐集／判讀 Skill；不要重新實作 Traceroute。**

目標市場分成兩層：

1. `工程師 / AI CLI 用戶`：下載 Skill，在自己連線環境上執行，獲得對應證據與報告。
2. `一般固網用戶`：不會使用終端機，未來需要一鍵程式（可選擇不安裝）與清楚文字；純雲端網頁無法可靠執行使用者本機的 traceroute、讀取實際 Wi-Fi/LAN 情形。

優先解決「客戶覺得慢，但拿不到可用證據」的問題，不以自稱全球路由判官、海纜推斷器、客觀 ISP 排行榜為賣點。

## 初版設計的各角色立場

| 視角 | 核心主張 | 反方質疑 | 決策 |
|---|---|---|---|
| 家庭使用者 | 在 1 分鐘內知道要測甚麼、客服怎麼說 | 下載 Skill 的使用者太少 | Skill 是技術版；一般用戶另設 GUI |
| 網路工程師 | 有線／同 LAN／DNS／IPv4/v6／TCP／HTTP ／MTR 分層測 | Ping、hop Loss 會誤報 | 不以中間 hop 判定根因 |
| 開源維護 | NextTrace MCP、MTR、Globalping 已有核心測量 | 多整合會產生相依與版本漂移 | 可插拔 Adapter，預設不用外部套件 |
| 台灣 ISP／海纜 | 接入、互連、CDN、海纜背景資料有在地價值 | BGP/GeoIP/海纜地圖並非真實光路 | 海纜只做背景事件，不做直接歸因 |
| UX／隱私 | 要有可分享、可遮罩報告 | 公開 IP 和 HAR、路由會洩漏網路詳情 | Local-first、分享前遮罩，預設不外傳 |
| 紅隊／批判思考 | 一張不完整路由圖最容易被 AI 說成「ISP 爛」 | ISP/服務商會對錯誤指控反彈 | Observed / Inferred / Unknown 分欄呈現 |

此表是初版設計推演，並非實測證據。本次程式審查與可重現驗證另見 `docs/REVIEW.md`。

## 使用者旅程

`Facebook 影片很卡` → 選 `影音 / 社群卡頓` → 確認有線/無線、VPN、問題時間 → 本機量測 Facebook / Google / Cloudflare HTTPS 入口 → 如有必要測 TCP/443 MTR → 教使用者蒐集播放器的實際串流統計 → 比對其他 ISP/地區的同時段測試 → 如果有國際段跡象再查海纜公告 → 輸出「已觀察到、尚未證實、下一步」→ 產生 ISP 報修文字與附件。

**服務目標不是等於串流目標**。`www.youtube.com` 僅是網站入口；實際影片通常由其他主機、CDN、授權 URL 提供，不能把首頁連通當作影片路由完全正常。Facebook、Netflix 同理。Playwright/Chrome DevTools/播放器統計可做進階體驗分析，但須處理登入與敏感 HAR。從不自動上傳 cookie、token、完整 URL。

## 執行原理

下圖為產品目標架構，**不代表全部已實作**。目前 CLI 僅提供系統解析器、HTTPS 入口、選用 gateway ping／MTR 與本機報告。NextTrace、Trippy、外部觀測、海纜資訊、測速與自動假設產生都不是現有 Adapter。

```text
Local user device
 ├─ Network context: link medium / VPN / ISP (user-provided)
 ├─ DNS: system resolver / IPv4 / IPv6
 ├─ HTTP: bounded HTTPS request / stage timing (not packet RTT)
 ├─ Path: NextTrace MCP / MTR / Trippy (optional)
 └─ Quality: Cloudflare Speed / FAST.com (user-guided)

External observations (NOT the user's line)
 ├─ Globalping / RIPE Atlas: other network vantage points
 ├─ RIPEstat / PeeringDB: IP ASN and routing metadata
 ├─ moda fault notices: time-bounded cable background
 └─ TeleGeography / OCF map: geographic infrastructure

Evidence normalizer → hypothesis + counterexample → uncertainty labels
                    → human-readable report / ISP complaint
```

## 檢測目標

- `basic`：Cloudflare、Google、Facebook、YouTube、Netflix 的 HTTPS **入口**。
- `social`：Facebook、Instagram、Threads、X。
- `video`：YouTube、Netflix、Twitch 的 HTTPS 入口；不測影片內容。
- `developer`：GitHub、Cloudflare、Google。
- 自訂目標：最多五個公開 DNS hostname，不接受任意 URL、IP、port；DNS 回私人／非全域 IP 則跳過。

**不要寫死某個 Googlevideo CDN IP**；它會隨 DNS、地點、時間、影片、登入、封包分配改變，不能直接代表使用者所見影片。

## 分層判讀與決策表

| 觀察 | 可採用的假設 | 不可直接宣稱 | 最具鑑別力的後續測試 |
|---|---|---|---|
| 只有 Wi-Fi 不穩、有線正常 | Wi-Fi 干擾／AP／頻道／漫遊 | ISP 連外壞 | 同位置有線 + 同時間檢測 |
| 同 LAN 基準也間歇失敗 | 本地路由器／LAN／網卡可疑 | 一定是 ISP | 第二裝置與閘道／同 LAN 目標比對 |
| 多域名 DNS 失敗但 IP/TCP 正常 | Resolver／DoH／VPN 可疑 | 全球網路不通 | OS resolver 與明確指定 Resolver 比對 |
| 僅 IPv6 連線失敗、IPv4 正常 | IPv6 path／MTU／路由問題 | 海纜斷 | 相同 hostname 的 v4/v6 多次測試 |
| 訪問單一服務失敗、控制網站正常 | 特定 CDN、網站、路由或應用故障 | ISP 一定限速 | 同服務不同設備、ISP、時段與瀏覽器 |
| 晚上某 ISP 變慢、白天正常 | 尖峰壅塞、共享頻寬、排程型負載 | 一定是國際出口不足 | 同條線多晚多次、負載時延遲、路由 |
| MTR 第 6 跳 loss 50%，最後跳 0% | 第 6 跳控制平面限速可能性高 | 第 6 跳故障 | 最後跳、TCP/443 與應用層結果 |
| 海纜公告有障礙 | 背景故障事件可供調查 | 流量走該海纜、造成卡頓 | ISP/營運者的路由／運量／維護證據 |

## 去程、回程與海纜

- 去程：本地 traceroute 是當前探測協定的出站路徑**片段**；CDN、Anycast、ECMP、ICMP rate limit、NAT、MPLS 造成不可觀測與波動。
- 回程：本地 traceroute 不會顯示遠端返回使用者的逐跳路徑。Globalping 的其他地點到相同網站不等於網站回到家庭接入線路的逆向路由。必須有受控或授權的遠端 vantage point，且目標、流量方向、時間與路徑都要標明。
- BGP/ASN：能提供 AS 宣告與控制平面線索，不保證實際資料流經過該 AS path 或相同地理位置。
- 海纜：拓樸圖只能說「哪些海纜在何處」，無法從 IP hop 映射到哪一條光纜／纜芯／波長。若無 ISP/國際 carrier 確認，只能標「可能相關」。

## 競品與可替代方案

- NextTrace：候選開源路由工具；Skill／MCP 的版本、能力與部署方式需在整合前查核。
- `connectivity-triage`：已有 macOS 連線問題診斷流程；更接近純技術故障處理。
- Cloudflare Speed、FAST.com：大多數使用者可以立即使用，但較少提供客觀且可追蹤的 ISP 報修推論鏈。
- Globalping / RIPE Atlas：跨網路測量成熟，但非所有使用者都知道如何同時解釋本地問題和公眾資料。
- OCF 網路韌性工具：有海纜地圖、App 依賴與斷線風險工具，是可引用的互補資料，而非需要重做的功能。

## 方案選擇

| 方案 | 可用性 | 差異化 | 主要問題 | 選擇 |
|---|---|---|---|---|
| 只寫 SKILL.md，教執行 ping/mtr | 最快 | 低 | 已有相似產品，無標準結果 | 不單獨發布 |
| Skill + 本機探針 + 統一 JSON + 報修報告 | 高（技術用戶） | 中高 | 需跨 OS 測試、處理假陽性 | **第一階段** |
| NextTrace MCP + 外部觀測資料整合 | 高（技術用戶） | 中 | 外部服務、額度與條款 | **第二階段** |
| GUI / 一鍵下載 / 長期時序圖 | 高（一般用戶） | 高 | 維護成本、簽章/更新、資安 | 問題驗證後再做 |
| 純網頁版完全檢測本機路由 | 不可完整達成 | 低 | 瀏覽器 Sandbox，沒有一般原生 traceroute 權限 | 不選 |

## 初版資料結構

`schema_version`, `metadata`（本機時間／OS／接入方式／ISP 自填／測量方式）, `samples`（hostname、resolved IP、family、DNS/TCP/TLS/HTTP 回應時間、HTTP status、error stage）, `summary`（sample count、response ratio、p50/p95），選填 `gateway_ping`、`mtr`。測試結果由程式保存 JSON，AI 只負責在證據上建立可反駁的假設，不補寫未測的 KPI。

計畫中的下一版才加入：`probe_network`, `location_scope`, `metric_definition`, `evidence_source`, `measurement_id`, `source_freshness`, `hypothesis`, `alternatives`, `confidence`, `limitations`。資料版本需要 backward compatible。

## 發行與合規檢查

1. 開源 Skill 與探針分離，預設本機儲存；不需要集中收集任何使用者流量。
2. 不要在未經同意下自動執行大量 ping/MTR／廣泛 port scan、流量壓測或第三方服務查詢。遇到未授權測試目標，不執行。
3. 帳號、公開 IP、內網 IP、宿主名稱、HAR/Cookie、授權查詢 URL、網域路徑及細緻地點需要分類處理；公開分享前提供明確遮罩機制。
4. NextTrace/MTR 等工具的 GPL 授權需評估再散布方式，對外部資料 API 的額度、商用條款也需個別檢查。
5. 官方海纜公告只以日期新鮮度與狀態為背景；不可自動把使用者網路問題歸咎於國家/業者或海纜斷裂。

## 建議用於驗證需求的實驗（全部是「目標值」，不是市場調查結果）

- 找 20 位台灣固網用戶試用（至少 3 種 ISP，涵蓋 Windows/macOS、Wi-Fi/有線），紀錄能否理解要做的步驟。
- 核心 KPI：70% 以上無需人工引導即可完成第一輪測試；80% 以上能從報告說出「目前知道什麼、還缺什麼」。
- 品質 Guardrail：100% 報告都清楚標註使用者端與公共探針來源；0 件不具證據的「ISP/海纜已確認故障」定論；所有輸出必須具測試時間與方法。
- 隱私 Guardrail：預設 0 自動上傳；每次分享都有清楚的使用者確認與遮罩預覽。
- 決策 Gate：若無法讓一般人完成 1 輪、或報修報告沒比直接打客服清楚，就暫停 GUI 擴充，先改善文字和證據判讀。

## 最佳下一步

1. 先用本包 Skill/CLI 量測實際連線，不要將本包的單元測試當成網路測試。
2. 參考 NextTrace 現有 MCP/Skill 加入 Path Adapter（只導入已經被授權的測量功能）。
3. 產出兩份報告：**一般人版（1 頁）**及**技術人員版（含 JSON、路由、採樣數與不確定性）**。
4. 人工收集 20 個使用者案例並做紅隊誤判檢查後，再評估 GUI 和社群 ISP 品質比較。

## 參考來源

原始來源整理在 `references/sources.md`，以官方更新日為主；請避免從以上初版文字直接推導任何即時海纜現況。
