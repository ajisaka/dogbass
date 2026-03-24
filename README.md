# dogbass

![](./dogbass.png)

`dogbass` は、Markdown ファイルと [DocBase](https://docbase.io/) のドキュメントを同期するための CLI です。

ローカルで書いた Markdown を DocBase に反映したり、DocBase 上の内容をローカルに取り込んだりできます。

## できること

- `push`: ローカルの Markdown を DocBase に反映する
- `pull`: DocBase の内容をローカルの Markdown に取り込む

## 前提

- Python 3.11 以上
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

## Markdown ファイル形式

DocBase と同期する Markdown ファイルは、先頭に YAML Front Matter を持ちます。

```md
---
title: ドキュメントタイトル
tags: [tag1, tag2]
draft: false
id: 123 # 新規作成時は省略可
---

# 本文

ここに DocBase と同期したい Markdown を書きます。
```

### Front Matter の意味

- `title`: DocBase のタイトル。必須
- `tags`: DocBase のタグ一覧。省略可
- `draft`: 下書き保存するかどうか。省略時は `false`
- `id`: DocBase のドキュメント ID。新規作成時は不要

## 使い方

### 1. 新規作成または更新する

```sh
uv run dogbass push path/to/document.md
```

- Front Matter に `id` が無い場合は、DocBase に新規作成します
- 作成に成功すると、返ってきた `id` を Markdown ファイルへ書き戻します
- Front Matter に `id` がある場合は、その DocBase ドキュメントを更新します

### 2. DocBase の内容を取り込む

```sh
uv run dogbass pull path/to/document.md
```

- Front Matter に `id` が必要です
- 指定した `id` の DocBase ドキュメントを取得し、ローカル Markdown のタイトル・タグ・`draft`・本文を更新します
- 既存ファイルの改行コードは維持します

## よくある運用

### ローカルから初回投稿する

1. `id` なしで Markdown を作る
2. `uv run dogbass push path/to/document.md` を実行する
3. 書き戻された `id` を含む Markdown を継続して編集する

### DocBase の内容をローカルに反映する

1. `id` を持つ Markdown を用意する
2. `uv run dogbass pull path/to/document.md` を実行する
3. 必要なら編集後に `push` で再反映する

## 参照

- [DocBase API](https://help.docbase.io/posts/45703)
