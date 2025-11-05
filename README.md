# Site Crawler

複数のウェブサイトを効率的にクロールし、HTMLファイルをダウンロードして保存するPythonスクリプトです。

## 特徴

- **一括処理**: JSONまたはCSVファイルから複数のURLを読み込み、順次クロール
- **robots.txt準拠**: 各サイトのrobots.txtを確認し、クロール可否を判断
- **進捗管理**: 途中で中断しても、次回は未完了のサイトから再開可能
- **ドメイン単位管理**: サイトごとにフォルダを作成して整理
- **安全設計**: リクエスト間に待機時間を設け、サーバーへの負荷を軽減

## 必要な環境

- Python 3.6以上
- 必要なライブラリ:
  - requests
  - beautifulsoup4
  - lxml

## インストール

1. リポジトリをクローン:
```bash
git clone <repository-url>
cd <repository-name>
```

2. 必要なパッケージをインストール:
```bash
pip install requests beautifulsoup4 lxml
```

または、requirements.txtがある場合:
```bash
pip install -r requirements.txt
```

## 使い方

### 基本的な使用方法

1. **入力ファイルを準備**

スクリプトと同じディレクトリに `input_urls.json` を配置します。

2. **スクリプトを実行**

```bash
python site_crawler.py
```

### コマンドライン引数

カスタムの入力ファイルや出力先を指定できます:

```bash
python site_crawler.py --input my_urls.json --output ./downloaded_sites
```

#### オプション

- `--input`: 入力ファイルのパス（デフォルト: `input_urls.json`）
- `--output`: 出力ディレクトリのパス（デフォルト: `crawled_sites`）

## 入力ファイルの形式

### JSON形式の例

**方式1: オブジェクトの配列**
```json
[
  {"url": "https://example.com"},
  {"url": "https://another-site.com"},
  {"website": "https://third-site.com"}
]
```

**方式2: URLの配列**
```json
{
  "urls": [
    "https://example.com",
    "https://another-site.com"
  ]
}
```

### CSV形式の例

```csv
url
https://example.com
https://another-site.com
```

## 設定項目

スクリプト内の以下の設定を編集できます:

| 設定項目 | デフォルト値 | 説明 |
|---------|------------|------|
| `INPUT_FILE_PATH` | `input_urls.json` | 入力ファイルのパス |
| `OUTPUT_BASE_DIR` | `crawled_sites` | 出力ディレクトリ |
| `USER_AGENT` | `MySiteCrawler/1.0` | クローラーのユーザーエージェント |
| `REQUEST_DELAY` | 2秒 | リクエスト間の待機時間 |
| `MAX_PAGES_PER_SITE` | 10ページ | 1サイトあたりの最大ページ数 |

## 出力

ダウンロードしたHTMLファイルは以下の構造で保存されます:

```
crawled_sites/
├── example.com/
│   ├── index.html
│   ├── about.html
│   └── contact.html
├── another-site.com/
│   ├── index.html
│   └── ...
└── crawl_progress.json  # 進捗管理ファイル
```

## 実行例

```bash
# デフォルト設定で実行
$ python site_crawler.py

# カスタム入力ファイルを指定
$ python site_crawler.py --input hospitals_list.json

# 入力と出力を両方指定
$ python site_crawler.py --input sites.csv --output ./my_output
```

## 途中再開機能

- クロールが中断された場合、次回実行時に自動的に続きから再開されます
- `crawl_progress.json` ファイルが進捗を記録しています
- 既にダウンロード済みのサイトは自動的にスキップされます

## 注意事項

1. **利用規約の確認**: クロール対象のウェブサイトの利用規約を必ず確認してください
2. **サーバー負荷**: `REQUEST_DELAY` を適切に設定し、対象サーバーに負荷をかけないようにしてください
3. **robots.txt**: このスクリプトはrobots.txtを尊重しますが、クロール前に手動で確認することを推奨します
4. **法的責任**: このスクリプトの使用による責任は利用者が負うものとします

## ライセンス

MIT License

## 貢献

バグ報告や機能提案は、Issuesからお願いします。プルリクエストも歓迎します。
