# 參與 NetDiag TW 測試與開發

感謝協助測試。這個專案仍在開發中，請優先回報能被重現的問題。

## 回報 Issue 時

請提供：

- OS 與 Python 版本（例如 macOS 15 / Python 3.12）。
- 有線 / Wi-Fi、是否使用 VPN / Proxy、IPv4 或 IPv6。
- **已遮罩**的 CLI 指令與錯誤訊息，及預期／實際結果。
- 是否能重現，是否只發生在尖峰時段。

**請勿公開**公網／內網 IP、Router 名稱、詳細住址、完整網路拓樸、完整 HAR、Cookie、Token 或可識別你的資訊。`results/` 預設不納入 Git。

## 開發前基本檢查

```bash
python3 -m unittest discover -s tests -v
python3 scripts/netdiag.py plan
python3 -m py_compile scripts/netdiag.py
```

離線測試不應自行呼叫外部網站。新增需連網的 integration tests 時，應採明確 opt-in，並說明流量和測量對象。

Pull Request 請說明變更原因、涉及的量測定義、替代解釋、平台驗證結果，以及對使用者隱私的影響。

## 公開前與跨平台驗證

Repository 的最新 CI 結果請查看 GitHub Actions；不要將已寫入 workflow 視為已通過。請分別記錄 macOS、Linux、Windows 的 Python 版本、離線測試結果與經同意的真實網路結果；尚未執行就標示未驗證。

測試資料一律寫入 `results/`。`.gitignore` 不是隱私過濾器，也不會遮罩任意位置的檔案；提交前確認沒有真實診斷結果。`examples/` 僅放明確標示的合成資料。新增指標須定義起訖時間、分母、失敗樣本處理與分位數算法，並驗證 JSON 與 Markdown 一致。

MIT 授權見 `LICENSE`。第三方工具目前不隨專案散布；新增相依或外部服務前，請記錄來源、授權、資料傳送範圍與呼叫限制。
