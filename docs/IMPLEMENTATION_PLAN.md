# 実装計画 — Codex Astra用

仕様の再議論だけで終了せず、この順に実装と検証を進めます。依存・コードはまだない状態が出発点です。

## M0. 土台

Django/Pythonの構成、uv lock、カスタムUser、SQLite設定、環境分離、テスト・Ruff・静的資産の構築を作成します。合成データだけで使えるseedを用意します。最初にアカウント・問題・リビジョン・回答の境界と制約を確定し、マイグレーションを追加します。

READMEに「現時点で実際に動く」セットアップを追記します。将来のコマンドを成功例にしません。

## M1. 認証と最小の学習経路

管理CLIで利用者を発行し、初回パスワード変更、ログイン、1問表示、タップ採点、解説表示をつなぎます。採点前に正解を送らないこと、未ログイン拒否、所有者検証、CSRF、回答の一意性まで一緒に実装します。

## M2. 出題・成績・復習

保存する学習キュー、絞り込み、順番／ランダム、最新回答集計、ブックマーク、復習を追加します。二つのアカウント・複数タブ・回答再送・空集合をテストします。

## M3. 画像・数式・import

ブロック構造、認証画像、拡大、数式、画像検証を実装します。`schemas/question-bundle.schema.json`、小さな合成bundle、dry-run、再取り込み、改訂、draft制御を作成します。

この工程で実問題・PDFをネットから集めないでください。図は著作物の切り抜きでなく、テスト用の単純な自作図にします。

## M4. 運用テンプレート

Dockerfile、Compose、`.env.example`、Nginx・DDNS・systemd・backup/restoreの例を作ります。SQLite snapshotとローカル復元は実装してテストします。遠隔通信・DNS書き換え・本番起動はしません。

`docs/DEPLOYMENT.md`と`docs/BACKUP_RESTORE.md`を追加し、値はすべて環境変数か予約済みの例示ホストにします。既存ホストのNginxやFWを上書きするワンライナーは作りません。

## M5. 品質・引き継ぎ

モバイルE2E、競合テスト、キャッシュ／権限、Ruff、Django check、マイグレーション検証、secret scanを実施します。GitHub ActionsのCI定義は追加できますが、最低限の`contents: read`権限にし、CD、SSH、DNS操作、秘密値投入を含めません。

全要件の実装状況をACCEPTANCEのIDで示し、HANDOFFを更新して終了します。未検証事項を「後で確認済みにする」と書き換えないでください。

## 推奨ディレクトリ

```text
app/
  config/                    # Django設定・URL・WSGI
  accounts/
  questions/
  learning/
  operations/
  templates/
  static_src/
  manage.py
schemas/
tests/
  fixtures/                  # 自作の合成データのみ
  e2e/
infra/
  nginx/
  systemd/
scripts/
docs/
Dockerfile
compose.yaml
pyproject.toml
uv.lock
.env.example
```

管理コマンドは`app/manage.py`を入口とします。SPEC内の`python manage.py`例は`app/`をカレントにした表記です。READMEではリポジトリルートから使えるコマンドに統一してください。

## 未指定の小さな判断

命名、URLパス、画面の余白、ライブラリの互換パッチ版などは自分で決めてDECISIONSへ記録します。公開範囲、認証、集計方法、外部サービス、本番操作の境界は変えません。

資料の不備・環境エラーで一部を進められない場合、独立して実装できる工程を先に進めます。制限を迂回して完成したことにせず、最後に再開位置と必要な人間の操作を残します。
