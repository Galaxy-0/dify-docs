#!/usr/bin/env python3
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DOC_DIRS = [ROOT / "zh-hans", ROOT / "plugin-dev-zh"]

IMG_PLACEHOLDER_TEMPLATE = "**[图片缺失] {label} ({src})**"

COMPONENT_LABELS = {
    "Info": "信息提示",
    "Tip": "提示",
    "Warning": "警告",
    "Callout": "提示",
    "Alert": "提醒",
    "Steps": "步骤",
}

SELF_CLOSING_COMPONENTS = {"TableOfContents"}

IMG_ATTR_PATTERN = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
HTML_COMMENT_PATTERN = re.compile(r'<!--.*?-->', re.S)
MDX_COMMENT_PATTERN = re.compile(r'\{\s*/\*.*?\*/\s*\}', re.S)
IMPORT_PATTERN = re.compile(r'^\s*import\s+.*$', re.M)
EXPORT_PATTERN = re.compile(r'^\s*export\s+\w.*$', re.M)
BACKTICK_EXPORT_PATTERN = re.compile(r'export\s+const\s+\w+\s*=\s*`.*?`;?', re.S)
FRONTMATTER_PATTERN = re.compile(r'^---\n(.*?)\n---\n', re.S)
UPPER_TAG_PATTERN = re.compile(r'</?[A-Z][A-Za-z0-9]*(?:\s[^>]*)?>')
IMG_TAG_PATTERN = re.compile(r'<img\s+([^>]+?)\s*/?>', re.I)
FRAME_WITH_CAPTION_PATTERN = re.compile(r'<Frame\s+[^>]*caption="([^"]+)"[^>]*>', re.I)
FRAME_PATTERN = re.compile(r'<Frame[^>]*>', re.I)
ATTRIBUTE_TITLE_PATTERN = re.compile(r'title="([^"]+)"')
ATTRIBUTE_TYPE_PATTERN = re.compile(r'type="([^"]+)"')
INLINE_BR_PATTERN = re.compile(r'<br\s*/?>', re.I)
DOUBLE_SPACE_PATTERN = re.compile(r'^[\t ]+$', re.M)


def extract_frontmatter(text: str):
    metadata = {}
    match = FRONTMATTER_PATTERN.match(text)
    if match:
        block = match.group(1)
        for line in block.splitlines():
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                metadata[key] = value
        text = text[match.end():]
    return text, metadata


def convert_image(match: re.Match) -> str:
    attrs = match.group(1)
    attr_dict = {}
    for attr_match in IMG_ATTR_PATTERN.finditer(attrs):
        attr_dict[attr_match.group(1).lower()] = attr_match.group(2)
    src = attr_dict.get('src', '').strip()
    alt = attr_dict.get('alt', '').strip()
    if src.startswith('/'):
        normalized_src = src.lstrip('/')
    else:
        normalized_src = src
    local_path = (ROOT / normalized_src).resolve()
    if src.startswith('http://') or src.startswith('https://'):
        return f'![{alt}]({src})'
    if local_path.exists():
        rel_path = local_path.relative_to(ROOT)
        return f'![{alt}]({rel_path.as_posix()})'
    if normalized_src:
        return IMG_PLACEHOLDER_TEMPLATE.format(label=alt or '未命名插图', src=normalized_src)
    return IMG_PLACEHOLDER_TEMPLATE.format(label=alt or '未命名插图', src='未知路径')


def replace_components(text: str) -> str:
    def opener(match: re.Match) -> str:
        name = match.group(1)
        attrs = match.group(2) or ''
        if name in SELF_CLOSING_COMPONENTS:
            return ''
        if name in COMPONENT_LABELS:
            label = COMPONENT_LABELS[name]
            title_match = ATTRIBUTE_TITLE_PATTERN.search(attrs)
            title = title_match.group(1) if title_match else ''
            type_match = ATTRIBUTE_TYPE_PATTERN.search(attrs)
            type_label = type_match.group(1) if type_match else ''
            suffix_parts = [part for part in [title, type_label] if part]
            suffix = '：' + ' - '.join(suffix_parts) if suffix_parts else '：'
            return f"\n> **{label}{suffix}**\n"
        return ''

    def closer(match: re.Match) -> str:
        name = match.group(1)
        if name in COMPONENT_LABELS:
            return '\n'
        if name in SELF_CLOSING_COMPONENTS:
            return ''
        return ''

    # Opening tags with attributes
    text = re.sub(r'<([A-Z][A-Za-z0-9]*)([^/>]*?)>', opener, text)
    # Closing tags
    text = re.sub(r'</([A-Z][A-Za-z0-9]*)>', closer, text)
    return text


def clean_mdx(text: str):
    text = text.replace('\r\n', '\n')
    text = HTML_COMMENT_PATTERN.sub('', text)
    text = MDX_COMMENT_PATTERN.sub('', text)
    text = INLINE_BR_PATTERN.sub('  \n', text)
    text = IMPORT_PATTERN.sub('', text)
    text = BACKTICK_EXPORT_PATTERN.sub('', text)
    text = EXPORT_PATTERN.sub('', text)
    text, metadata = extract_frontmatter(text)
    text = replace_components(text)
    text = FRAME_WITH_CAPTION_PATTERN.sub(lambda m: f"\n*图：{m.group(1)}*\n", text)
    text = FRAME_PATTERN.sub('\n', text)
    text = IMG_TAG_PATTERN.sub(convert_image, text)
    text = text.replace('](/', '](./')
    text = re.sub(r'\{`([^`]*)`\}', r'`\1`', text)
    text = re.sub(r'\{([^}]+)\}', lambda m: m.group(1) if not any(ch in m.group(1) for ch in '{}$') else m.group(0), text)
    text = UPPER_TAG_PATTERN.sub('', text)
    text = DOUBLE_SPACE_PATTERN.sub('', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip(), metadata


def gather_docs():
    files = []
    for doc_dir in DOC_DIRS:
        if doc_dir.exists():
            files.extend(sorted(doc_dir.rglob('*.mdx')))
            files.extend(sorted(doc_dir.rglob('*.md')))
    # remove duplicates while preserving order
    seen = set()
    ordered = []
    for path in sorted(files):
        if path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    return ordered


def main():
    markdown_path = ROOT / 'dify-docs-zh.md'
    doc_paths = gather_docs()
    lines = ['# Dify 中文文档合集', '', '该文档由仓库中的中文文档自动汇总生成。', '']
    for path in doc_paths:
        raw_text = path.read_text(encoding='utf-8')
        cleaned, metadata = clean_mdx(raw_text)
        title = metadata.get('title') or path.stem.replace('-', ' ')
        rel_path = path.relative_to(ROOT).as_posix()
        lines.append(f'\n## {title}')
        lines.append(f'> 来源：`{rel_path}`')
        if metadata.get('description'):
            lines.append(f'> 摘要：{metadata["description"]}')
        lines.append('')
        if cleaned:
            lines.append(cleaned)
        else:
            lines.append('_（该章节暂无正文内容）_')
        lines.append('')
    markdown_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f'已生成 {markdown_path.name}，共收录 {len(doc_paths)} 篇文档。')


if __name__ == '__main__':
    main()
