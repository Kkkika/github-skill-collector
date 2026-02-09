# 工作流程指南

> **重要原则**：本工具收集的内容默认为英文。为提供良好的中文体验，**每次收集后必须执行标准化的翻译流程**。

## 1. 收集 (Collection)

### 运行收集脚本
在项目根目录执行：

```bash
# 需确保安装依赖: pip install requests pyyaml
# 需设置 GITHUB_TOKEN 环境变量
python .trae/skills/skill-collector/scripts/collect.py <GitHub仓库URL>
```

此命令将：
- 扫描仓库中的 `SKILL.md`。
- 下载原始内容到 `skill-pages/`。

### 重新扫描
若需更新所有已收集仓库：
```bash
python .trae/skills/skill-collector/scripts/collect.py --rescan-all
```

## 2. 标准化翻译 (Standardized Translation)

收集完成后，**必须**执行以下两步翻译操作，顺序不可颠倒。

### 步骤 A：翻译元数据（汉化首页与侧边栏）

为了确保首页卡片、侧边栏导航显示中文，**直接修改 Markdown 文件的 Frontmatter**：

1.  进入 `skill-pages/` 目录。
2.  逐个打开 `.md` 文件。
3.  在顶部的 YAML Frontmatter 中，翻译 `description` 字段为中文（保留 `name` 为原文）。
4.  保存文件。
5.  执行构建命令，扫描 Frontmatter 并更新 HTML：
    ```bash
    python .trae/skills/skill-collector/scripts/build.py
    ```

### 步骤 B：翻译详情页（汉化文档内容）

1.  进入 `skill-pages/` 目录。
2.  逐个打开 `.md` 文件。
3.  将文档标题 (`# title`) 和正文内容翻译为中文。
    *   **规则 1**：保留所有代码块 (` ```...``` `) 不变。
    *   **规则 2**：保留专业术语（如 API, DTO, JSON, Python 等）。
    *   **规则 3**：保留顶部元数据引用链接。
4.  保存文件。

## 3. 预览与验证 (Preview & Verify)

启动服务进行最终检查：

```bash
python -m http.server 3000
# 或 npx docsify serve .
```

**验收标准**：
- [ ] 首页卡片标题和description为中文。
- [ ] 侧边栏导航为中文。
- [ ] 点击进入文档，一级标题和正文为中文。
- [ ] 代码块格式正确，未被错误翻译。
