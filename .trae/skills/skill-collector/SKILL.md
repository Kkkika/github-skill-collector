---
name: skill-collector
description: 当用户提供 GitHub 仓库链接并希望收集或查看该仓库的 Skill 时使用。此 Skill 自动扫描仓库、收集 SKILL.md、支持 Agent 执行翻译，并生成本地 Docsify 网站进行展示。
---

# Skill Collector

当用户请求从 GitHub 仓库收集或查看 Skill 时，请遵循以下流程。

## 核心工作流

1. **收集**：使用 `scripts/collect.py` 收集数据。
2. **翻译**：必须对收集到的内容进行标准化翻译。
3. **展示**：使用 `scripts/build.py` 生成站点，然后启动服务预览。

**详细步骤、命令及翻译规范请参阅 [WORKFLOWS.md](references/workflows.md)。**

## 资源

- **收集脚本**：`scripts/collect.py`
- **构建脚本**：`scripts/build.py`
- **网站模板**：`assets/`
