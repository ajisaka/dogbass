# `dogbass init` コマンドの追加

## 概要

素のテキストファイル (Front Matter を持たない Markdown など) に対し、dogbass が扱う YAML Front Matter ブロックを追加するサブコマンド `dogbass init` を追加する。タイトルはファイル名から拡張子を 1 つ除いた部分 (`Path.stem`) から自動的に導出する。

## 動機

現状、dogbass で DocBase に同期できる状態の Markdown を作るには `dogbass new` でテンプレートから新規作成する必要がある。既存の素の Markdown を後から dogbass 管理下に置く手段がないため、ローカルに既にあるメモやドキュメントを取り込みたいときに不便だった。`init` を追加することで、既存ファイルの本文をそのまま保ちながら、dogbass が必要とする Front Matter を後付けできるようにする。

## CLI インターフェース

```
dogbass init <file>
```

- 必須引数: `file` — 既存の通常ファイル (拡張子は問わない)
- オプション: なし
- 出力: 成功時に `Initialized front matter in <file>` を標準出力に出す (`new` の `Created Markdown file at ...` と同じトーン)

## 動作仕様

1. 引数の検証:
   - ファイルが存在しない、あるいはディレクトリの場合は Click 側で `UsageError` (`click.Path(exists=True, dir_okay=False)` による)
   - ファイルがすでに YAML Front Matter ブロックを含む場合は `FileConflictError` で中止。判定基準は `_extract_raw_front_matter_yaml` と同じ (改行を LF 正規化したうえで `---\n` で始まり、後続に閉じる `---` 行を持つ) とする。先頭が `---\n` でも閉じる `---` がなければ Front Matter とはみなさない。
   - `path.stem` を `strip()` した結果が空文字の場合は `ValidationError` (防御的チェック。通常のファイル名では発生しない)
2. ファイル本文を読み取る。元の改行スタイル (LF/CRLF/CR) と末尾の改行有無は保持する。
3. タイトルは `path.stem` を使用する。前後の空白は `strip()` する。
4. `new` コマンドと同じデフォルト値で Front Matter を構築:
   - `title: <stem>`
   - `tags: []`
   - `draft: true`
   - `notice: true` (テンプレートコメント `# notice: false` を併記)
   - `scope: private` (テンプレートコメント `# scope: everyone` `# scope: group` と groups ヒントを併記)
   - `id` は付与しない
5. 可能であれば `DocBaseClient.from_env().list_groups()` を呼び出し、groups コメントに DocBase 上のグループ一覧を埋め込む。`AppError` で失敗した場合は無視して続行する (`new` と同じパターン)。
6. ファイル先頭に Front Matter ブロックを挿入し、元の本文と元の改行スタイルを保持してファイルを上書きする。

## アーキテクチャ

### `dogbass/markdown.py`

新関数を追加する:

```python
def init_markdown_document(
    path: Path,
    title: str,
    available_groups: list[dict[str, Any]] | None = None,
) -> None
```

責務:
- 上記「動作仕様 1〜3」のバリデーション
- 既存本文と改行スタイルの読み取り
- `MarkdownDocument` を組み立て、本文に元ファイルの内容を入れる
- Front Matter + テンプレートコメントを付けてレンダリング (`_render_new_document` 相当)
- 元の改行スタイルに合わせて書き戻す

実装上の注意:
- Front Matter の有無判定は `_extract_raw_front_matter_yaml` の規約 (LF 正規化後に `---\n` で始まり、後続に閉じ `---` がある) と整合させる。専用ヘルパー `_has_front_matter(raw_text: str) -> bool` を追加して `init_markdown_document` から呼ぶ。
- 改行スタイルの保持は既存の `_render_post` 末尾と同等のロジックを利用する。`_render_new_document` を直接呼ぶと LF に正規化されてしまうため、ヘルパーで改行を後処理するか、`_render_post` と共通化できる小さな内部関数を切り出す。
- 既存の `create_markdown_document` (新規作成) と `init_markdown_document` (既存ファイルへ FM 追加) は別関数として並存させる。前者はファイル不在を要求し、後者はファイル存在を要求するため、混ぜると条件分岐が複雑になる。

### `dogbass/cli.py`

新サブコマンド `init_command` を追加する。

```python
@main.command("init")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@app_error_handler
def init_command(file: Path) -> None:
    """Add dogbass front matter to an existing plain text file."""
    title = file.stem
    if not title.strip():
        raise ValidationError("filename must have a non-empty stem")
    available_groups: list[dict[str, Any]] = []
    try:
        client = DocBaseClient.from_env()
        available_groups = client.list_groups()
    except AppError:
        pass
    init_markdown_document(file, title, available_groups=available_groups)
    click.echo(f"Initialized front matter in {file}")
```

`click.Path(exists=True, dir_okay=False)` で「存在するファイルであること」を Click 側に任せる。stem の空チェックだけ CLI 側で行う (markdown.py 側でも防御的にチェックしてもよい)。

## エラーハンドリング

- ファイル不在 / ディレクトリ → Click が `UsageError` を発生 (終了コード 2)
- 既存 Front Matter あり → `FileConflictError` (終了コード 1)
- stem が空 → `ValidationError` (終了コード 1)
- DocBase 接続不可 → 黙って groups ヒントだけ簡略化して続行 (`new` と同じ挙動)

エラーは `app_error_handler` デコレータで `AppError` → `click.exceptions.Exit(exit_code)` に変換される。

## テスト

`tests/test_cli.py` に以下を追加する (既存の `CliRunner` + `FakeDocBaseClient` パターンを踏襲):

正常系:
- `notes.md` に対して実行 → ファイルに FM が付与され、タイトルが `"notes"`、本文が元のまま保持される
- `notes.txt` に対して実行 → 同上 (拡張子に依存しない)
- 拡張子のないファイル `README` に対して実行 → タイトルが `"README"`
- LF 改行の本文 → LF が保持される
- CRLF 改行の本文 → CRLF が保持される
- `FakeDocBaseClient.list_groups()` が値を返す場合、groups コメントに反映される
- DocBase の環境変数が未設定の場合でも成功し、groups コメントは簡略テンプレートになる

異常系:
- 引数のファイルが存在しない → Click の `UsageError` (終了コード 2)
- 引数がディレクトリ → Click の `UsageError` (終了コード 2)
- ファイル先頭にすでに `---\n...\n---` がある → `FileConflictError` で終了コード 1、ファイルは書き換わらない
- 先頭が `---\n` だが閉じる `---` がない場合は Front Matter とみなさず、正常に追加できる

## 影響範囲

- 新規コマンドの追加のみ。既存の `new` / `push` / `pull` / `groups` / `install-hook` / `sync-commit` の挙動は変更しない。
- `dogbass/markdown.py` に新関数と小さな内部ヘルパーが増えるが、公開 API の変更はない。
- README / CLAUDE.md は次の PR でコマンド一覧を更新する余地があるが、本仕様の範囲外とする (本仕様では CLAUDE.md は更新しない)。

## 非ゴール

- `init --title` のような上書きオプションは追加しない (要望があれば後日)。
- 既存 Front Matter のマージや上書きは行わない (常にエラー)。
- DocBase へのプッシュは行わない (`init` 後にユーザーが `push` を実行する想定)。
- ファイル拡張子のチェックや `.md` への自動リネームは行わない。
