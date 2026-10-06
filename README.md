# 学習ノート

問題データを取り込んで、一問ずつ学習するセルフホストWebアプリです。Django＋SQLiteで動作します。

- 管理者発行のユーザー名・パスワードでログイン
- 選択肢を押して即時採点、解説・画像・数式を表示
- 各問題の最新有効回答による成績、復習、ブックマーク
- 科目・年度／実施回・分野で絞り込み
- JSON＋画像の取り込み、バックアップ・隔離復元

同梱の6問は自作の動作確認用合成問題です。実問題・PDF・利用者データ・秘密値は含みません。

## ローカル起動

Python 3.13、uv、Node.jsを準備し、リポジトリルートで実行します。

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

`http://127.0.0.1:8000/` を開きます。アカウント作成時は12文字以上のパスワードを入力し、初回ログイン後に変更します。公開サインアップはありません。

独自の問題データは [JSON Schema](schemas/question-bundle.schema.json) と [合成サンプル](tests/fixtures/synthetic/manifest.json) を参照し、`import_questions <バンドルディレクトリ> --dry-run` で確認してから取り込みます。権利と内容を人間が確認した `verified` の問題だけを出題します。

## 開発

新機能・通常の不具合修正は **Issue起票 → Issue番号付きブランチ → 実装・検証** の順に進めます。ブランチ名は `feat/<Issue番号>-<短い説明>` または `fix/<Issue番号>-<短い説明>`。詳細と操作の境界は [AGENTS.md](AGENTS.md) を参照してください。

製品要件は [SPEC](docs/SPEC.md)、受け入れ条件と検証記録は [ACCEPTANCE](docs/ACCEPTANCE.md) が正本です。

```sh
.venv/bin/pytest tests --ignore=tests/e2e --basetemp=.local/tmp/pytest -q
.venv/bin/ruff check app tests scripts
.venv/bin/ruff format --check app tests scripts
.venv/bin/python app/manage.py check
.venv/bin/python app/manage.py makemigrations --check --dry-run
.venv/bin/python scripts/check_public.py
git diff --check
```

ブラウザE2EはPlaywrightを使います。上記のキャッシュ設定で `.venv/bin/playwright install chromium` 後、`.venv/bin/pytest tests/e2e --basetemp=.local/tmp/e2e -q -x` を実行します。既存のChromium系テスト用ブラウザは `PLAYWRIGHT_EXECUTABLE_PATH` で指定できます。WebKitをインストール済みなら `PLAYWRIGHT_BROWSER=webkit .venv/bin/pytest tests/e2e --basetemp=.local/tmp/e2e-webkit -q` で同じケースを検証できます。

## 運用・ライセンス

- [公開手順・設定](docs/DEPLOYMENT.md)：IPv6 DDNS＋Cloudflareプロキシ＋Nginx
- [バックアップと復元](docs/BACKUP_RESTORE.md)
- [依存関係](docs/DEPENDENCIES.md)
- [セキュリティポリシー](SECURITY.md)：未公開の脆弱性は非公開で報告

ソフトウェアは [AGPL-3.0-only](LICENSE) です。ネットワーク提供時は、改変を含む対応ソースを取得できるよう `SOURCE_URL` を設定してください。第三者の問題・解答・教材の利用許諾は含みません。実データ・DB・バックアップ・秘密値はGitに含めないでください。本番構成の実機検証は未実施です。
