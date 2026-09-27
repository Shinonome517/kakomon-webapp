# バックアップと隔離復元

## ローカル操作

リポジトリルートで、未作成の出力先を指定する。

```sh
.venv/bin/python app/manage.py export_snapshot .local/backup-check
.venv/bin/python app/manage.py restore_snapshot .local/backup-check .local/restore-check
APP_RUNTIME="$PWD/.local/restore-check" .venv/bin/python app/manage.py check
APP_RUNTIME="$PWD/.local/restore-check" .venv/bin/python app/manage.py runserver 127.0.0.1:8001
```

`export_snapshot`は稼働中DBを単純コピーせず、SQLiteオンラインバックアップAPIを使う。スナップショットのintegrity_check後、DB参照先の不変画像を集め、SHA-256を検証する。DB・画像・バージョン・manifestが一時ディレクトリにそろってから完了先へ原子的に移す。既存出力先を上書きしない。

`restore_snapshot`はDB・画像のハッシュとintegrityを検証し、存在しない隔離ディレクトリへ復元する。復元DBのセッションは全削除するので全利用者が再ログインする。本番DBへ直接復元しない。アカウント・問題・最新回答集計・画像ハッシュが元と一致することは自動テストで確認した。ブラウザでの画像表示は実行環境の制約で未検証。

復元先でAPP_DBを使う場合は古い本番DBの値を引き継がない。隔離起動後に利用者数、問題数、成績、画像、パスワード再設定を確認し、停止時間・切り戻し先を用意してから人間が本番切替する。元のスナップショットは保管する。

## 日次の遠隔保存（テンプレート・未接続）

- `infra/backup.env.example`、`infra/ssh_config.example`、`scripts/backup.sh`、systemd service/timerを参照する。
- バックアップ実行ユーザーから、Tailscale経由で別拠点へ無人SFTP接続できることを人間が確認。ホスト鍵は別経路で照合し、専用known_hostsへ登録。`StrictHostKeyChecking yes`、`BatchMode yes`を維持する。SSH先の例を実値へ置換する作業は非公開設定で行う。
- ホスト側に同じlockのPython環境とNode.jsを用意する。バックアップ用APP_RUNTIMEはホストから見える同じ永続データを指す。本番コンテナにしかPythonがない構成なら、このホスト側CLIを先に準備する。
- バックアップステージとrestic cacheは実行ユーザーだけが読めるようにする。エクスポートには利用者・パスワードハッシュ・セッションが含まれる。ステージにはumask 077を適用。
- resticは暗号化SFTPリポジトリを使う。初期化・接続検証・復号鍵の別保管は人間が実施。アプリ秘密設定・Origin秘密鍵等は暗号化バックアップへ別途追加するか、安全な別保管場所へ置く。復号鍵をバックアップ元だけに置かない。
- 03:30 Asia/Tokyo、Persistent timer。flockで重複を拒否し、遠隔保存が成功した後だけ`last-success`を更新する。到達できなければ失敗終了し、既存成功マーカーとスナップショットを残す。
- ローカルステージの自動削除はしない。容量を監視し、遠隔保存と復元を確認してから不要な古いステージを人間が削除する。画像のGCは行わない。
- 初期保持案は日次14・週次8・月次3。`forget --keep-daily 14 --keep-weekly 8 --keep-monthly 3`とpruneは、復元試験後に人間が有効化する。自動削除・ミラーの`--delete`はテンプレートに含めない。

RPO目標24時間。停止・回線断で超過し得るため、`last-success`とjournalの失敗を毎日確認する。RTOは保証しない。遠隔resticから空の隔離領域へ復元後、ローカルの`restore_snapshot`で再検証する訓練を行う。遠隔接続・日次タイマー・本番復旧はこの実装作業では未実施。
