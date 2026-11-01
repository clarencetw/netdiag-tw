# 量測定義與解讀限制

每個樣本使用新的 TCP/TLS 連線；系統 DNS cache 與 TLS 信任根仍受本機環境影響。
固定 HTTPS/443、`GET /`、HTTP/1.1，不跟隨重新導向，不模擬瀏覽器或下載影片。

| 欄位 | 定義 | 不能解讀為 |
|---|---|---|
| `dns_ms` | 呼叫系統解析器至取得地址清單，包含工作排程及 cache | 指定 DNS 伺服器的封包 RTT、瀏覽器 DoH 時間 |
| `tcp_ms` | 成功那次 socket 建立及 connect 的耗時 | 所有 fallback 嘗試總耗時、單一封包 RTT |
| `tls_ms` | 預設憑證驗證下的 TLS 握手耗時 | 單純路由延遲 |
| `http_response_ms` | GET 完成送出後至收到第一個回應 byte | 頁面載入、最終回應完成、影片起播時間 |
| `elapsed_to_first_byte_ms` | 樣本開始到第一個 HTTP byte；含解析、失敗 TCP 嘗試、建連、TLS 設定與送出 GET | 各分階段數字直接相加（有本機開銷與不同起訖） |
| `https_responses / samples` | 取得有效最終 HTTP 狀態列（200–599）的樣本比例 | 網路封包成功率、HTTP 業務成功率 |
| `stage_counts` | 每一指標實際存在的非負有限數值個數 | 該服務整體成功數 |
| `tcp_attempts` | 最多四次地址嘗試的 family、IP、成功與耗時／錯誤類型 | 全部 DNS 答案或全部可用路徑 |

HTTP 302、403、404、500 都算取得回應，但不表示服務功能正常。HTTP 首 byte
可能屬於暫時回應或後來被判定不合法的回應；因此有首 byte 計時不一定 `ok=true`。
沒有收到任何 byte 就不填首 byte 計時。程式最多消耗 4096 個應用層回應 bytes，
底層 TLS/socket buffering 與伺服器送出的流量可能更多；這不是精確下載流量限制。

`p50` 使用中位數（偶數筆取中間兩筆平均）；`p95` 使用 nearest-rank：
排序後取第 `ceil(0.95 × n)` 筆。數值四捨五入至 0.1 ms；`success_ratio`
取三位小數，報告保留分子／分母。少量樣本的 p95 往往就是最大值，不能代表長期品質。
各階段只彙總有值的樣本，包含後續階段失敗者；缺值不填零，也不把 timeout 當成成功延遲。
這仍有「失敗階段無成功延遲」的取樣限制，必須一起閱讀錯誤數與有效樣本數。

`report` 以 `samples` 重算摘要，不採用 JSON 中可能過期的 `summary`。
沒有樣本時明示無法判斷，不宣稱成功。`schema_version` 是資料格式，不是發行版號。

## 超時與地址選擇

`--timeout` 分別限制系統解析等待、每個 TCP 嘗試、TLS 握手及整個 HTTP 階段；
HTTP 慢速回應不會藉由逐 byte 重設總時限。TLS 憑證／系統信任根載入等本機開銷
不包含在網路時限內，整個程序不是硬即時系統。

系統 `getaddrinfo` 沒有可攜的取消 API。等待逾時後，daemon worker 可能仍在解析；
最多四個未完成 lookup，滿額會記為 `local_resolver_capacity`，不能歸咎 DNS 服務商。
CLI 結束不會等待這些 worker；不保證底層 OS 解析器立刻停止活動。

最多試前四個不同的公開單播地址；只在 TCP 失敗時換地址，TLS／HTTP 失敗不再重試。
`auto` 順序採系統解析結果，可能未涵蓋 IPv4 與 IPv6，沒有 Happy Eyeballs。
沒有 AAAA、IPv6 socket 不可用、無路由、TLS 憑證失敗與 HTTP timeout 是不同觀察，
都不足以單獨判定 ISP 或海纜故障。

各服務依序執行，並非同時控制組。需要比較時，保留各樣本時間，使用同一條線路、
相近時段、相同 family 與相同取樣設定，並考慮 DNS/CDN 地址可能不同。

## Ping、MTR 與未實作能力

Gateway 是使用者提供的標籤，程式不查證它真的為預設閘道。ICMP 無回應可能是
防火牆或控制平面限速。MTR 只保存原始輸出，不自動判定中繼節點故障；
工具 exit code 為 0 也不證明最後一跳有回應。`requested_cycles`、`requested_count`
是要求值，不能當成實際已發送封包數。

尚未測量：吞吐量、負載下延遲、jitter、可靠端到端封包遺失率、PMTU、HTTP/2/3、
影片 CDN 播放、精確回程與物理海纜路徑。NextTrace、Globalping、RIPE Atlas 與海纜
事件 Adapter 仍是 Roadmap。診斷報告應保留這些未知，不以推論補值。
