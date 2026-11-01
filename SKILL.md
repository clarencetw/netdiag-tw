---
name: netdiag-tw
description: 在台灣協助使用者診斷固網、Wi-Fi、網站與影音卡頓。蒐集本機 DNS/HTTPS 與選用 MTR 證據，區分可能故障範圍，產生可向 ISP 報修的繁體中文報告。當使用者說網路很慢、Facebook/YouTube/Netflix 卡、封包遺失、夜間斷線、想查路由或海纜時使用。
license: MIT
compatibility: Python 3.10+; macOS/Linux/Windows; optional system mtr for TCP/443 route checks
---

# NetDiag TW — 證據優先的固網診斷（開發測試中）

使用繁體中文。本 Skill 不是執法認證，不能判定海纜故障或 ISP 責任。實測必須在使用者自己的網路上執行；不可把 AI 主機或雲端探針的結果說成使用者家中的結果。

## 1. 問診

先問最有鑑別力的問題：哪個服務、什麼動作、時段與頻率、有線或 Wi-Fi、VPN/Proxy、ISP 與方案、是否只有一台設備。不要索取姓名、帳密、住址。資料不足時不預設是 ISP 或海纜。

## 2. 執行前

- 需要本機 shell 與 Python 3.10+（`python3 --version`；Windows 用 `py -3`）。缺少環境時繼續問診或解讀已有資料，說明自動量測不可執行，**不得自行安裝**任何東西。
- 列出目標、IP family、每站樣本數與 HTTPS 請求上限，取得使用者同意後才連網。`plan` 與單元測試不連網。
- 不修改 DNS、路由器、防火牆；不自動提權。目的服務會看到使用者的出口 IP。
- 目前只自動執行 HTTPS、選用 gateway ping／MTR；NextTrace、Globalping、RIPE Atlas、海纜資料仍是人工查詢。

## 3. 測試（依層次蒐證，每層都可停止）

1. **LAN**：先有線重測；只有 Wi-Fi 異常就不必查海纜。
2. **DNS / IPv4 / IPv6**：分別測，記錄解析 IP 與時間。
3. **HTTPS 入口**：`scripts/netdiag.py`，只測首頁，不代表影片或整頁體驗。
4. **跨服務對照**：先按症狀選少量目標；需要多類網站時才用 `--preset diagnose`（12 站）。分組描述網站用途／服務市場，不代表節點所在地或國際線路。不能因某組較慢就推定國際出口故障。`social`／`video`／`work`／`game`／`ai` 只測入口，不代表動態牆、串流、通話、遊戲伺服器或 AI API 的品質。
5. **路由**：縮小範圍後才用 `mtr`／NextTrace；中間跳 Loss 若未延續到終點，不能判定該跳故障；即使延續到終點，仍需端到端與不同時段證據交叉驗證。
6. **外部觀測**：他國節點連到 Facebook ≠ Facebook 回連到使用者家。
7. **海纜**：只查數發部公告日期作為背景；traceroute、BGP、地圖都無法識別實際載流海纜。

```bash
python3 scripts/netdiag.py plan
python3 scripts/netdiag.py run --preset diagnose --repeat 5 --access unknown --output results/diagnose.json
python3 scripts/netdiag.py report results/diagnose.json --output results/report.md
```

上述 12 站 × 5 次最多 60 次 GET、240 次 TCP 嘗試、60 次系統解析呼叫；不是固定封包數。不要在未取得額外同意下擴充測試。MTR 另有最多 30 跳 × 預設 20 cycles，約最多 600 個探測位置；gateway ping 預設要求 20 次，需先確認目標與授權。

選用：`--family v4|v6`、`--gateway <先確認的閘道>`、`--mtr-host <host>`。`--access` 是自填，程式不驗證。程式不使用 Proxy 設定，VPN 仍會影響結果。結果與報告只存本機，輸出前須人工檢查並遮罩 IP、ISP 等識別資訊；讀取原始報告給雲端 AI 前先取得同意。

## 4. 輸出規則

每個結論標示 `observed`（數據）、`inferred`（推論）、`unknown`（無資料），並附時間、地點、目標、IP family、樣本數與限制。HTTPS 成功率不是封包遺失率。

- `LAN 疑似問題`：有線設備與同 LAN 目的端同時出現問題。
- `特定服務或路由疑似問題`：對照站正常、單一服務重複失敗。
- `上游/ISP 疑似問題`：多目標、多設備同時失敗，LAN 正常。
- `尚無法定位`：資料不足時的正常結論。

給出最可能的範圍後，再列至少兩個其他解釋與最小成本的下一步測試。

報告含：症狀與時間、證據表、限制、可驗證事實的報修文字。客服電話與申訴流程見 `references/taiwan-isp-complaint.md`，**電話須當次查證，不得憑記憶**。指標定義見 `docs/MEASUREMENTS.md`，來源見 `references/sources.md`。
