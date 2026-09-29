# Codex CLIの個人設定

このリポジトリではCodex CLIの設定とプラグインを個人環境で管理します。リポジトリの `.codex/` と `.agents/` はGitの除外対象です。実設定、認証情報、スキャン結果をGitへ含めないでください。

## モデルと実行権限

個人の `~/.codex/config.toml` に次を設定する例です。既存の個人設定を上書きせず、該当項目だけを確認してください。

```toml
model = "gpt-6-sol"
model_reasoning_effort = "medium"
sandbox_mode = "workspace-write"
approval_policy = "on-request"
```

通常の実装はGPT-6 Solを使い、設計や難しいレビューは `codex -m gpt-6-astra` で切り替えます。サンドボックスや承認を無効にしないでください。リポジトリの `AGENTS.md` が作業境界を定めます。

## プラグイン

Codex CLIの `/plugins` で公式の **Codex Security** を個人環境にインストールします。脆弱性の調査や差分レビューで必要なときだけ使い、検出結果は検証してから扱います。公式手順がスキャン品質のために推奨する `gpt-5.6-sol`／`xhigh` は、セキュリティスキャンだけの例外とします。

通常の開発にリポジトリ専用プラグインやGitHub書き込み用MCPを追加する必要はありません。OpenAI製品の仕様確認にはCodexに付属するOpenAI Docsを使います。プラグインのインストール後は新しいCodexセッションで認識を確認してください。

参考：[Codex設定](https://learn.chatgpt.com/docs/config-file/config-basic)、[Codex Security](https://learn.chatgpt.com/docs/security/plugin)、[GPT-6モデル](https://developers.openai.com/api/docs/models)。
