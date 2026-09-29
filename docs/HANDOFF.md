# 実装状況と引き継ぎ

## 現在の状態

v0.1のアプリ、合成問題、テスト、運用テンプレートを実装済み。本番・遠隔操作は未実施。

## 完了項目

- 管理CLI、ユーザー名認証、初回パスワード変更、ログイン制限、所有者・CSRF検証。
- 一問ずつの即時採点、保存キュー、絞り込み、復習、ブックマーク、最新の有効回答による成績、二重送信の冪等性。
- JSON取り込み、合成6問、認証付き画像、数式、問題改訂と採点版管理。
- Docker/Compose/Nginx/DDNS/systemd/resticのテンプレート、SQLiteオンラインスナップショットと隔離復元。

## 検証結果

- `.venv/bin/pytest tests`：52件成功（サーバー46件、Chromiumブラウザ6件）。
- Chromiumで360／390／768／1280pxの合成データ画面、回答・再送・画像拡大・数式・キーボード操作を確認。
- Ruff lint／format、Django check、migration差分検査、JavaScript／シェル構文検査、公開候補検査に成功。
- 複数接続のSQLite競合、取り込み再実行、バックアップからの隔離復元、隔離ソースでのlock依存再現を確認。

受け入れ項目別の結果は[ACCEPTANCE](ACCEPTANCE.md)を参照。

## 未検証

- WebKitと実回線切断。ブラウザの応答破棄による再送は検証済み。
- Dockerビルド・Compose起動・Nginx/systemd実機検査・GitHub Actionsのリモート実行。
- 本番環境、Cloudflare・DNS API・外部疎通・Tailscale・遠隔restic・日次timer。公開前項目C01〜C10は人間が確認する。
- 実問題の収集・権利確認・解答照合。同梱データは合成問題のみ。
- 一部依存の公式文書の再確認。詳細は[DEPENDENCIES](DEPENDENCIES.md)を参照。

## 次の操作

1. READMEのローカル手順でアカウント発行から成績表示まで確認する。
2. `.local/screenshots/`の合成データ画面と差分をレビューする。
3. 公開する場合は[DEPLOYMENT](DEPLOYMENT.md)と[BACKUP_RESTORE](BACKUP_RESTORE.md)に従い、C01〜C10を人間が検証する。
