# 公開前の適用手順（人間用・未実機検証）

Codexは本番機・別ホスト・既存コンテナ・DNS APIへ接続していない。以下はレビューしてから人間が適用するテンプレートであり、そのまま実設定へ上書きしない。

## 構成

Cloudflareのプロキシ付きAAAA → IPv6:443のホストNginx → ループバック:18080 → 非root Gunicorn/Django → ローカルSSD上のSQLiteとmedia。Tunnelは使用しない。単一アプリ、1 worker・4 threads。SQLiteはIMMEDIATE、busy timeout 2秒、回答だけ最大3回の有限リトライ。大規模同時更新は想定せず、実機で測定してから別途見直す。

## 準備

1. ソースとlockをレビューし、Python 3.13／Node.jsと運用用uvを準備する。Docker・Compose・Nginx・restic・Tailscaleの導入とサービス変更は人間が行う。
2. `.env.example`を参照して秘密設定を作る。SECRET_KEYはランダムな50文字以上、ALLOWED_HOSTSは実際の公開名だけ、CSRF_TRUSTED_ORIGINSはHTTPS origin。空・既知プレースホルダー・環境名の誤字は起動拒否。`.env`をGitに含めない。SOURCE_URLには利用者が対応する全ソースを取得できるURLを設定する。
3. `runtime/`をUID/GID 10001が読書きできるよう人間が準備。DB・mediaはローカルSSDに永続化し、NFS/SMB/同期フォルダーへ置かない。Composeのホスト公開は`127.0.0.1:18080`のみ。初回migration、管理CLI、importは同じDB・mediaに対して実行する。Composeコンテナ再作成で保持されることを実機確認する。
4. コンテナの構築・migration・起動は人間が行う。`Dockerfile`と`compose.yaml`は本作業でデーモンを使用していないため、ビルド・起動未検証。`collectstatic`はビルド時、migrationは運用者の明示操作に分けている。

## Nginx／Cloudflare

- `infra/nginx/study.conf.example`を読む。`server_name`・証明書の位置を設定し、Nginxの静的検査後に適用する。未知のHostは拒否。実IPモジュールを有効にせず、`geo`で元のソケット接続元を判定する。
- Cloudflareの最新IPv6送信元レンジを公式一覧から人間が確認し、`<CIDR> 1;`の形式で許可ファイルを作る。同梱例は空なので既定で全拒否。更新失敗時は以前の検証済み一覧を保持し、全許可へ切り替えない。
- ルーターとホストのIPv6 FWの両方でCloudflare送信元だけを許可する。元IPv6の直接アクセスを拒否。固定の自宅GUAにbindせずIPv6:443で待ち受ける。ホストの他サービスへ設定を流用しない。
- CloudflareはFull (strict)、対象名のOrigin CA証明書または公開CA証明書を使う。Flexibleは禁止。Origin CAではプロキシをOFFにすると通常ブラウザは証明書を信頼しない。
- NginxはHost、HTTPS、検証済みクライアントIPを上書きし、利用者入力のX-Forwarded-Forを捨てる。Djangoは本番の検証済みヘッダーだけをaxesへ渡す。ループバック外からアプリポートへ接続できないことが前提。
- CloudflareのCache Rulesで動的HTML/API/画像をバイパスし、Cache Everythingを適用しない。アプリも`private, no-store`を返す。`/media/`は404、staticには問題画像を置かない。
- 利用者側IPv4/IPv6は通常の両対応のままにする。AAAAのみオリジンへ設定しても、利用者側をIPv6限定にしない。IPv4のみの外部回線とIPv6回線で二つの合成アカウントを使って確認する。

## DDNS

`infra/ddns.env.example`とsystemdのservice/timerを参照。NIC、必要ならプレフィックス、対象zone/record ID、対象名、トークンファイルを人間が設定する。トークンは対象ゾーンのDNS編集だけ。実値・secretはGit対象外。

`ip -j -6 address show`の有効な安定GUAだけを使い、temporary/deprecated/tentative/dadfailed/ULA/link-localを除外。候補が複数なら停止する。DNS APIで既存の固定IDをGETし、差がある時だけPATCHする。作成・削除は行わず、`proxied=true`・Auto TTLを維持する。公開DNSへの問い合わせ結果は比較しない。タイマーは5分、API失敗は最大3回で終了する。

DDNSの単体テストはモックだけで行った。実API更新、IPv6到達性、Cloudflare・FWの設定、証明書更新は未検証。

## 運用

- 健康確認は`/health/`。内容は最小限。DB利用・認証付き画像・採点は別の合成アカウントで確認する。
- ログにはパスワードやトークンを出さない。運用ログは公開しない。Composeは10MiB×3でローテーションする。
- 不要になったDjangoセッションは`clearsessions`で整理。問題画像のGC、履歴の自動削除はしない。
- 日次バックアップは[BACKUP_RESTORE.md](BACKUP_RESTORE.md)。証明書期限・依存更新・容量・最終成功時刻を運用者が確認する。
- 公開判断はACCEPTANCEのC01〜C10を完了してから。CI定義は検証だけで、CD・SSH・DNS操作を含まない。
