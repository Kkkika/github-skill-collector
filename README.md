# GitHub Skill Collector
> **Author**: kika

本项目用于收集 GitHub 仓库中的 Skill，并生成展示网站。

## 项目状态
- **预览服务**: http://localhost:3000/
- 已启动 [Skill 展示 · 首页](https://kkkika.github.io/github-skill-collector/index.html)

## 功能
- 自动扫描 GitHub 仓库中的 `SKILL.md`
- 生成静态展示网站 (Docsify)
- 支持增量更新和本地预览

## 技术栈
- Python
- Docsify

## 开发规范
本项目遵循 `skill-creator` 规范：
- `SKILL.md`: 仅包含元数据和核心入口。
- `references/`: 包含详细的工作流程 (`workflows.md`)。
- `scripts/`: 包含核心执行脚本。
- `assets/`: 包含输出模板。