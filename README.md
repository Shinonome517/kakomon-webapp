# 一陸特 学習ノート v0.1

スマホで一問ずつ解く、セルフホストの学習Webアプリ。Django 5.2 LTS＋SQLite、管理者発行のユーザー名認証、選択肢タップ採点、各問題の最新回答による成績、復習・ブックマーク、認証付き複数画像・数式、JSON取り込み、バックアップ／隔離復元を実装しています。

同梱6問は**自作の動作確認用・試験対策用ではない合成問題**です。実問題・PDF・利用者情報・秘密値は含めません。実装と検証結果は[HANDOFF](docs/HANDOFF.md)、要件との対応は[ACCEPTANCE](docs/ACCEPTANCE.md)を参照してください。ChromiumブラウザE2Eは検証済み、本番構成は未検証です。

## ローカルで起動

Python 3.13、uv、Node.jsを別途準備済みの環境で、リポジトリルートから実行します。OSの自動変更はしません。

```sh
mkdir -p .cache/uv .cache/npm .cache/ms-playwright .local/tmp .local/logs
export UV_CACHE_DIR="$PWD/.cache/uv"
export UV_PYTHON_DOWNLOADS=never
export npm_config_cache="$PWD/.cache/npm"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/ms-playwright"
export TMPDIR="$PWD/.local/tmp"
uv sync --frozen --python python3.13
npm ci --ignore-scripts
npm run assets
.venv/bin/python app/manage.py migrate
.venv/bin/python app/manage.py collectstatic --noinput
.venv/bin/python app/manage.py import_questions tests/fixtures/synthetic --dry-run
.venv/bin/python app/manage.py import_questions tests/fixtures/synthetic
.venv/bin/python app/manage.py create_learner --username demo-learner
.venv/bin/python app/manage.py runserver 127.0.0.1:8000
```

ブラウザで `http://127.0.0.1:8000/` を開きます。CLIは12文字以上のパスワードを非表示で二回入力させます。ログイン後、本人が異なるパスワードへ変更するまで問題は見られません。固定アカウントや固定seedパスワードは作りません。管理コマンドはOSで実行できる運用者専用です。

```sh
.venv/bin/python app/manage.py reset_learner_password --username demo-learner
.venv/bin/python app/manage.py disable_learner --username demo-learner
```

リセットは他端末のセッションを失効させ、初回変更を再び必須にします。公開サインアップ、メール認証、Django adminの公開ルートはありません。

## 学習と取り込み

科目・年度／実施回・分野は取り込んだデータから選べます。未選択はすべて。復習対象とのANDで絞り込み、元順または保存されたランダムキュー、10・20・50・すべてを選べます。採点後は自動遷移せず、解説を読んで次へ進みます。通信切断時は同じ学習項目・同じ回答だけを再送し、再読み込みでも保存結果を復元します。

独自のバンドルは[JSON Schema](schemas/question-bundle.schema.json)と[合成サンプル](tests/fixtures/synthetic/manifest.json)を参照してください。

```sh
.venv/bin/python app/manage.py import_questions imports/example-bundle --dry-run
.venv/bin/python app/manage.py import_questions imports/example-bundle
```

入力は展開済みディレクトリ内のmanifestとPNG/JPEG/WebPです。HTML・外部画像・パス逸脱・symlink・不正な参照は拒否し、画像はメタデータを除去して不変ハッシュで保存します。数式はローカルKaTeXで検証します。未確認・不正な数式はdraftとなり、verifiedだけを出題します。画像欠損等はバンドル全体を拒否して部分公開しません。

同一内容の再投入は変更なし。解説のみの改訂は成績を維持し、本文・選択肢・正解・採点用図の改訂は採点版を更新して再学習扱いにします。古い履歴と論理問題へのブックマークは残ります。実問題の権利・正確性は人間が確認してから投入してください。

## 検証

```sh
.venv/bin/pytest tests --ignore=tests/e2e --basetemp=.local/tmp/pytest -q
.venv/bin/ruff check app tests scripts
.venv/bin/ruff format --check app tests scripts
.venv/bin/python app/manage.py check
.venv/bin/python app/manage.py makemigrations --check --dry-run
.venv/bin/python scripts/check_public.py
git diff --check
```

UIテストの実行可能環境では、次を追加します。ダウンロード拒否時はネットワークやサンドボックスを解除せず、接続先を管理者へ伝えてください。

```sh
.venv/bin/playwright install chromium
.venv/bin/pytest tests/e2e --basetemp=.local/tmp/e2e -q -x
```

既存のテスト用ブラウザを使う場合は`PLAYWRIGHT_EXECUTABLE_PATH`を指定できます。個人のブラウザプロフィールは使用しません。スクリーンショットは合成データだけを`.local/screenshots/`に保存します。Playwright ChromiumでE2E 6件が成功しました。WebKitは未実行です。

GitHub ActionsのCIは定義のみで、`verify` はリモート未実行です。デプロイは行っていません。

開発時の作業境界は[AGENTS.md](AGENTS.md)、Codex CLIの個人設定は[Codexセットアップ](docs/CODEX_SETUP.md)を参照してください。通常の不具合はIssueへ、未公開の脆弱性は[セキュリティポリシー](SECURITY.md)に従い非公開で報告してください。

## バックアップと公開

ローカルで実行済みの例です。出力先は未作成のディレクトリにします。

```sh
.venv/bin/python app/manage.py export_snapshot .local/backup-check
.venv/bin/python app/manage.py restore_snapshot .local/backup-check .local/restore-check
```

[バックアップと復元](docs/BACKUP_RESTORE.md)、[公開手順](docs/DEPLOYMENT.md)、[依存の固定と理由](docs/DEPENDENCIES.md)を参照してください。IPv6 DDNS＋Cloudflareプロキシ＋ホストNginx用のテンプレートを用意しています。Tunnelや外部DBは使いません。実環境への接続・コンテナ操作・DNS API呼出し・遠隔保存は人間の別作業です。

主な環境変数：`APP_ENV`、`DJANGO_SECRET_KEY`、`DJANGO_ALLOWED_HOSTS`、`DJANGO_CSRF_TRUSTED_ORIGINS`、`APP_RUNTIME`、任意の`APP_DB`と`SOURCE_URL`。開発既定のDB/mediaは`runtime/`です。本番は`.env.example`を参照し、設定不備では起動を拒否します。

## ライセンスと公開範囲

ソフトウェアは[AGPL-3.0-only](LICENSE)。ネットワーク提供時は改変を含む対応ソースを利用者が取得できるよう、`SOURCE_URL`を設定してください。同梱ライブラリのライセンスは別途保持します。

第三者の試験問題・解答・PDF・教材への利用許諾は含みません。実データ、画像切り抜き、利用者情報、DB、バックアップ、秘密値、実行ログ、個人メモはGitへ含めません。公開前に`check_public.py`と差分の目視レビューを実行します。補助スキャンはあらゆる秘密情報を検出するものではありません。
