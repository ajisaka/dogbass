# dogbass

![](./dogbass.png)

[DocBase](https://docbase.io/) のドキュメントを作成・更新するコマンドを提供する。

# 仕様

- YAML Front Matter で、タイトルや、ドキュメントの ID を指定する
- ID が無い場合、新規で作成し、ドキュメントに ID 情報を追記する
- ID がある場合、`pull` で DocBase 上の内容をローカル Markdown に取り込める

# YAML Front Matter

```
---
title: ${タイトル}
tags: [${タグ1}, ${タグ2}, ...]
draft: false
id: ${ドキュメントID} # 省略可。新規作成する場合は指定しない
---
```

# コマンド

- `dogbass push ${*.md}`
- `dogbass pull ${*.md}`
- `dogbass update ${*.md}` (`push` の互換エイリアス)

# 環境変数

- `DOCBASE_DOMAIN`: DocBase の team domain
- `DOCBASE_TOKEN`: DocBase API トークン

# 実行例

```sh
uv run dogbass push path/to/document.md
uv run dogbass pull path/to/document.md
```

# refs

- [DocBase API](https://help.docbase.io/posts/45703)
