#!/usr/bin/env python3
"""
负责从 skill-pages/ 目录下的 Markdown 文件生成静态网站 (Docsify + README)。
"""

import json
import sys
import shutil
import yaml
from pathlib import Path

# 导入公共模块
try:
    from utils import (
        OUTPUT_ROOT, 
        OUTPUT_BASE, 
        PAGES_DIR, 
        ASSETS_DIR,
        read_metadata_from_md,
        parse_repo_full,
        html_escape
    )
except ImportError:
    # 尝试调整 sys.path 以支持直接运行
    sys.path.append(str(Path(__file__).parent))
    from utils import (
        OUTPUT_ROOT, 
        OUTPUT_BASE, 
        PAGES_DIR, 
        ASSETS_DIR,
        read_metadata_from_md,
        parse_repo_full,
        html_escape
    )

def format_stars(stars: int) -> str:
    """
    将 star 数格式化，>=1000 显示为 k（保留 1 位小数，尾零去除）。
    @returns 格式化后的 star 文本，例如 1250 -> "1.3k"
    """
    value = int(stars or 0)
    if value >= 1000:
        k = value / 1000
        return f"{k:.1f}".rstrip("0").rstrip(".") + "k"
    return str(value)

def _generate_cards_html_for_readme(all_skills):
    cards = []
    idx = 0
    for item in all_skills:
        s = item["skill"]
        repo_rank = item["repo_rank"]
        owner = item["owner"]
        repo = item["repo"]
        
        idx += 1
        slug = s.get("detail_slug", f"skill-{idx}")
        
        # 尝试从本地文件读取最新 description
        md_rel = s.get("md_rel_path")
        file_desc = None
        if md_rel:
            md_path = OUTPUT_BASE / md_rel
            meta = read_metadata_from_md(md_path)
            file_desc = meta.get("description")

        # 优先使用文件中的 description，如果读不到则回退到 db 中的
        final_desc = file_desc if file_desc is not None else s.get("description")

        name = html_escape(s.get("name", "未命名"))
        desc = html_escape((final_desc or "")[:160])
        raw_url = html_escape(s.get("raw_url", "#"))
        repo_badge = html_escape(f"#{repo_rank} {owner}/{repo}")
        # Docsify 内部跳转链接
        detail_url = html_escape(f"#/skill-pages/{slug}.md")
        
        cards.append(
            f'<a class="card" href="{detail_url}" target="_blank">'
            f'<h3 class="card-title">{name}</h3>'
            f'<p class="card-desc">{desc}</p>'
            f'<div class="card-footer">'
            f'<span class="card-link" data-href="{raw_url}" onclick="event.preventDefault();event.stopPropagation();window.open(this.getAttribute(\'data-href\'),\'_blank\')">原 SKILL.md</span>'
            f'<span class="card-badge">{repo_badge}</span>'
            f'</div>'
            f"</a>"
        )
    return "".join(cards)

def generate_home_html_body(repos_sorted: list, skills_by_repo: dict) -> str:
    """
    生成首页的 HTML 内容（不含 html/body 标签，仅内容）。
    用于注入到 index.html 中。
    """
    # 1. 收集所有 Skill 并展平
    all_skills = []
    for repo_rank, ((owner, repo), _) in enumerate(repos_sorted, start=1):
        repo_skills = skills_by_repo.get((owner, repo), {}).get("skills", [])
        for s in repo_skills:
            all_skills.append({
                "skill": s,
                "repo_rank": repo_rank,
                "owner": owner,
                "repo": repo
            })

    # 2. 全局按 name 排序
    all_skills.sort(key=lambda x: (x["skill"].get("name") or "").lower())

    # 3. 生成卡片 HTML
    # 重新生成卡片 HTML 用于 home.md
    cards_html = _generate_cards_html_for_readme(all_skills)
    
    # 4. 生成底部仓库列表 HTML
    repo_items = []
    for i, ((owner, repo), _) in enumerate(repos_sorted, start=1):
        info = skills_by_repo.get((owner, repo), {})
        stars = info.get("stars", 0)
        full = html_escape(f"{owner}/{repo}")
        repo_items.append(
            f'<li>'
            f'<span class="repo-rank">#{i}</span>'
            f'<a href="https://github.com/{owner}/{repo}" target="_blank" rel="noopener">{full}</a> '
            f'<span class="stars">★ {format_stars(stars)}</span>'
            f'</li>'
        )

    # 组合最终的 HTML 内容
    repo_count = len(repos_sorted)
    skill_count = sum(len(v['skills']) for v in skills_by_repo.values())

    return f"""
<div class="home-content">
  <h1>Skill 展示</h1>
  <p>自动收集指定 GitHub 仓库下的所有 Skill（SKILL.md），生成展示站点。</p>
  <p style="color: var(--text-muted); margin-bottom: 2rem;">
    已收录 <strong>{repo_count}</strong> 个仓库，共 <strong>{skill_count}</strong> 个 Skill。
  </p>

  <div class="cards-wrap">
  {cards_html}
  </div>

  <footer class="site-footer">
  <p style="text-align: center; color: var(--text-muted); font-size: 0.8rem; margin-bottom: 1rem;">Author: kika</p>
  <h2>仓库列表（按 Star 降序）</h2>
  <ul class="repo-list">
  {''.join(repo_items)}
  </ul>
  </footer>
</div>
"""

def make_sidebar_md(skills_by_repo: dict, repos_sorted: list) -> str:
    """侧边栏：首页 + 项目介绍 + 各 Skill 链接（按仓库分组）。"""
    lines = [
        "* [首页](/)",
        "* [关于项目](README.md)",
        ""  # 分隔线
    ]
    for (owner, repo), _ in repos_sorted:
        # 添加仓库分组标题
        repo_name = f"{owner}/{repo}"
        # 使用粗体作为分组标题，或者普通的文本项
        lines.append(f"* **{repo_name}**")
        
        for s in skills_by_repo.get((owner, repo), {}).get("skills", []):
            name = (s.get("name") or "未命名").replace("[", "\\[")  # Docsify 侧栏括号转义
            slug = s.get("detail_slug", "")
            if slug:
                # 缩进表示层级
                lines.append(f"  * [{name}](skill-pages/{slug}.md)")
    return "\n".join(lines)

def make_index_html_content(home_html: str) -> str:
    """
    生成主页 HTML 内容 (index.html)。
    使用 Docsify 框架。
    """
    # 安全转义 HTML 内容以便嵌入 JS
    safe_home_html = json.dumps(home_html)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>Skill Collector</title>
  <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1" />
  <meta name="description" content="GitHub Skill Collector">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0">
  <link rel="stylesheet" href="https://unpkg.com/docsify/lib/themes/dark.css">
  <style>
    :root {{
      /* GitHub Dark Dimmed 风格 */
      --base-bg: #22272e;
      --base-color: #adbac7;
      
      --bg-card: #2d333b; 
      --border-color: #444c56;
      --accent: #539bf5; /* 蓝色系 */
      --text-muted: #ffffff;
      --text-normal: #adbac7;
      --code-bg: #2d333b;
      
      --sidebar-bg: #1c2128;
      --sidebar-border: #444c56;
      --sidebar-color: #adbac7;
    }}
    
    body {{ 
        background-color: var(--base-bg) !important;
        color: var(--base-color) !important;
        font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif !important;
    }}
    
    /* 侧边栏优化 */
    .sidebar {{
        background-color: var(--sidebar-bg) !important;
        border-right: 1px solid var(--sidebar-border) !important;
        color: var(--sidebar-color) !important;
        width: auto;
        max-width: 250px !important;
    }}
    .sidebar ul li a {{ color: var(--text-muted) !important; transition: color 0.2s; }}
    .sidebar ul li.active > a, .sidebar ul li a:hover {{ color: var(--accent) !important; border-right: 2px solid var(--accent); }}
    .sidebar-nav > ul > li > a {{ font-weight: 600; color: var(--text-normal) !important; }}

    /* 调整主内容区域左边距，适配新的 sidebar 宽度 */
    /* 仅在非关闭状态下生效，避免影响移动端或收起状态 */
    body:not(.close) main {{
        padding-left: 250px !important;
    }}
    body:not(.close) .sidebar-toggle {{
        left: 250px !important;
        width: 36px !important; /* 限制宽度 */
        background-color: transparent !important;
    }}
    /* 收起状态下恢复默认位置 */
    body.close .sidebar-toggle {{
        left: 0 !important;
        width: 36px !important;
        background-color: transparent !important;
    }}

    /* 侧边栏详情页模式：只显示当前 Skill 和首页 */
    .sidebar-nav.detail-mode > ul > li {{
        display: none !important;
    }}
    .sidebar-nav.detail-mode > ul > li.active {{
        display: block !important;
    }}
    /* 始终显示第一个 li (通常是首页) */
    .sidebar-nav.detail-mode > ul > li:first-child {{
        display: block !important;
        border-bottom: 1px solid var(--border-color);
        margin-bottom: 10px;
        padding-bottom: 10px;
    }}

    /* 正文区域优化 */
    .content {{ 
        padding-top: 20px; 
        left: 233px;
    }}
    .markdown-section {{ 
        margin: 0 auto; 
        max-width: 94%; 
        padding: 30px 15px 40px; 
        position: relative 
    }}
    .markdown-section h1, .markdown-section h2, .markdown-section h3 {{ color: var(--text-normal) !important; font-weight: 600; }}
    .markdown-section code {{ background-color: var(--code-bg) !important; color: var(--accent) !important; border-radius: 4px; padding: 2px 4px; }}
    .markdown-section pre {{ background-color: #1c2128 !important; border: 1px solid var(--border-color); border-radius: 6px; }}
    .markdown-section blockquote {{ color: var(--text-muted) !important; border-left-color: var(--border-color) !important; }}
    .markdown-section a {{ color: var(--accent) !important; text-decoration: none; }}
    .markdown-section a:hover {{ text-decoration: underline; }}

    /* 卡片视图样式 */
    .cards-wrap {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1.5rem; padding: 1rem 0; margin-bottom: 2rem; }}
    .card {{ 
        display: block; 
        background: var(--bg-card); 
        border: 1px solid var(--border-color); 
        border-radius: 8px; 
        padding: 1.5rem; 
        text-decoration: none !important; 
        color: inherit !important; 
        transition: all 0.2s ease; 
        position: relative; 
        cursor: pointer; 
        box-shadow: 0 1px 3px rgba(0,0,0,0.12);
    }}
    .card:hover {{ 
        border-color: var(--accent); 
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.25);
    }}
    .card-footer {{ display: flex; justify-content: space-between; align-items: center; margin-top: 1rem; }}
    .card-badge {{ font-size: 0.75rem; color: var(--text-muted); background: #22272e; padding: 2px 6px; border-radius: 4px; border: 1px solid var(--border-color); }}
    .card-title {{ margin: 0 0 0.75rem !important; font-size: 1.1rem !important; color: var(--accent) !important; font-weight: 600; border: none !important; }}
    .card-desc {{ margin: 0 !important; font-size: 0.95rem; color: var(--text-muted) !important; display: -webkit-box; -webkit-line-clamp: 3; line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.6; }}
    .card-link {{ font-size: 0.85rem; color: var(--accent) !important; cursor: pointer; display: inline-block; font-weight: 500; }}
    .card-link:hover {{ text-decoration: underline !important; }}
    
    .site-footer {{ border-top: 1px solid var(--border-color); margin-top: 60px; padding-top: 30px; }}
    .repo-list {{ list-style: none; padding: 0; }}
    .repo-list li {{ margin-bottom: 12px; display: flex; align-items: center; }}
    .repo-rank {{ color: var(--text-muted); margin-right: 12px; font-family: monospace; min-width: 30px; }}
    .stars {{ color: #e3b341; font-size: 0.9em; margin-left: 8px; }}

    strong {{ font-size: 12px; }}
    
  </style>
</head>
<body>
  <div id="app"></div>
  <script>
    window.$docsify = {{
      // homepage: 'home.md', // 已移除，使用插件注入 HTML
      // name: 'Skill Collector', // 用户要求移除
      repo: '',
      loadSidebar: true,
      subMaxLevel: 2,
      auto2top: true,
      search: {{
        maxAge: 86400000,
        paths: 'auto',
        placeholder: '搜索...',
        noData: '未找到结果',
        depth: 4,
        hideOtherSidebarContent: false,
      }},
      copyCode: {{
        buttonText: '复制',
        errorText: '错误',
        successText: '已复制'
      }},
      plugins: [
        function(hook, vm) {{
          // 注入首页内容 (由 Python 生成并插入)
          const HOME_HTML = {safe_home_html};

          hook.beforeEach(function(content) {{
            // 如果访问根路径，直接返回 HOME_HTML
            if (vm.route.path === '/') {{
              return HOME_HTML;
            }}
            return content;
          }});

          // 侧边栏模式切换：在详情页只显示当前 Skill 的目录
          hook.doneEach(function() {{
            const nav = document.querySelector('.sidebar-nav');
            if (!nav) return;
            
            const path = vm.route.path;
            // 简单判断：如果在 skill-pages 目录下
            if (path.indexOf('/skill-pages/') === 0) {{
                // 1. 获取当前激活的链接（Skill 标题）和对应的 TOC
                const activeLi = nav.querySelector('li.active');
                const activeLink = activeLi ? activeLi.querySelector('a') : null;
                const toc = activeLi ? activeLi.querySelector('.app-sub-sidebar') : null;

                // 2. 创建自定义侧边栏容器
                const newContent = document.createElement('div');
                newContent.className = 'custom-sidebar-content';
                newContent.style.padding = '10px 0 0 5px';

                // 3. 添加“返回首页”链接
                const homeLink = document.createElement('a');
                homeLink.href = '#/';
                homeLink.textContent = '← 返回首页';
                homeLink.style.display = 'block';
                homeLink.style.marginBottom = '1.5rem';
                homeLink.style.fontWeight = 'bold';
                homeLink.style.color = 'var(--accent)';
                homeLink.style.textDecoration = 'none';
                newContent.appendChild(homeLink);

                // 4. 添加当前 Skill 标题
                if (activeLink) {{
                    const title = document.createElement('div');
                    title.textContent = activeLink.textContent;
                    title.style.fontWeight = 'bold';
                    title.style.marginBottom = '0.5rem';
                    title.style.color = 'var(--text-normal)';
                    title.style.paddingLeft = '0'; 
                    newContent.appendChild(title);
                }}

                // 5. 添加 TOC
                if (toc) {{
                    // 克隆 TOC 节点
                    const newToc = toc.cloneNode(true);
                    newToc.style.marginLeft = '0'; // 重置左边距
                    newToc.style.paddingLeft = '10px';
                    newContent.appendChild(newToc);
                }} else {{
                    const noToc = document.createElement('p');
                    noToc.textContent = '（本文档无目录）';
                    noToc.style.fontSize = '0.85rem';
                    noToc.style.color = 'var(--text-muted)';
                    noToc.style.paddingLeft = '0';
                    newContent.appendChild(noToc);
                }}

                // 6. 替换原有侧边栏内容
                nav.innerHTML = '';
                nav.appendChild(newContent);
            }}
          }});

          hook.beforeEach(function(content) {{
            if (vm.route.path === '/') return content; // 首页不需要再次处理 Frontmatter

            // 匹配 Frontmatter (兼容 Windows \\r\\n 和 Unix \\n)
            const match = content.match(/^---\\r?\\n([\\s\\S]*?)\\r?\\n---\\r?\\n/);
            if (!match) return content;

            const fmText = match[1];
            const metadata = {{}};
            
            // 简单的键值对解析
            let currentKey = null;
            fmText.split(/\\r?\\n/).forEach(function(line) {{
                // 匹配 key: value
                const m = line.match(/^([a-z_]+):\\s*(.*)$/);
                if (m) {{
                  currentKey = m[1];
                  metadata[currentKey] = m[2];
                }} else if (currentKey && line.startsWith('  ')) {{
                  // 处理多行值
                  metadata[currentKey] += ' ' + line.trim();
                }}
            }});

            // 构建自定义 HTML
            let metaHtml = '';
            
            // 1. 使用 metadata.name 作为页面标题
            if (metadata.name) {{
                metaHtml += '<h1>' + metadata.name + '</h1>';
            }}
            
            // 2. 元数据卡片
            metaHtml += '<div class="skill-metadata" style="margin-bottom: 20px; padding: 15px; background-color: var(--bg-card); border: 1px solid var(--border-color); border-radius: 6px;">';
            
            if (metadata.description) {{
               // 移除开头可能的 > 符号
               let cleanDesc = metadata.description.replace(/^>\\s*/, '');
               metaHtml += '<p style="color: var(--text-muted);"><strong>📝 简介：</strong> ' + cleanDesc + '</p>';
            }}
            
            const infos = [];
            if (metadata.repo) infos.push('📦 仓库: <a href="https://github.com/' + metadata.repo + '" target="_blank">' + metadata.repo + '</a>');
            if (metadata.raw_url) infos.push('🔗 <a href="' + metadata.raw_url + '" target="_blank">原 SKILL.md</a>');
            if (metadata.stars) infos.push('⭐ Stars: ' + metadata.stars);
            if (metadata.file_last_updated) {{
                const date = metadata.file_last_updated.split('T')[0];
                infos.push('📅 更新: ' + date);
            }}

            if (infos.length > 0) {{
                metaHtml += '<p style="margin-bottom: 0; color: var(--text-muted); font-size: 0.9em;">' + infos.join(' &nbsp; | &nbsp; ') + '</p>';
            }}
            
            metaHtml += '</div>';

            // 替换 Frontmatter
            return content.replace(match[0], metaHtml);
          }});
        }}
      ]
    }}
  </script>
  <script src="https://unpkg.com/docsify/lib/docsify.min.js"></script>
  <script src="https://unpkg.com/docsify/lib/plugins/search.min.js"></script>
  <script src="https://unpkg.com/docsify/lib/plugins/zoom-image.min.js"></script>
  <script src="https://unpkg.com/docsify-copy-code/dist/docsify-copy-code.min.js"></script>
</body>
</html>"""


def setup_output_assets():
    """Docsify 模式下暂不需要本地静态资源，保留此函数以兼容接口。"""
    pass

def rebuild_site_from_files() -> None:
    """
    扫描 skill-pages/ 下的所有 Markdown 文件，读取 Frontmatter，重建 index.html / README.md / _sidebar.md。
    完全不再依赖 skills_db.json。
    """
    if not PAGES_DIR.exists():
        print("未找到 skill-pages 目录，跳过站点生成。")
        return

    # 结构： skills_by_repo[ (owner, repo) ] = { "stars": int, "skills": [ {meta}, ... ] }
    skills_by_repo = {}

    for md_file in PAGES_DIR.glob("*.md"):
        meta = read_metadata_from_md(md_file)
        if not meta:
            continue
        
        # 必须字段
        repo_full = meta.get("repo")
        if not repo_full:
            continue
            
        owner, repo = parse_repo_full(repo_full)
        if not owner or not repo:
            continue

        stars = int(meta.get("stars", 0))
        
        bucket = skills_by_repo.setdefault((owner, repo), {"stars": 0, "skills": []})
        # 取最大的 stars（防止不同文件记录不一致）
        if stars > bucket["stars"]:
            bucket["stars"] = stars
        
        skill_entry = {
            "name": meta.get("name", md_file.stem),
            "description": meta.get("description", ""),
            "raw_url": meta.get("raw_url", "#"),
            "detail_slug": md_file.stem,  # 文件名即 slug
            "md_rel_path": f"skill-pages/{md_file.name}",
            "file_last_updated": meta.get("file_last_updated", "")
        }
        bucket["skills"].append(skill_entry)

    # 同一仓库内按名称排序
    for k in skills_by_repo.keys():
        skills_by_repo[k]["skills"] = sorted(skills_by_repo[k]["skills"], key=lambda s: (s.get("name") or "").lower())

    # 仓库按 Star 降序
    repos_sorted = sorted(skills_by_repo.items(), key=lambda x: -x[1]["stars"])

    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    
    # 准备静态资源
    setup_output_assets()
    
    # 生成 Sidebar
    (OUTPUT_BASE / "_sidebar.md").write_text(make_sidebar_md(skills_by_repo, repos_sorted), encoding="utf-8")
    
    # 生成主页 HTML (直接注入内容，不生成 home.md)
    home_html = generate_home_html_body(repos_sorted, skills_by_repo)
    index_content = make_index_html_content(home_html)
    (OUTPUT_BASE / "index.html").write_text(index_content, encoding="utf-8")
    
    # 清理旧的 home.md
    home_md_path = OUTPUT_BASE / "home.md"
    if home_md_path.exists():
        try:
            home_md_path.unlink()
        except Exception:
            pass
    
    print(f"已基于文件重建站点：{len(repos_sorted)} 个仓库，共 {sum(len(v['skills']) for v in skills_by_repo.values())} 个 Skill。")

def main():
    rebuild_site_from_files()

if __name__ == "__main__":
    main()
