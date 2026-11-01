# 公開狀態與維護檢查

本專案定位為 **Early Development**；目前不建立版本標籤或 GitHub Release。

2026-11-02 維護者確認測試結果並授權 Commit／公開／Push。發布檢查時，
`clarencetw/netdiag-tw` 已是該帳號下的空公開 Repository，因此直接使用既有 Repository。

## 已完成的公開準備

- 本機 Mac 已完成授權的 18 次 HTTPS 入口測試；接入方式未確認，保留 access=unknown。
- 40 項離線測試通過；Linux／macOS／Windows 的 CI 矩陣涵蓋 Python 3.10／3.12／3.14。
- 待提交內容經獨立隱私審查；原始量測 `results/`、快取與環境設定不納入 Git。
- 公開提交使用此帳號的 GitHub noreply 地址，避免暴露本機私人 email。
- MIT LICENSE 與既有著作權署名保留。
- README 優先呈現 AI 操作，明示內建量測仍依賴本機 Python；不宣稱免安裝。
- Issues 與私人安全漏洞回報已啟用，附錯誤回報與 PR 模板。

## 持續檢查

每次 Push 後都應確認 [GitHub Actions](https://github.com/clarencetw/netdiag-tw/actions/workflows/test.yml)
對應提交的九個矩陣工作全部成功。以該次 run 的實際結果為準，不以 workflow 存在或
過往成功推定新提交也通過。CI 是離線測試，不代表各平台實際固網品質已驗證。

提交前檢查真實診斷資料與憑證；更新 README 的實作／規劃界線。新版本標籤、Release、
進一步連網測試與部署需要各自授權。

Repository description：

> Local-first Taiwan broadband diagnostics: an AI Skill and Python HTTPS probe with evidence-based ISP reports. Early Development.

已設定 Topics：

`network-diagnostics`, `taiwan`, `python`, `agent-skills`, `dns`, `ipv6`, `troubleshooting`

本專案只使用 Python 標準函式庫，沒有打包第三方路由工具。
NextTrace、Globalping、RIPE Atlas、海纜事件與影音量測均維持 Roadmap，整合前個別審閱
當時的 API、額度、授權、隱私與使用者同意流程。免裝 Python 的交付方式仍需驗證需求，
打包執行檔只是候選方案，尚未提供安裝器或二進位下載。
