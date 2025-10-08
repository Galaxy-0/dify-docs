#!/usr/bin/env python3
import hashlib
import sys
import urllib.request
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
MARKDOWN = ROOT / 'dify-docs-zh.md'
TARGET_DIR = ROOT / 'images' / 'remote'
TARGET_DIR.mkdir(parents=True, exist_ok=True)
PLACEHOLDER = TARGET_DIR / 'download-failed.png'

# minimal 1x1 PNG
PLACEHOLDER_DATA = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0bIDAT\x08\x99c``\x00\x00\x00\x05\x00\x01\x0d\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
if not PLACEHOLDER.exists():
    PLACEHOLDER.write_bytes(PLACEHOLDER_DATA)

if not MARKDOWN.exists():
    print(f'未找到 {MARKDOWN}', file=sys.stderr)
    sys.exit(1)

pattern = re.compile(r'!\[[^\]]*\]\((https?://[^)]+)\)')
text = MARKDOWN.read_text(encoding='utf-8')
urls = list(dict.fromkeys(pattern.findall(text)))  # preserve order, dedupe
print(f'检测到 {len(urls)} 个远程图片链接。')

url_to_local = {}
failures = []

for idx, url in enumerate(urls, 1):
    clean_url = url.strip()
    name_part = clean_url.split('?')[0].rstrip('/')
    suffix = Path(name_part).suffix.lower()
    if suffix not in {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp'}:
        suffix = '.png'
    filename = hashlib.sha1(clean_url.encode('utf-8')).hexdigest() + suffix
    local_path = TARGET_DIR / filename
    if not local_path.exists():
        try:
            print(f'[{idx}/{len(urls)}] 下载 {clean_url} ...')
            with urllib.request.urlopen(clean_url, timeout=60) as resp:
                data = resp.read()
            local_path.write_bytes(data)
        except Exception as exc:
            print(f'[{idx}/{len(urls)}] 下载失败: {clean_url} -> {exc}')
            failures.append((clean_url, str(exc)))
            url_to_local[clean_url] = PLACEHOLDER.relative_to(ROOT).as_posix()
            continue
    url_to_local[clean_url] = local_path.relative_to(ROOT).as_posix()

print(f'下载完成：成功 {len(url_to_local) - len(failures)}，失败 {len(failures)}。')
if failures:
    print('失败列表:')
    for url, reason in failures:
        print(f'  {url} -> {reason}')

# 更新 markdown 引用

def replace_url(match: re.Match) -> str:
    url = match.group(1).strip()
    local = url_to_local.get(url)
    if not local:
        return match.group(0)
    return match.group(0).replace(url, './' + local)

updated_text = pattern.sub(replace_url, text)
MARKDOWN.write_text(updated_text, encoding='utf-8')
print('已更新 dify-docs-zh.md 中的图片路径。')
