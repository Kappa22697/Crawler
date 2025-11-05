import csv
import requests
import re
import time
import json
import os
import argparse
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from collections import deque
from bs4 import BeautifulSoup

# --- 設定項目 ---
# 1. 読み込むファイルのパス (スクリプトと同じディレクトリにあると仮定)
INPUT_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'input_urls.json')

# 2. ダウンロードしたHTMLを保存するベースディレクトリ (スクリプトからの相対パス)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_BASE_DIR = os.path.join(SCRIPT_DIR, 'crawled_sites')

# 3. クローラーのユーザーエージェント名 (誰がアクセスしたかを示す識別子)
USER_AGENT = 'MySiteCrawler/1.0 (+http://example.com/bot-info)'

# 4. 各リクエスト間の待機時間（秒）。サーバーへの負荷を軽減します。
REQUEST_DELAY = 2

# 5. 1サイトあたりにダウンロードする最大ページ数 (無限クロールを防ぐため)
MAX_PAGES_PER_SITE = 10

# 6. 進捗状況を保存するファイル名
PROGRESS_FILE = 'crawl_progress.json'
# --- 設定はここまで ---


def normalize_url(url):
    """URLを正規化して、表記揺れを統一します。"""
    if not url or not isinstance(url, str):
        return None

    # "http://" や "https://" で始まらない場合は、"http://" を補完
    if not re.match(r'^https?://', url):
        url = 'http://' + url.replace('//', '/').lstrip('/')

    # "www." プレフィックスを削除
    url = re.sub(r'^https?://www\.', 'https://', url)
    # 末尾のスラッシュを削除
    return url.rstrip('/')


def read_urls_from_file(filepath):
    """JSONまたはCSVファイルからURLのリストを読み込みます。"""
    urls = []
    try:
        # ファイル拡張子で判定
        if filepath.endswith('.json'):
            with open(filepath, mode='r', encoding='utf-8') as jsonfile:
                data = json.load(jsonfile)
                # JSONの構造に応じて調整が必要
                # 例1: [{"url": "..."}, {"url": "..."}, ...]
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            url = item.get('url') or item.get('website')
                            if url:
                                urls.append(url)
                        elif isinstance(item, str):
                            urls.append(item)
                # 例2: {"urls": ["...", "...", ...]}
                elif isinstance(data, dict) and 'urls' in data:
                    urls.extend(data.get('urls', []))
        else:
            # CSVファイルとして読み込み
            with open(filepath, mode='r', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    url = row.get('url')
                    if url and url.startswith('http'):
                        urls.append(url)
    except FileNotFoundError:
        print(f"エラー: ファイルが見つかりません: {filepath}")
        return None
    except json.JSONDecodeError as e:
        print(f"エラー: JSONファイルの解析に失敗しました: {e}")
        return None

    # URLを正規化し、Noneや空文字列を除外してから重複を削除
    normalized_urls = {normalize_url(u) for u in urls}
    valid_urls = {u for u in normalized_urls if u}
    return sorted(list(valid_urls))


def scan_completed_sites(output_dir):
    """出力ディレクトリをスキャンして、既にクロール済みのサイト（ドメイン）を検出します。"""
    completed_domains = set()

    if not os.path.exists(output_dir):
        return completed_domains

    try:
        # output_dir内のサブディレクトリ（ドメイン名）をスキャン
        for item in os.listdir(output_dir):
            item_path = os.path.join(output_dir, item)
            # ディレクトリかつ、中にHTMLファイルが存在するか確認
            if os.path.isdir(item_path):
                html_files = [f for f in os.listdir(item_path) if f.endswith('.html')]
                if html_files:
                    completed_domains.add(item)
                    print(f"  検出: '{item}' には {len(html_files)} 個のHTMLファイルがあります")
    except Exception as e:
        print(f"警告: 出力ディレクトリのスキャンに失敗しました: {e}")

    return completed_domains


def load_progress(output_dir):
    """進捗状況ファイルを読み込みます。"""
    progress_path = os.path.join(output_dir, PROGRESS_FILE)
    if os.path.exists(progress_path):
        try:
            with open(progress_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"警告: 進捗ファイルの読み込みに失敗しました: {e}")
            return {'completed_urls': [], 'failed_urls': []}
    return {'completed_urls': [], 'failed_urls': []}


def save_progress(output_dir, progress_data):
    """進捗状況をファイルに保存します。"""
    progress_path = os.path.join(output_dir, PROGRESS_FILE)
    try:
        with open(progress_path, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"警告: 進捗ファイルの保存に失敗しました: {e}")


def sanitize_filename(url):
    """URLから安全なファイル名を生成します。"""
    parsed_url = urlparse(url)
    path = parsed_url.path
    
    # ルートパスの場合は index.html とする
    if not path or path.endswith('/'):
        path += 'index.html'
        
    # スラッシュや不要な文字をアンダースコアに置換
    filename = path.strip('/').replace('/', '_')
    
    # クエリパラメータもファイル名に含める（例: page_id=3 -> page_id_3）
    if parsed_url.query:
        query_part = parsed_url.query.replace('=', '_').replace('&', '_')
        filename += f"_{query_part}"

    # 拡張子がない場合は .html を追加
    if not re.search(r'\.[a-zA-Z0-9]{2,5}$', filename):
        filename += '.html'
        
    return filename

def crawl_site(start_url):
    """
    単一のウェブサイトをクロールし、HTMLを保存します。

    Args:
        start_url: クロール開始URL

    Returns:
        bool: 成功した場合True、スキップまたは失敗した場合False
    """
    parsed_start_url = urlparse(start_url)
    domain = parsed_start_url.netloc
    base_scheme = parsed_start_url.scheme

    # ドメイン名が正しく取得できない場合は処理を中断
    if not domain:
        print(f"エラー: URL '{start_url}' からドメイン名を取得できませんでした。スキップします。")
        return False

    # サイトごとの保存ディレクトリを作成
    site_dir = os.path.join(OUTPUT_BASE_DIR, domain)

    os.makedirs(site_dir, exist_ok=True)
    
    # 探索用のキューと訪問済みセット
    queue = deque([start_url])
    visited = {start_url}
    
    # robots.txtの準備
    robots_url = f"{base_scheme}://{domain}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        print(f"robots.txtを確認中: '{robots_url}' ...")
        headers = {'User-Agent': USER_AGENT}
        # タイムアウトを5秒に設定
        robots_response = requests.get(robots_url, headers=headers, timeout=5)
        if robots_response.status_code == 200:
            # 取得した内容をパーサーに渡す
            rp.parse(robots_response.text.splitlines())
            print(f"情報: '{robots_url}' を解析しました。")
        else:
            print(f"情報: '{robots_url}' はステータス {robots_response.status_code} を返しました。クロールを許可されていると見なします。")
            rp.allow_all = True # 404などの場合はクロールを許可
    except Exception as e:
        print(f"情報: '{robots_url}' を取得できませんでした（タイムアウト等）。クロールを許可されていると見なします。詳細: {e}")
        rp.allow_all = True # タイムアウトやその他の例外が発生した場合もクロールを許可

    page_count = 0
    while queue and page_count < MAX_PAGES_PER_SITE:
        current_url = queue.popleft()
        
        # robots.txtで許可されているか確認
        if not rp.can_fetch(USER_AGENT, current_url):
            print(f"アクセス拒否 (robots.txt): {current_url}")
            continue

        print(f"ダウンロード中 ({page_count + 1}/{MAX_PAGES_PER_SITE}): {current_url}")
        try:
            headers = {'User-Agent': USER_AGENT}
            response = requests.get(current_url, headers=headers, timeout=15)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            html_content = response.text
            
            # HTMLをファイルに保存
            filename = sanitize_filename(current_url)
            filepath = os.path.join(site_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            page_count += 1

            # ページ内のリンクを探索
            soup = BeautifulSoup(html_content, 'lxml')
            for link in soup.find_all('a', href=True):
                href = link['href']
                # 相対URLを絶対URLに変換
                next_url = urljoin(current_url, href)
                
                # URLのフラグメント（#...）を削除
                next_url = urljoin(next_url, urlparse(next_url).path)
                
                # 同じドメイン内かつ未訪問のURLをキューに追加
                if urlparse(next_url).netloc == domain and next_url not in visited:
                    visited.add(next_url)
                    queue.append(next_url)

        except requests.RequestException as e:
            print(f"ページの取得に失敗しました ({current_url}): {e}")
        except Exception as e:
            print(f"予期せぬエラーが発生しました ({current_url}): {e}")

        # サーバーへの負荷を考慮して待機
        time.sleep(REQUEST_DELAY)

    print(f"サイト '{domain}' のクロール完了。{page_count} ページをダウンロードしました。")
    return page_count > 0


def main():
    """メインの処理を実行します。"""
    # OUTPUT_BASE_DIRをグローバルに更新（crawl_site関数で使用されるため）
    global OUTPUT_BASE_DIR

    parser = argparse.ArgumentParser(description='ウェブサイトクローラー - JSONまたはCSVから複数サイトをクロールします')
    parser.add_argument(
        '--input',
        default=INPUT_FILE_PATH,
        help=f'入力ファイルのパス (JSON/CSV) (デフォルト: {INPUT_FILE_PATH})'
    )
    parser.add_argument(
        '--output',
        default=OUTPUT_BASE_DIR,
        help=f'出力ディレクトリのパス (デフォルト: {OUTPUT_BASE_DIR})'
    )
    args = parser.parse_args()

    # コマンドライン引数から取得したパスを使用
    input_path = args.input
    output_dir = args.output

    start_urls = read_urls_from_file(input_path)
    if not start_urls:
        print("処理対象のURLがありません。")
        return

    os.makedirs(output_dir, exist_ok=True)
    print(f"HTMLは '{output_dir}' ディレクトリに保存されます。")

    OUTPUT_BASE_DIR = output_dir

    # 既存のHTMLファイルをスキャンして完了済みサイトを検出
    print("\n既存のクロール済みサイトを確認中...")
    completed_domains = scan_completed_sites(output_dir)

    # 進捗状況を読み込む
    progress = load_progress(output_dir)
    completed_urls = set(progress.get('completed_urls', []))
    failed_urls = set(progress.get('failed_urls', []))

    # 進捗ファイルからもドメイン情報を読み込む
    progress_domains = set(progress.get('completed_domains', []))
    completed_domains.update(progress_domains)

    if completed_domains or completed_urls:
        print(f"\n途中再開モード: {len(completed_domains)} ドメイン、{len(completed_urls)} URLが既に完了しています。")
    else:
        print("\n新規クロールを開始します。")

    total_sites = len(start_urls)
    processed = 0
    skipped = 0
    failed = 0

    for i, url in enumerate(start_urls):
        print(f"\n{'='*20} サイト {i + 1}/{total_sites} の処理を開始 {'='*20}")
        print(f"URL: {url}")

        # URLからドメインを取得
        parsed_url = urlparse(url)
        domain = parsed_url.netloc

        if not domain:
            print(f"エラー: URL '{url}' からドメイン名を取得できませんでした。スキップします。")
            failed += 1
            continue

        # ドメインまたはURLが既に完了している場合はスキップ
        if domain in completed_domains or url in completed_urls:
            print(f"スキップ: '{domain}' (URL: {url}) は既に完了しています。")
            skipped += 1
            # completed_urlsに追加（まだない場合）
            completed_urls.add(url)
            continue

        try:
            success = crawl_site(url)
            if success:
                completed_urls.add(url)
                completed_domains.add(domain)  # ドメインも追加
                if url in failed_urls:
                    failed_urls.remove(url)
                processed += 1
                print(f"✓ 成功: '{domain}' のクロールが完了しました。")
            else:
                failed_urls.add(url)
                failed += 1
                print(f"✗ 失敗: '{domain}' のクロールに失敗しました。")
        except Exception as e:
            print(f"✗ エラー: '{url}' の処理中に予期せぬエラーが発生しました: {e}")
            failed_urls.add(url)
            failed += 1

        # 進捗を保存（URLとドメインのマッピングも保存）
        progress['completed_urls'] = sorted(list(completed_urls))
        progress['failed_urls'] = sorted(list(failed_urls))
        progress['completed_domains'] = sorted(list(completed_domains))
        save_progress(output_dir, progress)
        print(f"進捗を保存しました: 完了 {len(completed_urls)} / 失敗 {len(failed_urls)}")

    print(f"\n{'='*60}")
    print(f"すべての処理が完了しました。")
    print(f"  処理済み: {processed + skipped} サイト")
    print(f"  新規処理: {processed} サイト")
    print(f"  スキップ: {skipped} サイト")
    print(f"  失敗: {failed} サイト")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()