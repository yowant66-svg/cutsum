# Educational Distillation V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 transcript 级 `educational_distillation` Alpha 推进为具备上下文、视觉依赖、AUTO/DIRECTED、系列拆分和可播放诊断片的 V1 策略。

**Architecture:** 教育信号是候选上的可追溯证据；教育资格和选择独立于 Highlight14。文本信号由 semantic spans 提取，视觉信号通过显式接口输入，应用层根据 HostIntent/ResolvedTaskProfile 处理 AUTO/DIRECTED 与时长，媒体层只执行 CutPlan。

**Tech Stack:** Pydantic、Python、现有 CutCandidate/CutPlan、pytest、FFmpeg。

---

### Task 1: 教育 V1 协议

**Files:**
- Modify: `src/universal_cutup/domain/education.py`
- Modify: `src/universal_cutup/domain/candidates.py`
- Test: `tests/contract/test_educational_v1.py`

- [x] 写失败测试覆盖 key terms、上下文需求、逻辑角色和视觉依赖。
- [x] 新增 `EducationContextRole`、`EducationVisualDependencyType`、`EducationVisualDependency` 和 `EducationalCandidateProfile`。
- [x] `EducationSignal` 保存 key terms 与上下文角色；视觉证据必须引用候选 evidence。
- [x] 运行定向合同测试和 Schema 导出。

### Task 2: 语义信号与上下文完整性

**Files:**
- Modify: `src/universal_cutup/strategies/educational.py`
- Create: `src/universal_cutup/application/educational.py`
- Test: `tests/contract/test_educational_context.py`

- [x] 先扫描 `subtitle_semantic_spans` / `subtitle_display_units`，再回退 source cues。
- [x] 提取定义、规则、推理、例题、步骤、总结、错误、难点、强调和考试相关 key terms。
- [x] 为候选计算 `self_contained|requires_previous|requires_following|requires_visual`。
- [x] 上下文不完整的候选不得在 AUTO 中伪装为独立知识片。

### Task 3: AUTO、DIRECTED 与系列拆分

**Files:**
- Modify: `src/universal_cutup/strategies/educational.py`
- Modify: `src/universal_cutup/application/duration.py`
- Test: `tests/contract/test_educational_task_modes.py`

- [x] AUTO 优先结构性知识和完整上下文，教师强调提高优先级但不单独入选。
- [x] DIRECTED 按自然语言目标映射 definition/example/steps/mistake/difficult point，并服从宿主数量。
- [x] 默认 15–60 秒；必要上下文可延长到 120 秒并记录原因；超过 120 秒按语义 cue 拆 Part。
- [x] 系列 Part 过滤并重建教育信号、显示字幕、翻译记录和 provenance，重新验证后可序列化。

### Task 4: 教育评测与成片

**Files:**
- Create: `evaluation/educational-v1-cases.json`
- Create: `tests/integration/test_educational_v1_evaluation.py`
- Modify: `.agents/skills/cutsum-intelligence/SKILL.md`
- Modify: `docs/progress.md`
- Modify: `docs/release-readiness.md`

- [x] 建立定义、步骤、例题、难点、错误、视觉依赖和失败案例。
- [x] AUTO 与纯自然语言 DIRECTED 均不得读取候选 ID 或参考时间点。
- [x] 使用来源明确的 MIT 本地材料生成 1–3 个可播放诊断片。
- [x] 运行完整质量门，更新 Skill、Schema、风险和进度并提交。
