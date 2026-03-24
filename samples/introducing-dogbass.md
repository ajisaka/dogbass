---
draft: false
id: 4080654
scope: everyone
tags:
- docbase
- markdown
- cli
- Python
- productivity
title: dogbassでMarkdownとDocBaseを気持ちよく同期する
notice: false
---

# dogbassでMarkdownとDocBaseを気持ちよく同期する

著者: GitHub Copilot

DocBase は便利です。
でも、長めの文章や技術メモを編集するときに、「普段使っているエディタで Markdown のまま書きたい」と思うことがあります。

`dogbass` は、そんな気持ちから作った CLI ツールです。
ローカルの Markdown ファイルと DocBase のドキュメントを同期できます。

リポジトリ:
https://github.com/ajisaka/dogbass

## 使い始める前に必要なもの

使い始める前に、次の 2 つを用意します。

- DocBase の team domain
- DocBase API トークン

API トークンは、DocBase の設定画面にあるアクセストークン作成画面から発行できます。

`dogbass` は次の環境変数を参照します。

```sh
export DOCBASE_DOMAIN=your-team
export DOCBASE_TOKEN=your-token
```

インストールは次のコマンドです。

```sh
uv tool install --python 3.12 --force git+https://github.com/ajisaka/dogbass.git
```

## できること

`dogbass` でできることはシンプルです。

- `new`: DocBase 用の Markdown ファイルを作る
- `push`: ローカルの Markdown を DocBase に反映する
- `pull`: DocBase の内容をローカルに取り込む

つまり、**ふだんはローカルで書き、必要なときに DocBase と同期する**、という流れを扱いやすくします。

## うれしいポイント

### 1. Markdown をローカルで育てられる

エディタの補完、検索、置換、Git 管理など、普段の開発体験をそのまま使えます。

DocBase のエディタで直接書くよりも、慣れた環境で落ち着いて文章を編集できます。

### 2. Front Matter で状態を持てる

`dogbass` は Markdown の先頭に YAML Front Matter を持たせます。

```md
---
title: ドキュメントタイトル
tags: [tag1, tag2]
draft: false
---
```

ここにタイトルやタグ、下書き状態をまとめて書けるので、DocBase に送る情報がファイル側に自然にまとまります。

初回 `push` のあとには DocBase の `id` も書き戻されるため、次回以降の更新もスムーズです。

### 3. pull もできる

ローカルから送るだけではなく、DocBase 側の内容をローカルへ取り込めます。

すでに同期済みのファイルなら `pull` で更新できますし、DocBase 上の既存記事を `pull --id` で新しく取り込むこともできます。

## 使い方はシンプル

環境変数を設定したら、まず新しい原稿ファイルを作ります。

```sh
dogbass new path/to/document.md
```

そのあと、ローカルの Markdown を DocBase に反映します。

```sh
dogbass push path/to/document.md
```

DocBase 側の内容をローカルに取り込みたいときはこうです。

```sh
dogbass pull path/to/document.md
```

既存の DocBase 記事を新しいローカルファイルとして持ってきたいときは、次のように使えます。

```sh
dogbass pull --id 1234567 path/to/imported.md
```

## こんな人に向いています

- DocBase を使っている
- 記事やメモはローカルのエディタで書きたい
- Markdown を Git で管理したい
- CLI ベースの小さい道具が好き

こういう人にはかなり相性がいいと思います。

## おわりに

`dogbass` は、「DocBase を使いたい」と「ローカルで Markdown を書きたい」を両立するための道具です。

派手なことはしませんが、日々の文書作業を少し素直にしてくれます。
DocBase をもっと自分の書き方に寄せたい人は、ぜひ試してみてください。
