#!/usr/bin/env python3
import hashlib
import re
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent

IMG_PLACEHOLDER_TEMPLATE = "**[图片缺失] {label} ({src})**"
COMPONENT_LABELS = {
    "Info": "信息提示",
    "Tip": "提示",
    "Warning": "警告",
    "Callout": "提示",
    "Alert": "提醒",
    "Steps": "步骤",
    "Note": "说明",
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
MARKDOWN_IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\((https?://[^)]+)\)')
FRAME_WITH_CAPTION_PATTERN = re.compile(r'<Frame\s+[^>]*caption="([^"]+)"[^>]*>', re.I)
FRAME_PATTERN = re.compile(r'<Frame[^>]*>', re.I)
ATTRIBUTE_TITLE_PATTERN = re.compile(r'title="([^"]+)"')
ATTRIBUTE_TYPE_PATTERN = re.compile(r'type="([^"]+)"')
ATTRIBUTE_HREF_PATTERN = re.compile(r'href="([^"]+)"')
INLINE_BR_PATTERN = re.compile(r'<br\s*/?>', re.I)
DOUBLE_SPACE_PATTERN = re.compile(r'^[\t ]+$', re.M)
IFRAME_PATTERN = re.compile(r'<iframe.*?</iframe>', re.S | re.I)

REMOTE_SUFFIX_WHITELIST = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp'}


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


def hash_remote_url(url: str) -> Path:
    clean_url = url.strip()
    name_part = clean_url.split('?')[0].rstrip('/')
    suffix = Path(name_part).suffix.lower()
    if suffix not in REMOTE_SUFFIX_WHITELIST:
        suffix = '.png'
    filename = hashlib.sha1(clean_url.encode('utf-8')).hexdigest() + suffix
    return ROOT / 'images' / 'remote' / filename


def convert_image(match: re.Match) -> str:
    attrs = match.group(1)
    attr_dict = {}
    for attr_match in IMG_ATTR_PATTERN.finditer(attrs):
        attr_dict[attr_match.group(1).lower()] = attr_match.group(2)
    src = attr_dict.get('src', '').strip()
    alt = attr_dict.get('alt', '').strip()
    if src.startswith('http://') or src.startswith('https://'):
        local_path = hash_remote_url(src)
        if local_path.exists():
            rel_path = local_path.relative_to(ROOT).as_posix()
            return f'![{alt}]({rel_path})'
        placeholder = ROOT / 'images' / 'remote' / 'download-failed.png'
        if placeholder.exists():
            return f'![{alt}]({placeholder.relative_to(ROOT).as_posix()})'
        return f'![{alt}]({src})'
    normalized_src = src.lstrip('/')
    local_path = (ROOT / normalized_src).resolve()
    try:
        rel_path = local_path.relative_to(ROOT)
    except ValueError:
        rel_path = Path(normalized_src)
    if local_path.exists():
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
        if name == 'Card':
            title_match = ATTRIBUTE_TITLE_PATTERN.search(attrs)
            title = title_match.group(1) if title_match else ''
            href_match = ATTRIBUTE_HREF_PATTERN.search(attrs)
            href = href_match.group(1) if href_match else ''
            title_part = f'**{title}**' if title else '卡片'
            link_part = f'（链接：{href}）' if href else ''
            return f"\n- {title_part}{link_part}\n"
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
        if name in COMPONENT_LABELS or name == 'Card':
            return '\n'
        if name in SELF_CLOSING_COMPONENTS:
            return ''
        return ''

    text = re.sub(r'<([A-Z][A-Za-z0-9]*)([^>]*)>', opener, text)
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
    text = MARKDOWN_IMAGE_PATTERN.sub(lambda m: replace_markdown_image(m.group(1), m.group(2)), text)
    text = IFRAME_PATTERN.sub('\n*嵌入式演示请参阅原文链接*\n', text)
    text = text.replace('](/', '](./')
    text = re.sub(r'\{`([^`]*)`\}', r'`\1`', text)
    text = re.sub(r'\{([^}]+)\}', lambda m: m.group(1) if not any(ch in m.group(1) for ch in '{}$') else m.group(0), text)
    text = UPPER_TAG_PATTERN.sub('', text)
    text = DOUBLE_SPACE_PATTERN.sub('', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'\n\[编辑此页面[^\n]*\n?', '\n', text)
    text = re.sub(r'\n\[提交问题[^\n]*\n?', '\n', text)
    return text.strip(), metadata


def replace_markdown_image(alt: str, url: str) -> str:
    local_path = hash_remote_url(url)
    if local_path.exists():
        return f'![{alt}]({local_path.relative_to(ROOT).as_posix()})'
    placeholder = ROOT / 'images' / 'remote' / 'download-failed.png'
    if placeholder.exists():
        return f'![{alt}]({placeholder.relative_to(ROOT).as_posix()})'
    return f'![{alt}]({url})'


def read_clean(path: Path) -> str:
    raw = path.read_text(encoding='utf-8')
    cleaned, _ = clean_mdx(raw)
    return cleaned


def slice_until(text: str, stop_heading: str) -> str:
    lines = text.splitlines()
    result = []
    for line in lines:
        if line.strip() == stop_heading.strip():
            break
        result.append(line)
    return '\n'.join(result).strip()


def slice_between(text: str, start_heading: str, end_heading: Optional[str]) -> str:
    lines = text.splitlines()
    start_idx = None
    for idx, line in enumerate(lines):
        if line.strip() == start_heading.strip():
            start_idx = idx
            break
    if start_idx is None:
        return ''
    end_idx = len(lines)
    if end_heading:
        for idx in range(start_idx + 1, len(lines)):
            if lines[idx].strip() == end_heading.strip():
                end_idx = idx
                break
    return '\n'.join(lines[start_idx:end_idx]).strip()


def main():
    paths = {
        'intro': ROOT / 'zh-hans' / 'introduction.mdx',
        'application_overview': ROOT / 'zh-hans' / 'guides' / 'application-orchestrate' / 'readme.mdx',
        'application_create': ROOT / 'zh-hans' / 'guides' / 'application-orchestrate' / 'creating-an-application.mdx',
        'knowledge_import': ROOT / 'zh-hans' / 'guides' / 'knowledge-base' / 'create-knowledge-and-upload-documents' / 'import-content-data' / 'readme.mdx',
        'knowledge_pipeline': ROOT / 'zh-hans' / 'guides' / 'knowledge-base' / 'knowledge-pipeline' / 'readme.mdx',
        'knowledge_chunking': ROOT / 'zh-hans' / 'guides' / 'knowledge-base' / 'create-knowledge-and-upload-documents' / 'chunking-and-cleaning-text.mdx',
        'knowledge_index': ROOT / 'zh-hans' / 'guides' / 'knowledge-base' / 'create-knowledge-and-upload-documents' / 'setting-indexing-methods.mdx',
        'knowledge_manage': ROOT / 'zh-hans' / 'guides' / 'knowledge-base' / 'knowledge-and-documents-maintenance' / 'introduction.mdx',
        'knowledge_documents': ROOT / 'zh-hans' / 'guides' / 'knowledge-base' / 'knowledge-and-documents-maintenance' / 'maintain-knowledge-documents.mdx',
        'knowledge_api': ROOT / 'zh-hans' / 'guides' / 'knowledge-base' / 'knowledge-and-documents-maintenance' / 'maintain-dataset-via-api.mdx',
        'workflow': ROOT / 'zh-hans' / 'guides' / 'workflow' / 'readme.mdx',
        'workflow_key_concept': ROOT / 'zh-hans' / 'guides' / 'workflow' / 'key-concept.mdx',
        'workflow_nodes': ROOT / 'zh-hans' / 'guides' / 'workflow' / 'node' / 'README.mdx',
        'features': ROOT / 'zh-hans' / 'getting-started' / 'readme' / 'features-and-specifications.mdx',
        'model_overview': ROOT / 'zh-hans' / 'guides' / 'model-configuration' / 'readme.mdx',
        'model_credentials': ROOT / 'zh-hans' / 'guides' / 'model-configuration' / 'manage-model-credential.mdx',
        'model_schema': ROOT / 'zh-hans' / 'guides' / 'model-configuration' / 'schema.mdx',
        'model_load_balancing': ROOT / 'zh-hans' / 'guides' / 'model-configuration' / 'load-balancing.mdx',
        'model_new_provider': ROOT / 'zh-hans' / 'guides' / 'model-configuration' / 'new-provider.mdx',
        'model_customizable': ROOT / 'zh-hans' / 'guides' / 'model-configuration' / 'customizable-model.mdx',
        'tools_readme': ROOT / 'zh-hans' / 'guides' / 'tools' / 'readme.mdx',
        'tools_extensions': ROOT / 'zh-hans' / 'guides' / 'tools' / 'extensions' / 'README.mdx',
        'app_management': ROOT / 'zh-hans' / 'guides' / 'management' / 'app-management.mdx',
        'app_version': ROOT / 'zh-hans' / 'guides' / 'management' / 'version-control.mdx',
        'account_management': ROOT / 'zh-hans' / 'guides' / 'management' / 'personal-account-management.mdx',
        'team_management': ROOT / 'zh-hans' / 'guides' / 'management' / 'team-members-management.mdx',
        'subscription_management': ROOT / 'zh-hans' / 'guides' / 'management' / 'subscription-management.mdx',
    }

    cleaned = {key: read_clean(path) for key, path in paths.items()}

    intro_background = slice_until(cleaned['intro'], '### Dify 能做什么？')
    intro_goals = slice_between(cleaned['intro'], '### Dify 能做什么？', '### 下一步行动')

    lines: list[str] = []
    lines.append('# 智能体平台方案文档')
    lines.append('')
    lines.append('Dify 智能体平台提供从数据治理、模型调度到业务运营的一站式能力。')
    lines.append('本文档整合官方中文资料，按照投标要求梳理平台定位、业务流程、技术架构及各系统模块的实现细节。')
    lines.append('')

    lines.append('## 平台概述')
    lines.append('')
    lines.append('本章节聚焦项目背景与核心目标，明确平台建设的价值主张与应用场景。')
    lines.append('')
    lines.append('### 项目背景')
    lines.append('> 内容来源：`zh-hans/introduction.mdx`')
    lines.append('')
    if intro_background:
        lines.extend(intro_background.splitlines())
    lines.append('')
    lines.append('### 核心目标')
    lines.append('> 内容来源：`zh-hans/introduction.mdx`')
    lines.append('')
    if intro_goals:
        goal_lines = intro_goals.splitlines()
        if goal_lines and goal_lines[0].strip().startswith('###'):
            goal_lines = goal_lines[1:]
        lines.extend(goal_lines)
    lines.append('')

    lines.append('## 总体设计')
    lines.append('')
    lines.append('总体设计部分说明智能体平台的定位、应用类型与交付形态，为后续业务方案奠定基础。')
    lines.append('')
    lines.append('### 核心定位')
    lines.append('> 内容来源：`zh-hans/guides/application-orchestrate/readme.mdx`')
    lines.append('')
    lines.extend(cleaned['application_overview'].splitlines())
    lines.append('')

    lines.append('## 业务流设计')
    lines.append('')
    lines.append('业务流设计覆盖数据接入、知识构建到智能应用交付的端到端路径，确保业务需求能够在平台内顺畅落地。')
    lines.append('')
    lines.append('### 数据源与接入方法')
    lines.append('> 内容来源：`zh-hans/guides/knowledge-base/create-knowledge-and-upload-documents/import-content-data/readme.mdx`')
    lines.append('')
    lines.extend(cleaned['knowledge_import'].splitlines())
    lines.append('')
    lines.append('### 知识化处理与构建方法')
    lines.append('> 内容来源：`zh-hans/guides/knowledge-base/knowledge-pipeline/readme.mdx`')
    lines.append('')
    lines.extend(cleaned['knowledge_pipeline'].splitlines())
    lines.append('')
    lines.append('### 数据清洗与分段策略')
    lines.append('> 内容来源：`zh-hans/guides/knowledge-base/create-knowledge-and-upload-documents/chunking-and-cleaning-text.mdx`')
    lines.append('')
    lines.extend(cleaned['knowledge_chunking'].splitlines())
    lines.append('')
    lines.append('### 索引与检索配置')
    lines.append('> 内容来源：`zh-hans/guides/knowledge-base/create-knowledge-and-upload-documents/setting-indexing-methods.mdx`')
    lines.append('')
    lines.extend(cleaned['knowledge_index'].splitlines())
    lines.append('')
    lines.append('### 智能化应用方法')
    lines.append('> 内容来源：`zh-hans/guides/application-orchestrate/creating-an-application.mdx`')
    lines.append('')
    lines.extend(cleaned['application_create'].splitlines())
    lines.append('')

    lines.append('## 整体架构')
    lines.append('')
    lines.append('整体架构部分阐述平台运行原理、工作流机制与底层技术栈，为系统实施提供技术依据。')
    lines.append('')
    lines.append('### 实现原理')
    lines.append('> 内容来源：`zh-hans/guides/workflow/readme.mdx`')
    lines.append('')
    lines.extend(cleaned['workflow'].splitlines())
    lines.append('')
    lines.append('#### 工作流关键概念')
    lines.append('> 内容来源：`zh-hans/guides/workflow/key-concept.mdx`')
    lines.append('')
    lines.extend(cleaned['workflow_key_concept'].splitlines())
    lines.append('')
    lines.append('#### 核心节点能力说明')
    lines.append('> 内容来源：`zh-hans/guides/workflow/node/README.mdx`')
    lines.append('')
    lines.extend(cleaned['workflow_nodes'].splitlines())
    lines.append('')
    lines.append('### 技术栈')
    lines.append('> 内容来源：`zh-hans/getting-started/readme/features-and-specifications.mdx`')
    lines.append('')
    lines.extend(cleaned['features'].splitlines())
    lines.append('')

    lines.append('## 系统模块设计')
    lines.append('')
    lines.append('系统模块设计聚焦平台的核心子系统，覆盖知识、模型、工具、应用与运营管理的完整能力。')
    lines.append('')
    lines.append('### 知识库模块设计')
    lines.append('> 内容来源：`zh-hans/guides/knowledge-base/knowledge-and-documents-maintenance/introduction.mdx`')
    lines.append('')
    lines.extend(cleaned['knowledge_manage'].splitlines())
    lines.append('')
    lines.append('#### 知识库操作')
    lines.append('> 内容来源：`zh-hans/guides/knowledge-base/knowledge-and-documents-maintenance/maintain-knowledge-documents.mdx`')
    lines.append('')
    lines.extend(cleaned['knowledge_documents'].splitlines())
    lines.append('')
    lines.append('#### API 运维能力')
    lines.append('> 内容来源：`zh-hans/guides/knowledge-base/knowledge-and-documents-maintenance/maintain-dataset-via-api.mdx`')
    lines.append('')
    lines.extend(cleaned['knowledge_api'].splitlines())
    lines.append('')

    lines.append('### 模型管理模块')
    lines.append('> 内容来源：`zh-hans/guides/model-configuration/readme.mdx`')
    lines.append('')
    lines.extend(cleaned['model_overview'].splitlines())
    lines.append('')
    lines.append('#### 模型对接与凭据管理')
    lines.append('> 内容来源：`zh-hans/guides/model-configuration/manage-model-credential.mdx`')
    lines.append('')
    lines.extend(cleaned['model_credentials'].splitlines())
    lines.append('')
    lines.append('#### 模型参数配置规范')
    lines.append('> 内容来源：`zh-hans/guides/model-configuration/schema.mdx`')
    lines.append('')
    lines.extend(cleaned['model_schema'].splitlines())
    lines.append('')
    lines.append('#### 负载均衡与容灾策略')
    lines.append('> 内容来源：`zh-hans/guides/model-configuration/load-balancing.mdx`')
    lines.append('')
    lines.extend(cleaned['model_load_balancing'].splitlines())
    lines.append('')
    lines.append('#### 新模型供应商接入流程')
    lines.append('> 内容来源：`zh-hans/guides/model-configuration/new-provider.mdx`')
    lines.append('')
    lines.extend(cleaned['model_new_provider'].splitlines())
    lines.append('')
    lines.append('#### 自定义模型管理实践')
    lines.append('> 内容来源：`zh-hans/guides/model-configuration/customizable-model.mdx`')
    lines.append('')
    lines.extend(cleaned['model_customizable'].splitlines())
    lines.append('')

    lines.append('### 函数库模块')
    lines.append('> 内容来源：`zh-hans/guides/tools/readme.mdx`')
    lines.append('')
    lines.extend(cleaned['tools_readme'].splitlines())
    lines.append('')
    lines.append('#### 扩展机制')
    lines.append('> 内容来源：`zh-hans/guides/tools/extensions/README.mdx`')
    lines.append('')
    lines.extend(cleaned['tools_extensions'].splitlines())
    lines.append('')

    lines.append('### 应用管理模块')
    lines.append('> 内容来源：`zh-hans/guides/management/app-management.mdx`')
    lines.append('')
    lines.extend(cleaned['app_management'].splitlines())
    lines.append('')
    lines.append('#### 版本治理与发布流程')
    lines.append('> 内容来源：`zh-hans/guides/management/version-control.mdx`')
    lines.append('')
    lines.extend(cleaned['app_version'].splitlines())
    lines.append('')

    lines.append('### 系统管理模块')
    lines.append('')
    lines.append('#### 用户管理与登录认证')
    lines.append('> 内容来源：`zh-hans/guides/management/personal-account-management.mdx`')
    lines.append('')
    lines.extend(cleaned['account_management'].splitlines())
    lines.append('')
    lines.append('#### 团队管理')
    lines.append('> 内容来源：`zh-hans/guides/management/team-members-management.mdx`')
    lines.append('')
    lines.extend(cleaned['team_management'].splitlines())
    lines.append('')
    lines.append('#### 订阅与资源策略')
    lines.append('> 内容来源：`zh-hans/guides/management/subscription-management.mdx`')
    lines.append('')
    lines.extend(cleaned['subscription_management'].splitlines())
    lines.append('')

    text = '\n'.join(lines)
    text = re.sub(r'\n> 内容来源：`[^`]+`\n', '\n', text)
    output_path = ROOT / 'dify-bid-doc.md'
    output_path.write_text(text, encoding='utf-8')
    print(f'已生成 {output_path.name}。')


if __name__ == '__main__':
    main()
