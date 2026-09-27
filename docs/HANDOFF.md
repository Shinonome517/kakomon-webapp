# 実装状況と引き継ぎ

最終更新：2026-09-27

## 現在の状態

v0.1のアプリ、合成問題、サーバー側テスト、運用テンプレートを実装した未コミットの作業ツリー。主要機能はローカルで検証済み。ブラウザE2Eは環境による起動失敗で未検証。Gitのadd/commit/push等、本番・遠隔操作は行っていない。

## 完了した工程

- M0：Python 3.13.15、Django 5.2.17、uv/npm lock、カスタムUser、migration、SQLite IMMEDIATE、ローカル静的資産。
- M1：管理CLI、メール不要ログイン、初回／リセット後の変更、POSTログアウト、axes制限、所有者／CSRF検証、一問表示、即時採点・解説。
- M2：保存キュー、複数フィルター、順番／ランダム、最新有効回答の成績、復習、ブックマーク、履歴、二重送信の冪等性。
- M3：JSON Schema、合成6問、複数図、認証画像、KaTeX、dry-run、再取り込み、非公開、採点版変更、改訂履歴。
- M4：Docker/Compose/Nginx/DDNS/systemd/resticのテンプレート、SQLiteオンラインスナップショット、画像hash検証、セッション無効化付き隔離復元。
- M5：独立した読み取りレビューを実施し5件を修正。回帰テスト・Ruff・起動検証・文書・CI定義を追加。E2Eの実行完了は残っている。

工程の節目ごとに当ファイルへ保存し、最終結果へ整理した。細部の判断はDECISIONS、受け入れID別の結果はACCEPTANCEを参照。

## 実行した検証

- `.venv/bin/pytest tests --ignore=tests/e2e --basetemp=.local/tmp/pytest -q`：**46 passed**。
- 複数接続の実ファイルSQLite：同じitemの並行保存一件、別itemの最新ID集計、ロック時最大3回・ロールバック成功。
- `.venv/bin/ruff check app tests scripts`／`ruff format --check app tests scripts`：PASS。
- Django check、makemigrations --check --dry-run：PASS。テスト内の本番check --deployも警告なし。
- JavaScript 3ファイルの`node --check`、`sh -n scripts/backup.sh`：PASS。
- 合成import dry-run／通常／再実行、管理CLIのテスト、オンラインexport→隔離restore：PASS。
- 新規の隔離ソースディレクトリ＋空venvで`uv sync --frozen --offline`、migration、合成import、collectstatic、check、migration差分なし：PASS。
- ローカルrunserverの実HTTP：healthとログインが200。
- `scripts/check_public.py`、`git diff --check`：PASS。これは補助検査であり、人間の公開差分レビューも必要。

失敗を修正した事項：静的manifest不足のセットアップ手順、同一パスワードによる必須変更迂回、既知placeholder秘密鍵、APP_ENV誤字、dry-runのDB衝突、画像中断書込み。

詳細ログは`.local/logs/`のみ。ローカルDBと画像は`runtime/`、検証用の複製・復元は`.local/`。公開文書へ生ログは転記していない。

## 未完了／未検証

- **ブラウザE2E 6ケース**：配布Chromeの取得が許可先制限403。既存ChromeもSIGABRTで起動不能。UI描画・幅・操作・実通信切断・スクリーンショットは未検証。WebKit未実行。テスト定義は残し、skipやモックへ置換していない。
- 必要な取得先：`cdn.playwright.dev`（Chrome配布先へリダイレクトする場合を含む）。制限・プロキシ・サンドボックスを変更していない。依存公式文書の一部も403／接続エラーで取得できず、DEPENDENCIESに記録。
- Dockerビルド、Compose起動、Nginx/systemd実機検査、GitHub Actionsのリモート実行は未実施。
- 本番N100・Cloudflare・DNS API・FW・IPv4/IPv6外部疎通・Tailscale・遠隔restic・日次timerは未接続／未検証。C01〜C10は人間が実施する。
- 実問題の収集・権利確認・解答照合は範囲外。同梱は合成問題だけ。

## 翌朝の操作／再開位置

1. READMEのローカル手順で起動。`create_learner`からアカウントを発行し、初回変更→問題→図→採点→成績を確認する。
2. ブラウザ実行可能な環境で`playwright install chromium`後、`pytest tests/e2e --basetemp=.local/tmp/e2e -q -x`を実行し、失敗は直す。360/390/768/1280pxとキーボードを合成データで確認。成功するまでUIを検証済みにしない。
3. `git status`・差分・公開候補を人間がレビューする。commit/pushはまだ行っていない。
4. 公開する場合のみ、非公開の本番値・対応ソースURL・証明書・最小権限token・復号鍵を用意し、DEPLOYMENT／BACKUP_RESTOREとC01〜C10を実施する。実環境の適用は人間が判断する。
