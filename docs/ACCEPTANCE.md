# 受け入れテストと公開前チェック

## A. 自動化必須

| ID | ケース | 合格条件 |
|---|---|---|
| A01 | 管理者発行→初回変更→ログイン | メール不要。旧一時パスワードが以後使えず、必須変更前には問題を読めない。 |
| A02 | ログアウト・無効化・リセット | ログアウトはPOST。無効アカウントと失効済みセッションはアクセス不可。 |
| A03 | 認証漏れ | 問題画面・JSON・画像・解説・成績の全経路で未認証を拒否。 |
| A04 | ユーザー間分離 | U1のsession/item/bookmark/history IDをU2が指定しても取得・変更できない。 |
| A05 | CSRF・入力検証 | CSRFなし／他オリジンの変更を拒否。別問題の選択肢・不正なIDも拒否。 |
| A06 | ログイン制限 | 連続失敗で有限期間の制限。一般化したエラー。復帰と他ユーザー影響を検証。 |
| A07 | 回答前の情報漏洩 | HTML/JSON/data属性/プリロードに正解ID・解説・解説専用画像を含めない。 |
| A08 | タップ即時採点 | 別の確定ボタン不要。保存成功後に正誤・正解・解説を表示し、自動遷移しない。 |
| A09 | 二重タップ・同一再送 | 同じitemで並行POSTしてもAnswerAttemptは1件。同じ選択肢なら同じ結果。 |
| A10 | 違う選択肢で同じitemを再送 | 既存の結果を変更せず、409相当と既存結果を返す。 |
| A11 | 保存後に応答が消失 | 再送・再読み込みで既存結果を回復し、成績を二重計上しない。 |
| A12 | 再学習 | 明示的な新しいitemで再回答でき、履歴が増える。単なる画面更新では増えない。 |
| A13 | 最新回答正答率 | A:誤→正、B:誤で50.0%。B:正で100.0%。未回答C追加でも正答率は変わらない。 |
| A14 | 未回答だけ／空集合 | 正答率は—、0除算なし。対象0件から学習開始できない。 |
| A15 | フィルター・復習 | 科目・実施回・分野と最終不正解／未回答／ブックマークのANDが正しい。 |
| A16 | 元順・ランダム | 元順が再現され、ランダムの1セッション内に重複がない。再読込でもキューを保持。 |
| A17 | 図・選択肢の図・解説の図 | 複数画像、順序、拡大、altを表示。解説画像への早期アクセスも拒否。 |
| A18 | 数式とXSS | インライン・独立数式を表示。script/生HTML/危険URL・外部画像の入力を無害化・拒否。 |
| A19 | 画像アクセス・キャッシュ | パス推測／未認証で取得不可。private, no-store。スタティック配信経路への迂回なし。 |
| A20 | import dry-run | 追加・更新見積もりが出るが、DB/media/履歴は一切変わらない。 |
| A21 | import再実行 | 同じbundleで件数不変。既存の履歴・ブックマークを維持。 |
| A22 | import異常入力 | 欠損画像、重複ID、複数正解、未知形式、巨大画像、外部パス、symlinkを拒否し部分公開なし。 |
| A23 | draftとwithdrawn | 未確認・取り下げを出題と現在集計から除外。直接URLでも本文・図を取得できない。 |
| A24 | 問題改訂 | 解説変更では成績維持。採点版変更では旧履歴保持・現在の未回答扱い。古いitem送信を拒否。 |
| A25 | SQLite競合 | 実ファイルDB・複数接続で、一意性・最新ID・有限リトライ・ロック失敗時の整合性を確認。 |
| A26 | DB export・restore | 稼働中の単純コピーを使わず、隔離復元後に件数・成績・画像hashが一致。 |
| A27 | DDNSロジック | GUA選択、temporary除外、候補曖昧時停止、API失敗、変更なし、proxied保持をモック検証。 |
| A28 | 本番設定 | SECRET等未設定でfail closed、DEBUG=False、Host制限、CSRF、HTTPS/cookie設定。 |
| A29 | 秘密情報とGit | check_public合格。実データ・秘密値・個人メモ・実行ログが追跡対象にない。 |
| A30 | 開発環境から再現 | fresh checkout＋lock依存でmigration・合成seed・起動・テストが再現できる。 |

## B. UI／E2E

Playwrightを基準に、少なくとも次を確認します。利用可能なブラウザだけ実施し、未実施のWebKit等は明示します。

| ID | 確認 | 基準 |
|---|---|---|
| B01 | 360px・390px・768px・PC | ページ横はみ出しなし。本文16px以上。選択肢44px以上。 |
| B02 | スマホの一連操作 | ログイン→フィルター→図の拡大→回答→解説→次へ→成績が操作できる。 |
| B03 | 通信エラー表示 | 送信中・保存不明・再試行が識別でき、二重タップで重複保存しない。 |
| B04 | アクセシビリティ | キーボード操作、見えるフォーカス、文字の正誤表示、結果の読み上げ通知。 |
| B05 | モーダル | 開閉・Esc・フォーカス復帰。大きな図が潰れずズームできる。 |
| B06 | デザイン | 緑・白・淡い黄の独自デザイン。既存サイトの資産コピーなし。 |

スクリーンショット・ブラウザログの出力先は`.local/`等のGit除外領域です。

## C. 人間が公開前に実機で行うこと

テンプレートと手順が完成していても、実環境で確認するまで「疎通確認済み」としないでください。

| ID | 実機チェック |
|---|---|
| C01 | N100上の永続ボリューム権限・再起動・コンテナ再作成後のデータ保持。 |
| C02 | NginxのIPv6:443、Origin証明書、Cloudflare Full (strict)、Host制限。 |
| C03 | ルーターとホストのIPv6 FW、Cloudflare送信元のみ許可、オリジンへの直接アクセス拒否。 |
| C04 | IPv4のみの外部回線とIPv6回線で、Cloudflare経由のログイン・採点・図を確認。 |
| C05 | 公開DNSはCloudflareのIPを返し、DDNSのAPI値だけが自宅GUAへ更新される。 |
| C06 | Cloudflare共有キャッシュへ問題・成績・画像が入らず、アカウント切り替えで混線しない。 |
| C07 | N100のバックアップ実行ユーザーから別拠点へ無人SFTP接続でき、ホスト鍵を検証する。 |
| C08 | 日次バックアップ成功・失敗・再開と、遠隔スナップショットから隔離環境への復元。 |
| C09 | 復号鍵の別保管、保存先空き容量、証明書期限、依存更新の確認方法。 |
| C10 | 実問題の権利・解答・解説・図を確認した後にのみverifiedで取り込む。 |


## 実装と検証結果

実行：`.venv/bin/pytest tests --ignore=tests/e2e --basetemp=.local/tmp/pytest -q` → **46 passed**。
テスト名の先頭に対象IDを含める。複数の異常入力はパラメータ化した独立ケースとして実行している。

| ID | 実装／検証の根拠 | 結果 |
|---|---|---|
| A01–A02 | `tests/test_accounts.py`：対話CLIを非表示入力の代替で呼び、実DB・標準ハッシュ・必須変更・同一パスワード拒否・他端末失効・14日設定／期限切れを検証。 | PASS |
| A03–A05 | `tests/test_learning.py`：未認証、ユーザー間のitem／履歴／画像／bookmark分離、CSRF・他origin・不正選択肢。 | PASS |
| A06 | `test_A06_limit_expiry_and_other_source`、`test_A06_source_limit_different_names`：5回、15分、送信元全体と別送信元、一般化エラー。 | PASS |
| A07 | `test_A03_A07_A19_protection_before_answer`：回答前HTMLから解説・正解フィールド・解説図URLを排除。推測URLも拒否。 | PASS（ブラウザ通信一覧は未検証） |
| A08 | `test_A08_A10_A11_A12_answer_retry`：通常POSTとJSON採点・解説、テンプレートに選択肢ボタンを実装。 | サーバーとブラウザPASS |
| A09–A12 | 同テストと`test_A09_A25_parallel_real_file`：再送・異なる回答409・再読み込み・明示した再学習・並行一意制約。 | PASS（ブラウザ応答消失・再送を含む） |
| A13–A16 | `test_A13_latest_statistics`、`test_A14_empty`、`test_A15_A16_filters_and_queue`：最新回答、未回答除外、AND、空集合、保存済み順序。 | PASS |
| A17 | 認証画像の実HTTP配信、画像メタデータ除去、複数ブロック・用途別参照。 | サーバーとブラウザの画像拡大PASS |
| A18 | `tests/test_import.py`：HTML・危険URL・外部画像拒否、不正数式draft。KaTeX／Markdown出力のローカル配信を実装。 | 入力検証とブラウザ数式描画PASS |
| A19 | `test_A03_A07_A19_protection_before_answer`：所有権、private/no-store、media迂回404。 | PASS、Cloudflare実キャッシュ未検証 |
| A20–A22 | `tests/test_import.py`：dry-runのDB/media/履歴不変、衝突拒否、再実行、未知形式・重複・外部パス・欠損・symlink・巨大図・画像中断。 | PASS |
| A23–A24 | 同ファイル：非公開の集計／直接アクセス除外、解説のみ維持、正解／図変更による採点版更新、古いitem409。 | PASS |
| A25 | `test_A09_A25_parallel_real_file`、`test_A25_lock_timeout_rolls_back`、`test_A25_parallel_distinct_items_latest_server_id`。 | 実ファイルDB・複数接続PASS |
| A26 | `tests/test_operations.py::test_A26_live_export_restore`：実DBのオンライン取得、隔離復元、件数・最新成績・画像hash・セッション失効、破損拒否。CLI手動実行も成功。 | PASS |
| A27 | `test_A27_gua_selection`、`test_A27_patch_noop_and_failure`。 | モックPASS、DNS API未接続 |
| A28 | 本番`check --deploy --fail-level WARNING`、Host/HTTPS/安全cookie設定、未設定・誤字・placeholder拒否。 | PASS |
| A29 | `scripts/check_public.py`と`git diff --check`。公開候補を走査、ログ等は除外領域のみ。 | PASS、Git変更操作なし |
| A30 | 除外領域の新規ディレクトリへ公開候補だけを複製し、空venvへlock依存をオフライン再取得。migration・合成import・collectstatic・check・migration差分なしを確認。 | PASS（実git cloneは行わない） |

静的検査：Ruff lint／format、Django check、migration差分検査、JavaScript構文検査、backup shell構文検査が成功。実HTTPでhealth・ログイン200を確認。

UI：`tests/e2e/test_browser.py`で360／390／768／1280px、ログイン→絞り込み→拡大→回答→次へ→成績、キーボード・Esc・フォーカス復帰、保存後応答消失→再送、JavaScript無効時POSTの**6件成功**。合成データの4幅スクリーンショットを`.local/screenshots/`に生成して確認した。WebKitは未実行。

Docker・Compose・Nginx・systemd・resticのテンプレートはコード上のレビューに限定する。実デーモンでの設定検証、コンテナビルド、GitHub Actions実行、C01〜C10は未実施。
