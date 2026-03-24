# dogbass

![](./dogbass.png)

`dogbass` は、Markdown ファイルと [DocBase](https://docbase.io/) のドキュメントを同期するための CLI です。

ローカルで書いた Markdown を DocBase に反映したり、DocBase 上の内容をローカルに取り込んだりできます。

## できること

- `new`: DocBase 用の Markdown ファイルを新規作成する
- `push`: ローカルの Markdown を DocBase に反映する
- `pull`: DocBase の内容をローカルの Markdown に取り込む
- `groups`: 利用できる DocBase グループ一覧を表示する

## 前提

- Python 3.12 以上
- `uv`
- DocBase の team domain
- DocBase API トークン

## 環境変数

- `DOCBASE_DOMAIN`: DocBase の team domain
- `DOCBASE_TOKEN`: DocBase API トークン

```sh
export DOCBASE_DOMAIN=your-team
export DOCBASE_TOKEN=your-token
```

## インストール

初回導入と更新は、同じコマンドで行えます。

```sh
uv tool install --python 3.12 --force git+https://github.com/ajisaka/dogbass.git
```

## Markdown ファイル形式

DocBase と同期する Markdown ファイルは、先頭に YAML Front Matter を持ちます。

```md
---
title: ドキュメントタイトル
tags: [tag1, tag2]
draft: false
notice: true
# notice: false
scope: private
# scope: everyone
# scope: group
# groups: [123] # scope が group のときに指定
id: 123 # 新規作成時は省略可
---

# 本文

ここに DocBase と同期したい Markdown を書きます。
```

### Front Matter の意味

- `title`: DocBase のタイトル。必須
- `tags`: DocBase のタグ一覧。省略可
- `draft`: 下書き保存するかどうか。省略時は `false`
- `notice`: push 時に通知するかどうか。省略時は DocBase のデフォルトに従う
- `scope`: 公開範囲。`private` / `everyone` / `group`
- `groups`: 公開範囲が `group` のときのグループ ID 一覧
- `id`: DocBase のドキュメント ID。新規作成時は不要

## 使い方

### 1. 新しい Markdown を作る

```sh
dogbass new path/to/document.md
```

- 対話プロンプトでタイトルを聞きます
- 生成される Markdown は `draft: true` / `notice: true` / `scope: private` で始まります
- `scope` の候補は、コメントを外すだけで切り替えられる形で一緒に出力されます
- `notice` もコメントを外すだけで `false` に切り替えられます
- `id` はまだ入らないので、最初の `push` で DocBase 側に作成されます

### 2. 新規作成または更新する

```sh
dogbass push path/to/document.md
```

```sh
dogbass push --notify path/to/document.md
dogbass push --no-notify path/to/document.md
```

- Front Matter に `id` が無い場合は、DocBase に新規作成します
- 作成に成功すると、返ってきた `id` を Markdown ファイルへ書き戻します
- Front Matter に `id` がある場合は、その DocBase ドキュメントを更新します
- `--notify` / `--no-notify` を指定した場合は、Front Matter の `notice` より CLI オプションを優先します

### 3. DocBase の内容を取り込む

```sh
dogbass pull path/to/document.md
```

- Front Matter に `id` が必要です
- 指定した `id` の DocBase ドキュメントを取得し、ローカル Markdown のタイトル・タグ・`draft`・本文を更新します
- `scope` / `groups` も取得できる場合は一緒に更新します
- 既存ファイルの改行コードは維持します

既存ファイルがまだ無い場合は、`--id` を指定して新規に取り込めます。

```sh
dogbass pull --id 123 path/to/document.md
```

- DocBase のドキュメント ID を指定して、新しい Markdown ファイルを作成します
- 生成されるファイルには `title` / `tags` / `draft` / `scope` / `groups` / `id` / 本文が入ります
- 既に同名ファイルがある場合は、誤上書きを防ぐため失敗します

### 4. グループ ID を調べる

`scope: group` を使う前に、利用できるグループ ID を確認できます。

```sh
dogbass groups
```

- `グループID<TAB>グループ名` の形式で出力します
- `scope: group` と `groups: [...]` を設定するときに使えます

## よくある運用

### ローカルから初回投稿する

1. `dogbass new path/to/document.md` を実行する
2. プロンプトにタイトルを入力する
3. 必要なら本文やタグを編集する
4. `dogbass push path/to/document.md` を実行する
5. 書き戻された `id` を含む Markdown を継続して編集する

### DocBase の内容をローカルに反映する

1. `id` を持つ Markdown を用意する
2. `dogbass pull path/to/document.md` を実行する
3. 必要なら編集後に `push` で再反映する

### 既存の DocBase ドキュメントをローカルに取り込んで始める

1. `dogbass pull --id 123 path/to/document.md` を実行する
2. 作成された Markdown を編集する
3. 必要なら `dogbass push path/to/document.md` で再反映する

## 参照

- [DocBase API](https://help.docbase.io/posts/45703)
