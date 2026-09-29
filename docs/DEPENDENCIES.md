# 依存と静的資産

Python 3.13.15で検証。直接依存と推移依存の正確な固定値・配布物ハッシュは`uv.lock`、ブラウザ資産は`package-lock.json`が正本。取得したスクリプトの自動実行は無効にしている。

| 依存 | 固定版 | 採用理由・公式資料 |
|---|---|---|
| Django | 5.2.17 | 認証・CSRF・セッション・ORM・migration。[認証](https://docs.djangoproject.com/en/5.2/topics/auth/default/)、[SQLite](https://docs.djangoproject.com/en/5.2/ref/databases/) |
| django-axes | 8.3.1 | DBに保存する有限時間のログイン制限。[設定](https://django-axes.readthedocs.io/en/latest/4_configuration.html) |
| Gunicorn | 23.0.0 | 単一インスタンスのWSGI実行。[設定](https://docs.gunicorn.org/en/stable/settings.html) |
| Pillow | 12.3.0 | 画像の実デコード・容量確認・メタデータ除去。[Image](https://pillow.readthedocs.io/en/stable/reference/Image.html) |
| jsonschema | 4.26.0 | Draft 2020-12の取り込み契約検証。[検証](https://python-jsonschema.readthedocs.io/en/stable/validate/) |
| markdown-it-py | 4.2.0 | 生HTMLを無効化できるMarkdownパーサー。[Security](https://markdown-it-py.readthedocs.io/en/latest/security.html) |
| nh3 | 0.3.7 | Markdown出力を許可タグだけへサニタイズ。[公式](https://nh3.readthedocs.io/en/latest/) |
| WhiteNoise | 6.12.0 | ハッシュ付き公開CSS/JSの配信。画像は対象外。[Django](https://whitenoise.readthedocs.io/en/stable/django.html) |
| KaTeX | 0.16.47 | 外部アクセスなしの数式描画と取り込み時の構文確認。[Options](https://katex.org/docs/options.html) |
| pytest / pytest-django | 9.1.1 / 4.14.0 | DB・HTTP・競合・運用検証。 |
| Ruff | 0.16.9 | lint・整形。 |
| Playwright | 1.63.0 | 幅別・通信切断・キーボードのE2E定義。 |
| uv | 0.12.19 | lock再現・仮想環境作成。 |

DjangoのIMMEDIATE／timeoutとKaTeXのtrust=falseを公式資料で確認した。django-axesなど一部の公式文書は未確認で、導入済み版のソース・API・自動テストで補った。保守更新時には公式文書、lock、全テストを再確認する。

KaTeXのJS・CSS・フォントとMITライセンスは`app/static_src/vendor/katex/`に同梱する。更新は`npm ci --ignore-scripts && npm run assets`。本番はCDN・外部フォント・解析を使わない。Node.jsは数式検証時のみ必要で、Webリクエスト中に起動しない。

Python依存はそれぞれの配布物のライセンスが適用される（Django/WhiteNoise: BSD、axes/markdown-it-py/nh3/jsonschema: MIT、Pillow: HPND、Gunicorn: MIT）。正確な文面はインストール済みdistributionのlicenseファイルを参照する。アプリのAGPLとは別である。
