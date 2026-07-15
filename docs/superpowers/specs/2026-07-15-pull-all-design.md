# `dogbass pull-all` コマンドの追加

## 概要

指定したユーザー (省略時はアクセストークンの持ち主自身) が DocBase 上に書いた記事を全件取得し、`${id}-${タイトルのスラグ}.md` というファイル名でディレクトリに書き出す新規サブコマンド `dogbass pull-all` を追加する。

## 動機

既存の `pull` は 1 記事ずつ、既知の `id` を指定して取得する用途に限定されている。自分 (または特定ユーザー) が書いた記事をまとめてローカルにエクスポートしたい、という需要には対応できない。DocBase API には「トークン所有者の記事を検索する」専用エンドポイントはないが、`GET /teams/:domain/profile` でトークン所有者の `id` を取得でき、`GET /teams/:domain/posts?q=author_id:<id>` で著者を指定した検索ができるため、これらを組み合わせて実現する。

## CLI インターフェース

```
dogbass pull-all <directory> [--user <user_id>]
```

- 必須引数: `directory` — 保存先ディレクトリ。存在しない場合は作成する (`mkdir(parents=True, exist_ok=True)`)。ファイルが指定された場合は Click 側で `UsageError` (`click.Path(file_okay=False)`)。
- オプション: `--user <user_id>` (int) — 記事を取得する対象ユーザーの DocBase user id。省略時は `GET /teams/:domain/profile` でトークン所有者自身の id を解決して使う。
- 出力: 取得した記事ごとに `Pulled DocBase post {id} into {path}` を標準出力に出し、最後に `Pulled {n} DocBase post(s) into {directory}` のサマリを出す (`push`/`pull` と同じトーン)。

## 動作仕様

1. `--user` が指定されていなければ `client.get_profile()` を呼び、レスポンスの `id` (int) をユーザー id として使う。`id` が int でなければ `DocBaseResponseError`。
2. `directory` を作成する (存在していれば何もしない)。
3. 対象ユーザーの記事を「公開・下書き問わず全件」取得する。DocBase の検索 API がデフォルトで下書きを含むかどうかドキュメント上明確でないため、安全側に倒して次の 2 クエリを両方発行し、`id` で重複排除して合成する:
   - `author_id:<user_id>`
   - `author_id:<user_id> is:draft`
4. 各クエリについて `per_page=100` でページング取得する。`page=1` から開始し、返ってきた `posts` 件数が `100` 未満になった時点でそのクエリの取得を打ち切る (次ページが空になるまで回すのではなく、最終ページのレスポンス件数で判定する)。
5. 集約した記事 (`id` をキーとする辞書) を `id` の昇順で処理する。各記事について:
   a. タイトルから `title_to_filename()` (既存の `cli.py` のスラグ化関数) でスラグを作る。スラグが空文字になる場合 (絵文字のみのタイトルなど) は `f"{id}.md"` を、それ以外は `f"{id}-{slug}"` (`title_to_filename` が返す `slug.md` の `slug` 部分を使う) をファイル名とする。
   b. `directory` 内の `*.md` を走査し、ファイル名の `stem` が `str(id)` と等しいか `f"{id}-"` から始まるものを「この記事の既存ファイル」とみなす (id の前方一致誤爆を避けるため、桁数を跨いだ部分一致にはならないことを確認する: 例えば `id=1` は `10-title.md` にはマッチしない)。
   c. 既存ファイルの中に今回の書き込み先パスと同じものがあれば、そのファイルの `notice` (front matter) を読み取って引き継ぎ、それ以外の同 id ファイルは削除する。書き込み先と同名の既存ファイルがない場合は、既存ファイルのうち先頭の 1 件から `notice` を引き継いだ上で、該当する既存ファイルをすべて削除する (タイトル変更によるリネームを表現する)。既存ファイルの読み込みに失敗した場合 (front matter が壊れている等) は `notice=None` として続行する。
   d. `markdown_document_from_docbase(target_path, post, id, notice=notice)` で `MarkdownDocument` を組み立て、`write_markdown_document(document)` で書き込む。書き込み先が既存パスと同じ場合は既存の YAML 構造を保った更新に、リネームの場合は新規ファイルとして (テンプレートコメント付きで) レンダリングされる、という既存のふるまいをそのまま利用する。
   e. `Pulled DocBase post {id} into {target_path}` を出力する。
6. 全件処理後に `Pulled {n} DocBase post(s) into {directory}` を出力する。

## アーキテクチャ

### `dogbass/docbase.py`

`DocBaseClient` にメソッドを追加する:

```python
def get_profile(self) -> dict[str, Any]:
    return self._request_object("GET", f"/teams/{self.domain}/profile")

def list_posts(
    self, query: str, page: int = 1, per_page: int = 20
) -> dict[str, Any]:
    params = {"q": query, "page": page, "per_page": per_page}
    return self._request_object(
        "GET", f"/teams/{self.domain}/posts", params=params
    )
```

`_request_object` / `_request_json` は現状 `json=payload` しか `httpx` に渡していないため、GET のクエリパラメータを渡せるよう `params: dict[str, Any] | None = None` を追加し、`client.request(method, path, headers=headers, json=payload, params=params)` に変更する。既存の呼び出し (`create_post` 等) は `params` を渡さないため影響はない。

`get_profile()` / `list_posts()` はどちらも `get_post()` と同様に生の `dict` を返すだけで、フィールドの妥当性検証は呼び出し側 (`cli.py`) で行う (`list_groups()` のように docbase.py 側で構造検証はしない、`get_post` 相当の薄いラッパーとする)。

### `dogbass/cli.py`

新しい内部関数を追加する:

```python
def resolve_user_id(client: DocBaseClient, user_id: int | None) -> int:
    """--user が None のとき profile API で自分の id を解決する"""

def pull_all_filename(post_id: int, title: str) -> str:
    """title_to_filename() を使い f"{post_id}-{slug}.md" 形式のファイル名を作る"""

def existing_paths_for_id(directory: Path, post_id: int) -> list[Path]:
    """directory 内で post_id に属する既存ファイルを stem 完全一致/前方一致で探す"""

def fetch_all_posts(client: DocBaseClient, user_id: int) -> dict[int, dict[str, Any]]:
    """author_id:<id> と author_id:<id> is:draft の2クエリをページングして id をキーに合成する"""

def pull_all_markdown_files(
    directory: Path, client: DocBaseClient, user_id: int | None = None
) -> int:
    """動作仕様 1〜6 を実行し、書き込んだ件数を返す"""
```

`pull_all_markdown_files` は `push_markdown_file` / `pull_markdown_file` と同じ形 (click.echo で進捗を出し、`AppError` はそのまま呼び出し元 (`app_error_handler`) に伝播させる) に揃える。

新サブコマンド:

```python
@main.command("pull-all")
@click.option(
    "--user",
    "user_id",
    type=int,
    default=None,
    help="DocBase user id to fetch posts for (defaults to the token owner).",
)
@click.argument(
    "directory", type=click.Path(file_okay=False, path_type=Path)
)
@app_error_handler
def pull_all_command(directory: Path, user_id: int | None) -> None:
    """Fetch all DocBase posts written by a user into a directory."""
    client = DocBaseClient.from_env()
    pull_all_markdown_files(directory, client, user_id=user_id)
```

`dogbass/markdown.py` の変更は不要。既存の `markdown_document_from_docbase` / `write_markdown_document` / `load_markdown_document` をそのまま再利用する。

## エラーハンドリング

- `DOCBASE_DOMAIN` / `DOCBASE_TOKEN` 未設定 → `ConfigurationError` (`DocBaseClient.from_env()` が送出、既存の挙動)
- profile API のレスポンスに `id` (int) がない → `DocBaseResponseError`
- 検索 API のレスポンスが `posts` (list) を含まない、または各要素が `dict` でない、`id` (int) を持たない → `DocBaseResponseError`
- 個々の記事を `MarkdownDocument` に変換する際のフィールド欠落は既存の `markdown_document_from_docbase` のバリデーションに従う (`DocBaseResponseError`)
- `directory` にファイル (ディレクトリでないパス) を渡した場合 → Click の `UsageError` (終了コード 2)
- 既存ファイルの読み込み失敗 (front matter 破損など) は `notice` の引き継ぎを諦めて `None` 扱いにし、処理は継続する (致命的エラーにしない)

## テスト

`tests/test_cli.py` の `FakeDocBaseClient` に以下を追加する:

- `get_profile(self) -> dict[str, object]` — 固定の `{"id": <int>}` を返す
- `list_posts(self, query: str, page: int, per_page: int) -> dict[str, object]` — テストケースごとに用意した記事一覧を `query`/`page` に応じて返せるよう、呼び出しを記録しつつ `{"posts": [...]}` を返す (下書きクエリと通常クエリを区別できるフェイクにする)

追加するテストケース (正常系):

- `--user` 省略時、`get_profile()` の `id` で著者を絞り込むこと (`list_posts` に渡った `query` を検証)
- `--user <id>` 指定時、`get_profile()` を呼ばずにその id で絞り込むこと
- 複数ページ (`per_page` 未満になるまで) を正しく走査すること
- 通常クエリと `is:draft` クエリの両方で返ってきた記事が `id` で重複排除されること
- 取得した記事が `{id}-{slug}.md` という名前で書き込まれ、front matter に `id` / `title` / `draft` / `tags` / `scope` が反映されること
- タイトルが空スラグになる記事 (絵文字のみ等) が `{id}.md` として書き込まれること
- 既存の `{id}-旧タイトル.md` がある状態で再実行すると、新タイトルの `{id}-新タイトル.md` にリネームされ、旧ファイルが削除されること
- 既存ファイルの `notice` 設定がリネーム後も引き継がれること
- 保存先ディレクトリが存在しない場合、自動的に作成されること

異常系:

- profile レスポンスに `id` がない → `DocBaseResponseError` で終了コード 1
- 検索レスポンスが不正な形式 → `DocBaseResponseError` で終了コード 1
- `directory` に既存ファイルのパスを渡す → Click の `UsageError` で終了コード 2

## 影響範囲

- 新規コマンドの追加のみ。既存の `new` / `push` / `pull` / `groups` / `install-hook` / `sync-commit` / `init` の挙動は変更しない。
- `dogbass/docbase.py` の `_request_object` / `_request_json` に `params` 引数が増えるが、デフォルト `None` のため既存呼び出しは無変更で動く。
- README / CLAUDE.md のコマンド一覧更新は本仕様の範囲外とする。

## 非ゴール

- アーカイブ済み記事 (`is:archived`) の取得は対象外とする (要望があれば後日追加)。
- `--include-drafts` / `--no-drafts` のような下書き除外オプションは追加しない (常に下書きを含める)。
- 差分のみを取得する増分同期は行わない。常に全件取得・全件書き込みとする。
- 既存ファイルの本文をローカルで編集していた場合の競合検出・警告は行わない (`pull` 単体コマンドと同じ「常に DocBase の内容で上書きする」方針)。
