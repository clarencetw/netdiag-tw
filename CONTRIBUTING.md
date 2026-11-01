# 參與 NetDiag TW

回報 Issue 請提供：OS 與 Python 版本、有線／Wi-Fi、VPN／Proxy、IPv4／IPv6、**已遮罩**的指令與錯誤、預期與實際結果。請勿貼上公網／內網 IP、Router 名稱、住址、HAR、Cookie、Token。

開發前檢查（離線，不連網）：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/netdiag.py plan
python3 -m compileall -q scripts tests
```

- 新增連網測試須明確 opt-in。
- 新增指標須定義起訖、分母、失敗樣本處理，並驗證 JSON 與 Markdown 一致。
- 測試資料只寫入 `results/`；`examples/` 僅放標示清楚的合成資料。
- 新增外部相依或服務前，記錄來源、授權與資料傳送範圍。
- PR 請說明原因、替代解釋、平台驗證與隱私影響。

Commit 訊息遵循 [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)：`type(scope): description`，scope 可省略。新增功能用 `feat`，修正用 `fix`，文件用 `docs`；只有破壞性變更才加 `!` 或 `BREAKING CHANGE`。功能與文件整理可分開提交。

本專案維持 **Early Development**，不自動建立 tag／Release。Commit、Push、發布各自依維護者授權。公開前檢查隱私、MIT 署名、第三方授權與安全回報管道（見 SECURITY.md）。CI 通過只代表該提交的離線測試，真實平台與網路驗證另列；不要沿用過往成功宣稱新提交已驗證。
