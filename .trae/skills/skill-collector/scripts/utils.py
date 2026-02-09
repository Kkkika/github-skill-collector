import shutil
import re
import yaml
from pathlib import Path

# ------------------------- 配置 -------------------------
# 项目根：.trae/skills/github-skill-collector/scripts -> 往上 4 级
_script_dir = Path(__file__).resolve().parent
_skill_root = _script_dir.parent  # .trae/skills/github-skill-collector

# 输出目录：集中在项目根目录，便于浏览
OUTPUT_ROOT = _script_dir.parent.parent.parent.parent
OUTPUT_BASE = OUTPUT_ROOT

PAGES_DIR = OUTPUT_BASE / "skill-pages"

# 模板与静态资源：放在当前 skill 的 assets/ 下，符合 skill-creator 规范
ASSETS_DIR = _skill_root / "assets"

def parse_repo_full(repo_full: str):
    """解析 'owner/repo' -> (owner, repo)。"""
    if not repo_full or "/" not in repo_full:
        return "", repo_full or ""
    owner, repo = repo_full.split("/", 1)
    return owner, repo

def html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )

def extract_frontmatter(content: str):
    """提取 YAML frontmatter 与 body。"""
    if not content.strip().startswith("---"):
        return {}, content
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if not match:
        return {}, content
    fm_str, body = match.group(1), match.group(2)
    try:
        fm = yaml.safe_load(fm_str) or {}
    except Exception:
        fm = {}
    return fm, body

def read_metadata_from_md(file_path: Path) -> dict:
    """从 Markdown 文件中读取元数据 (Frontmatter)。若无 Frontmatter，尝试解析引用块中的description。"""
    if not file_path.exists():
        return {}
    
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return {}

    fm, _ = extract_frontmatter(content)
    
    # 如果没有 Frontmatter (旧文件)，尝试解析引用块
    # 格式: > **description**
    #       >
    #       > ...
    if not fm or not fm.get("description"):
        match = re.search(r'> \*\*description\*\*\s*\n>\s*\n> (.*?)(?:\n\n|\Z)', content, re.DOTALL)
        if match:
            desc = match.group(1).replace("\n> ", "\n").strip()
            if not fm: fm = {}
            fm["description"] = desc
    
    return fm

def name_to_slug(name: str) -> str:
    """将 skill 名称转换为 URL 友好的 slug（小写、连字符、移除特殊字符）。"""
    # 转换为小写
    slug = name.lower().strip()
    # 替换空格、下划线、点号为连字符
    slug = re.sub(r'[\s_\.]+', '-', slug)
    # 移除所有非字母数字和连字符的字符
    slug = re.sub(r'[^a-z0-9\-]', '', slug)
    # 移除连续的连字符
    slug = re.sub(r'-+', '-', slug)
    # 移除首尾连字符
    slug = slug.strip('-')
    # 如果结果为空，返回默认值
    if not slug:
        slug = 'unnamed'
    return slug

def ensure_unique_slug(base_slug: str, used_slugs: set) -> str:
    slug = base_slug
    counter = 2
    while slug in used_slugs:
        slug = f"{base_slug}-{counter}"
        counter += 1
    used_slugs.add(slug)
    return slug

def get_existing_skills_map() -> tuple[dict, set, set]:
    """
    扫描 skill-pages/ 下的所有 Markdown 文件。
    返回:
      1. map: { raw_url: pathlib.Path }  (用于根据 raw_url 找到已存在的文件，以 raw_url 为唯一键)
      2. set: { slug } (用于生成新 slug 时查重)
      3. set: { repo_full } (所有已收录的仓库)
    """
    mapping = {}
    used_slugs = set()
    repos = set()
    
    if not PAGES_DIR.exists():
        return mapping, used_slugs, repos

    for md_file in PAGES_DIR.glob("*.md"):
        meta = read_metadata_from_md(md_file)
        raw_url = meta.get("raw_url")
        repo = meta.get("repo")
        
        # 兼容旧文件：尝试从正文中解析 raw_url 和 repo
        if not raw_url or not repo:
            try:
                content = md_file.read_text(encoding="utf-8")
                # 匹配 [打开原 SKILL.md](url) · owner/repo
                # 格式参考: [打开原 SKILL.md](https://...) · owner/repo
                m = re.search(r'\[.*?\]\((https?://github\.com/.*?/blob/.*?/SKILL\.md)\)\s*·\s*([^\s]+/[^\s]+)', content, re.I)
                if m:
                    if not raw_url: raw_url = m.group(1)
                    if not repo: repo = m.group(2)
            except Exception:
                pass

        if raw_url:
            mapping[raw_url] = md_file
        
        if repo:
            repos.add(repo)
            
        used_slugs.add(md_file.stem)
        
    return mapping, used_slugs, repos
