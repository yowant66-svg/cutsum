# Universal Cutup V1 RC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Gate J 后的 Universal Cutup 持续推进为可安装、可使用、可评测、可重复构建的内部 V1 Release Candidate。

**Architecture:** 保持 `domain → application/strategies → media/providers → CLI/SDK/Skill` 单向依赖，以 CutPlan 为可保存、可重复执行的一等协议。项目拆成九个可独立验证的子计划，每个子计划先写失败测试、实现、跑完整门禁、更新四份控制文档并提交。

**Tech Stack:** Python 3.11+、Pydantic、Typer、FFmpeg/ffprobe、Swift macOS fallback、pytest、Ruff、mypy、REUSE、pip-audit、GitHub Actions。

---

## 子计划与完成顺序

- [x] **阶段 1：Gate J 基础修复**
  提交 `50f63fbe0544e4c4a224e8b6448da60bd2ae0e7d`，157 tests passed。
- [x] **阶段 2：字幕系统产品化**
  计划：`docs/superpowers/plans/2026-07-31-subtitle-productization.md`。
- [x] **阶段 3：教育策略 V1**
  输出教育上下文、视觉依赖、系列拆分、AUTO/DIRECTED 与可播放评测。
- [x] **阶段 4：sports_highlight Alpha**
  输出音频/镜头/回放/OCR 接口、多模态事件协议、AUTO/DIRECTED 与少量合成评测片。
- [x] **阶段 5–6：四轨评测与质量迭代**
  建立访谈、剧情、教育、体育四轨；先盲跑、冻结，再对照参考答案。
- [x] **阶段 7：SDK、CLI、Skill 收口**
  所有命令复用应用层；不可用能力返回结构化错误。
- [x] **阶段 8：基础 9:16**
  中心裁切、手工焦点、fit background、安全区和固定单人基础构图。
- [x] **阶段 9：可靠性与跨平台**
  幂等、恢复、失败记录、临时文件、路径安全、CI 矩阵和能力探测。
- [x] **阶段 10–11：许可证、安全、文档和安装体验**
  干净环境完成至少两条离线链路。
- [x] **阶段 12：内部 Release Candidate**
  锁定 Schema、构建 wheel/sdist、生成评测和复核包；不公开发布。

## 每个子计划的统一门禁

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest -q
uv run reuse lint
uv run pip-audit
uv build
git diff --check
```

## 强制停止条件

只在需要费用、私人凭据/Cookie/OAuth、绕过访问控制、不可替代的版权风险、不可逆数据/Git 操作、公开发布/PyPI/GitHub/正式 Release/申请提交，或产品原则出现根本冲突时停止请求维护者决定。
