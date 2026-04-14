# stockApp 棚卸し記録

## 2026-04-10
- stockApp棚卸し開始。26ページ→実運用は1ページ(コアサテライト管理)の現実を直視
- ゴーストファイル3つをarchive移動(commit済み)
- GitHub PAT と Anthropic API Key の漏洩事故を発見し両方revoke
- bash_history と git履歴のクリーンアップ完了

## 2026-04-11
- 新しいAnthropic API KeyをStreamlit Cloud Secretsに設定(ターミナル経由せず)
- VS Code導入。stockApp全体を初めて正しく可視化
- 3月24日のヒアドキュメント崩壊事故の全貌発見(空フォルダ多数: [github], =, cat, EOF, ANTHROPIC_API_KEY等)
- コアサテライト管理ページのリスクパリティがnan%バグを発見
- 異常フォルダ群の掃除とnan%バグ修正は別日
- nan%バグ調査: ローカルでyf.download→pct_change→stdは全て正常動作を確認。yfinance、コード、計算ロジックは無罪。原因はStreamlit Cloud側(キャッシュ、レート制限、または環境差)と特定。修正は別日: ①Streamlit Cloudでキャッシュクリア ②再デプロイ ③それでもダメならst.cache_dataを一時削除して検証