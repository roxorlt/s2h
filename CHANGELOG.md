# Changelog

## 1.2.0 (2026-04-11)

### 改进
- 硬模板系统：HTML 输出基于 `templates/base.html`，确保所有用户获得一致的页面结构和样式
- UI 文案外置到 `templates/ui_strings.json`（8 语言 18 字段），防止上下文压缩丢失翻译
- 完成报告格式外置到 `templates/completion.txt`
- 分类规则和过滤规则增加结构化 checklist，减少 LLM 判断漂移
- Mermaid 语法校验增加 6 项自检 checklist
- 使用统计通过 Stop hook 确保数据上报（全链路确定性，不依赖 LLM）
- 用户面向文案"遥测"改为"使用统计"

## 1.1.0 (2026-04-10)

### 改进
- 新增"复制页面"和"导出 MD"功能：可以把 HTML 结果复制为 Markdown 格式，便于粘贴给 AI

## 1.0.0 (2026-04-09)

- 首次发布
