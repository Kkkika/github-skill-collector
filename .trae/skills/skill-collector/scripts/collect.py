#!/usr/bin/env python3
"""
负责从 GitHub 收集 SKILL.md 文件并保存到本地。
"""

import os
import re
import sys
import yaml
import urllib3
from pathlib import Path
from datetime import datetime, timezone

try:
    import requests
except ImportError as e:
    print("请安装依赖: pip install requests pyyaml")
    raise SystemExit(1) from e

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 导入公共模块
try:
    from utils import (
        OUTPUT_ROOT, 
        OUTPUT_BASE, 
        PAGES_DIR, 
        get_existing_skills_map, 
        ensure_unique_slug, 
        name_to_slug, 
        extract_frontmatter,
        read_metadata_from_md,
        parse_repo_full
    )
except ImportError:
    # 尝试调整 sys.path 以支持直接运行
    sys.path.append(str(Path(__file__).parent))
    from utils import (
        OUTPUT_ROOT, 
        OUTPUT_BASE, 
        PAGES_DIR, 
        get_existing_skills_map, 
        ensure_unique_slug, 
        name_to_slug, 
        extract_frontmatter,
        read_metadata_from_md,
        parse_repo_full
    )

GITHUB_API = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"

# ------------------------- GitHub API -------------------------

def get_token():
    # 优先从项目根目录的 GITHUB_TOKEN.txt 读取
    token_file = OUTPUT_ROOT / "GITHUB_TOKEN.txt"
    if token_file.exists():
        try:
            token = token_file.read_text(encoding="utf-8").strip()
            if token:
                return token
        except Exception as e:
            print(f"警告: 读取 GITHUB_TOKEN.txt 失败: {e}")

    # 回退到环境变量
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print(f"错误: 请在 {token_file} 中写入 Token，或设置环境变量 GITHUB_TOKEN")
        sys.exit(1)
    return token

def parse_repo_url(url: str):
    """从 URL 解析 owner/repo，并返回 default_branch。"""
    url = url.strip().rstrip("/")
    # 支持 https://github.com/owner/repo 或 https://github.com/owner/repo/
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url, re.I)
    if not m:
        raise ValueError("无效的 GitHub 仓库 URL")
    owner, repo = m.group(1), m.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo

def api_get(path: str, token: str, session: requests.Session):
    r = session.get(f"{GITHUB_API}{path}", headers={"Authorization": f"token {token}"}, timeout=30)
    r.raise_for_status()
    return r.json()

def get_repo_info(owner: str, repo: str, token: str, session: requests.Session):
    data = api_get(f"/repos/{owner}/{repo}", token, session)
    return {
        "default_branch": data.get("default_branch", "main"),
        "stars": data.get("stargazers_count", 0),
        "full_name": data.get("full_name", f"{owner}/{repo}"),
    }

def get_file_last_updated(owner: str, repo: str, path: str, token: str, session: requests.Session):
    """
    获取某个文件在 GitHub 上的最后更新时间（最近一次提交的时间，ISO8601 字符串）。
    如获取失败，返回空字符串。
    """
    try:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/commits"
        params = {"path": path, "per_page": 1}
        r = session.get(
            url,
            headers={"Authorization": f"token {token}"},
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json() or []
        if not data:
            return ""
        commit = data[0].get("commit") or {}
        author = commit.get("author") or {}
        # author.date 一般存在；若不存在则尝试 committer.date
        date = author.get("date") or (commit.get("committer") or {}).get("date") or ""
        return str(date)
    except Exception:
        return ""

def get_tree_sha(owner: str, repo: str, branch: str, token: str, session: requests.Session):
    ref = api_get(f"/repos/{owner}/{repo}/git/ref/heads/{branch}", token, session)
    commit_sha = ref["object"]["sha"]
    commit = api_get(f"/repos/{owner}/{repo}/git/commits/{commit_sha}", token, session)
    return commit["tree"]["sha"]

def list_skill_files(owner: str, repo: str, branch: str, token: str, session: requests.Session):
    tree_sha = get_tree_sha(owner, repo, branch, token, session)
    tree = api_get(f"/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1", token, session)
    paths = [n["path"] for n in tree.get("tree", []) if n.get("type") == "blob" and n.get("path", "").endswith("SKILL.md")]
    return paths

def download_raw(owner: str, repo: str, branch: str, path: str, session: requests.Session) -> str:
    url = f"{RAW_BASE}/{owner}/{repo}/{branch}/{path}"
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return r.text

# ------------------------- Translation / Processing -------------------------

def is_mainly_chinese(text: str) -> bool:
    """
    粗略判断文本是否主要为中文。
    """
    if not text.strip():
        return True
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    return cjk / max(len(text), 1) > 0.3

def translate_markdown_body(body: str) -> str:
    """
    占位函数：目前不对正文做任何自动翻译，直接返回原文。
    """
    return body

def process_and_translate_content(raw_content: str) -> tuple[dict, str]:
    """
    核心处理流程：
    1. 提取 Frontmatter 和 Body
    2. (可选) 翻译 Description
    3. (可选) 翻译 Body
    返回处理后的 (frontmatter, body)
    """
    # 1. 提取
    fm, body = extract_frontmatter(raw_content)
    
    # 2. 翻译 Description (此处预留位置，当前由 Agent 手动处理或保持原文)
    # if fm.get("description"):
    #     fm["description"] = translate_text(fm["description"])

    # 3. 翻译 Body (占位)
    body = translate_markdown_body(body)
    
    return fm, body

def make_skill_md(name: str, description: str, body: str, raw_url: str, repo_full: str, stars: int, last_updated: str) -> str:
    """单个 Skill 的 Markdown：Frontmatter + 标题 + 原链接 + 文件更新时间（可选）+ 突出 description + 正文。"""
    # 构造 Frontmatter，包含重建索引所需的所有元数据
    fm = {
        "name": name,
        "description": description,
        "repo": repo_full,
        "stars": stars,
        "raw_url": raw_url,
        "file_last_updated": last_updated
    }
    # 使用 yaml.dump 生成 frontmatter，确保格式正确
    fm_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False).strip()

    parts = [
        f"---",
        f"{fm_str}",
        f"---",
        f"",
    ]
    
    parts.append(body)
    return "\n".join(parts)

# ------------------------- Main Logic -------------------------

def collect_repo(owner: str, repo: str, token: str, session: requests.Session, existing_map: dict, used_slugs: set):
    """
    收集单个仓库的所有 SKILL.md。
    """
    repo_full = f"{owner}/{repo}"
    print(f"正在获取仓库信息: {repo_full} ...")
    try:
        repo_info = get_repo_info(owner, repo, token, session)
    except Exception as e:
        if hasattr(e, "response") and getattr(e.response, "status_code", None) == 404:
            print("  仓库不存在或无权访问")
        else:
            print(f"  获取仓库失败: {e}")
        return

    branch = repo_info["default_branch"]
    stars = repo_info["stars"]
    # 优先使用 API 返回的 full_name (大小写正确)
    repo_full = repo_info.get("full_name") or repo_full

    print("  正在列出 SKILL.md 文件...")
    try:
        paths = list_skill_files(owner, repo, branch, token, session)
    except Exception as e:
        print(f"  列出文件失败: {e}")
        return

    if not paths:
        print("  该仓库下未找到 SKILL.md")
        return

    PAGES_DIR.mkdir(parents=True, exist_ok=True)

    for i, path in enumerate(paths):
        print(f"  处理 ({i+1}/{len(paths)}): {path}")
        
        raw_url = f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"
        # 获取 GitHub 上的最后更新时间
        file_last_updated = get_file_last_updated(owner, repo, path, token, session)
        
        # 检查是否需要下载
        existing_md_path = existing_map.get(raw_url)
        need_download = True
        
        if existing_md_path and existing_md_path.exists():
            # 读取本地文件，比较更新时间
            meta = read_metadata_from_md(existing_md_path)
            local_updated = meta.get("file_last_updated", "")
            
            # 只有当两者都有时间且相等时，才跳过
            if local_updated and file_last_updated and local_updated == file_last_updated:
                 print("    未检测到更新时间变化，跳过下载。")
                 need_download = False
        
        if not need_download:
            continue
            
        print("    发现更新或新文件，重新下载...")
        try:
            raw_content = download_raw(owner, repo, branch, path, session)
        except Exception as e:
            print(f"    下载失败: {e}")
            continue
            
        # === Step 2: Translation / Processing ===
        fm, body = process_and_translate_content(raw_content)
        
        name = fm.get("name") or Path(path).parent.name or "未命名"
        description = fm.get("description") or ""
        
        # 确定 slug
        if existing_md_path:
            slug = existing_md_path.stem
        else:
            base_slug = name_to_slug(name)
            slug = ensure_unique_slug(base_slug, used_slugs)
            
        md_rel = f"skill-pages/{slug}.md"
        md_path = OUTPUT_BASE / md_rel
        
        # 更新内存状态
        existing_map[raw_url] = md_path
        used_slugs.add(slug)
        
        # 生成并写入
        skill_md = make_skill_md(name, description, body, raw_url, repo_full, stars, file_last_updated)
        md_path.write_text(skill_md, encoding="utf-8")


def rescan_all_repos(token: str) -> None:
    """
    扫描 skill-pages/ 下的所有文件，提取仓库列表，然后重新收集这些仓库。
    """
    print("正在扫描本地文件以获取仓库列表...")
    existing_map, used_slugs, repos = get_existing_skills_map()
    
    if not repos:
        print("未找到任何已收录的仓库。")
        return
        
    print(f"发现 {len(repos)} 个仓库，开始重新扫描...")
    
    session = requests.Session()
    session.verify = False
    session.headers["Authorization"] = f"token {token}"
    session.headers["Accept"] = "application/vnd.github.v3+json"
    
    for repo_full in sorted(repos):
        owner, repo = parse_repo_full(repo_full)
        if not owner or not repo:
            continue
        collect_repo(owner, repo, token, session, existing_map, used_slugs)
        
    # 注意：collect.py 只负责收集，不负责 rebuild site
    # 如果需要重建，应提示用户运行 build.py，或在此处调用 build.py 的逻辑
    print("\n收集完成。请运行 build.py 重新生成站点。")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        print("用法:")
        print("  收集单个仓库: python collect.py <GitHub仓库URL>")
        print("  重新扫描所有仓库: python collect.py --rescan-all")
        sys.exit(0)

    cmd = sys.argv[1]

    # 重新扫描所有已收录的仓库
    if cmd == "--rescan-all" or cmd == "--rescan-db": 
        token = get_token()
        rescan_all_repos(token)
        return

    # 收集单个仓库
    url = cmd
    token = get_token()
    try:
        owner, repo = parse_repo_url(url)
    except ValueError as e:
        print(f"错误: {e}")
        print("请提供有效的 GitHub 仓库 URL (例如 https://github.com/owner/repo)")
        sys.exit(1)
    
    session = requests.Session()
    session.verify = False
    session.headers["Authorization"] = f"token {token}"
    session.headers["Accept"] = "application/vnd.github.v3+json"
    
    existing_map, used_slugs, _ = get_existing_skills_map()
    collect_repo(owner, repo, token, session, existing_map, used_slugs)
    
    print("\n收集完成。请运行 build.py 重新生成站点。")

if __name__ == "__main__":
    main()
