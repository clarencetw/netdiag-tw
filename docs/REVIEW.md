# 接手審查與驗證紀錄

本次完整讀取 README、SKILL、DESIGN、探針、tests、references、examples、CI 與維護文件。
由三個獨立 Agent 分工網路工程／Red Team、Python／安全、使用體驗／維護，主 Agent
再交叉審查並整合。結論以重現案例與測試為依據，並非以多數意見表決。

## 已確認與修正

| 原問題 | 修正及證據 |
|---|---|
| IPv6 socket 建立例外可中止整輪 | 納入 TCP 失敗紀錄；保留 errno、family 與各次嘗試 |
| 系統 DNS 無等待時限 | 有界等待與最多四個 daemon worker；揭露底層解析不能取消 |
| HTTP 慢滴可持續延長量測 | 全階段 deadline 及共用 4096 bytes 上限 |
| TLS／HTTP 錯誤無法區別 | 分開 error_stage，憑證錯誤保留 error_type |
| EOF 仍有虛假首 byte 計時 | 只有實際收到 byte 才填時間 |
| 非法／截斷狀態列也可能算成功 | 驗證完整 HTTP/1.x 狀態列；1xx 後繼續讀 final，101 明示不支援 |
| 各階段只取整體成功樣本 | 各階段有值樣本獨立統計，列 counts／errors，定義分位數 |
| 報告信任可能過期的 summary | 從 samples 重算、驗證 schema 與數值；空樣本不宣稱成功 |
| CLI 計時欄位不存在 | 使用實際 http_response_ms |
| .md 輸出會覆蓋原 JSON | run 要求 .json；report 禁止輸入輸出相同 |
| 多播地址可能通過 is_global | 額外拒絕 multicast／reserved／unspecified，地址去重 |
| 使用者欄位可破壞 Markdown | 轉義特殊字元，驗證 ICMP 百分比 |
| macOS IPv6 ping 與 MTR 平台語意 | macOS 選 ping6；MTR 固定執行檔、family、最多 30 跳 |
| 文件混淆實作、規劃、樣本與封包數 | 補指標定義、請求量、Roadmap、Proxy／VPN、隱私與平台限制 |

反方審查沒有接受「任何 1xx 都直接失敗」的簡化方案：合法 103 後的 200 必須能在
原本上限內辨識。也沒有把 TCP fallback 擴充成 TLS／HTTP 多次重試，避免改變已告知
使用者的 GET 請求上限。MTR 中繼 loss 保留原始證據，不自動歸責 ISP。

## 離線驗證

本機環境：Darwin、Python 3.14.7。原始 10 項測試通過，但未涵蓋上述多個缺陷。
修正後 **40 項測試通過**，包括 11 個獨立 Red Team 案例與確切計時／分位數驗證。
另以 Python audit hook 阻擋真實 socket connect、getaddrinfo、sendto 及 subprocess
啟動後執行全套測試；攔截事件為空，40 項仍全部通過。

實際執行：

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q scripts tests
python3 scripts/netdiag.py plan
python3 scripts/netdiag.py report examples/SYNTHETIC-RESULT.json --output results/synthetic-checked.md
```

合成 JSON summary 與 samples 重算結果一致，合成 Markdown 與產生器完全一致，
`results/` 的 Git ignore 已驗證。所有範例資料均為虛構，不能視為真實網路測試。

CI 設定 Linux／macOS／Windows × Python 3.10／3.12／3.14；官方 Actions 範例的
checkout@v7、setup-python@v7 已核對。此為發布前離線審查紀錄；發布後的 CI 狀態以 GitHub Actions 與 `docs/PUBLICATION.md` 為準。
本機測試中的 Windows／ping／MTR 使用 mock，不是那些平台上的真實運行證據。

## 經授權的 Mac 連網驗證

完成離線驗證後，使用者明確同意三目標 × IPv4／IPv6 × 各三次的上限。
實際執行 18 個樣本、18 次 TCP 連線及 18 次 HTTPS GET，均取得有效最終 HTTP 狀態列；
Cloudflare 為 301，YouTube／Facebook 為 200。沒有追蹤重新導向、額外重跑、
ping、MTR、測速、影片 CDN 測試或系統設定修改。

兩份 JSON 的 summary 皆與 samples 重算一致，兩份 Markdown 皆與產生器結果完全一致。
詳細時刻、指令與數值保留在 Git 忽略的 `results/VALIDATION.md` 及同目錄原始檔案；
不將真實網路資料放進合成 examples。接入方式與 VPN／Proxy 狀態未確認，因此
保留 access=unknown，不能稱為已確認有線固網基準。

只證明該 Mac 當時可取得這三個入口的 HTTP 回應。每組三筆、先後測量與 CDN／路由
差異都限制推論；沒有驗證吞吐量、影片播放、長期丟包、MTR、Windows／Linux 實機。

## 公開與剩餘限制

適合作為 Early Development 的試用候選；不能宣稱穩定跨平台或已驗證 ISP 診斷準確率。
公開前仍需維護者確認實測結果、署名與安全回報管道，建立 Repository 後跑真正 CI。
已加入 Issue／PR 模板與建議 Topics；審查當時尚未設定遠端 Topics、Commit、Push、Release；後續發布狀態另記於 `docs/PUBLICATION.md`。

目前沒有自動隱私遮罩，也沒有自動取得公網來源 IP；自填資料、目的地址與可選路由
輸出仍可能敏感。AI 閱讀本機結果不等於資料永遠留在本機。

優先下一步：真實多平台測試、分享用遮罩與預覽、明確 schema 相容性、播放器／CDN
經授權蒐證。外部探針和海纜背景事件應在這些基礎穩定後再接入。
