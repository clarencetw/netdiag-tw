# 量測定義與限制

每個樣本：新的 TCP/TLS 連線、HTTPS/443、`GET /`、HTTP/1.1，不跟隨轉址。

| 欄位 | 定義 | 不能解讀為 |
|---|---|---|
| `dns_ms` | 系統解析器耗時（含 cache） | DNS 伺服器封包 RTT、DoH 時間 |
| `tcp_ms` | 成功那次 connect 耗時 | 單一封包 RTT |
| `tls_ms` | TLS 握手耗時 | 純路由延遲 |
| `http_response_ms` | GET 完成送出後到第一個回應 byte | 整頁載入、影片起播 |
| `elapsed_to_first_byte_ms` | 樣本開始到第一個 HTTP byte | 各階段直接相加 |
| `https_responses / samples` | 取得最終 HTTP 狀態列（200–599）的比例 | 封包成功率；302、403 也算有回應 |

- `p50` 為中位數，`p95` 為 nearest-rank（排序後第 `ceil(0.95 × n)` 筆）；少量樣本的 p95 常等於最大值。
- 各階段只統計有值的樣本，缺值不補零；請同時看有效樣本數與錯誤數。
- `report` 由 `samples` 重算摘要，不信任 JSON 內可能過期的 `summary`。
- `--timeout` 分別限制 DNS、每次 TCP、TLS、整個 HTTP 階段；不是整輪總時限。系統 DNS 逾時後底層查詢無法取消，最多保留四個，滿額記為 `local_resolver_capacity`。
- 最多試前四個公開 IP，只有 TCP 失敗才換址。`auto` 不模擬 Happy Eyeballs。
- 各站依序測量，不是同時對照；比較時請用同線路、相近時段、相同 family。
- Gateway 由使用者指定，程式不驗證；ICMP 無回應可能只是限速。MTR 只保存原始輸出，不自動判定節點故障。

尚未測量：吞吐量、負載延遲、jitter、封包遺失率、PMTU、HTTP/2/3、影片 CDN、精確回程與實體海纜路徑。

## 分組與資料範圍

分組依網站用途或服務市場，並非已驗證的節點所在地；`baseline` 不是 LAN 或近端探針，`tw`／`region` 也不能證明國內／國際路徑。分組 p50 對全部有值樣本合併計算，非各站中位數平均；各站樣本數不等時權重也不同。必須一起看各項有效樣本數、失敗數與單站結果，不用分組快慢定位出口或海纜。

HTTP 首 byte 可能屬於 1xx 暫時回應，甚至後來判定無效的回應；有計時不代表取得最終狀態列。EOF 前沒有 byte 就不填首 byte 計時。整個 HTTP 階段最多消耗 4096 個應用層回應 bytes，底層 buffering／實際傳輸可能更多。

`tcp_ms` 只含成功那次 socket 建立與 connect，失敗嘗試另列 `tcp_attempts`；整體首 byte 時間也包含先前嘗試、TLS 設定與本機開銷。缺值不等於零，也不把 timeout 填成成功延遲。`stage_counts` 為有值樣本數。`schema_version` 是資料格式，不是發行版號；舊資料沒有 group 時不產生分組表。

MTR 的 cycle 是每跳輪數，不是總封包數；`requested_count`／`requested_cycles` 是要求值，工具 exit code 0 也不證明目的端有回應。TLS 信任根載入等本機開銷不受網路 timeout 完整限制。
