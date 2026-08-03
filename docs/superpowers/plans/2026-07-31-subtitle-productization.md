# Subtitle Productization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Gate J 的语义字幕修复扩展为跨格式、可读性可评测、后端能力明确且兼容旧 CutPlan 的 V1 字幕系统。

**Architecture:** source evidence、semantic span、translation record、display unit、visual layout 五层分离。domain 保存协议，application 负责语义重排和可读性，media 负责 sidecar/burn-in 与后端能力，CLI/SDK 只调用同一应用服务。

**Tech Stack:** Pydantic、Python 标准库、FFmpeg/libass、Swift/AppKit fallback、pytest。

---

### Task 1: 字幕时序与可读性协议

**Files:**
- Modify: `src/universal_cutup/domain/subtitles.py`
- Modify: `src/universal_cutup/domain/transcript.py`
- Create: `src/universal_cutup/application/subtitle_readability.py`
- Test: `tests/contract/test_subtitle_productization.py`

- [x] 写失败测试：词级时间必须落在 source cue 内；display unit 必须记录 `sentence|clause|phrase` 语义层级；CPS、行数、孤立功能词和时间覆盖进入可读性报告。
- [x] 运行 `uv run pytest -q tests/contract/test_subtitle_productization.py`，确认新模型缺失导致失败。
- [x] 新增 `SubtitleWordTiming`、`SubtitleSemanticLevel`、`SubtitleReadabilityFinding`、`SubtitleReadabilityReport`，并实现纯函数：

```python
def assess_subtitle_readability(
    units: tuple[SubtitleDisplayUnit, ...],
    *,
    max_characters_per_second: float,
    max_lines: int,
) -> SubtitleReadabilityReport:
    return SubtitleReadabilityReport(
        passed=not findings,
        unit_count=len(units),
        maximum_characters_per_second=maximum_characters_per_second,
        findings=tuple(findings),
    )
```

- [x] 验证词级、句级、显示级映射和 Gate J 向后兼容。

### Task 2: 英文与中文语义重排

**Files:**
- Modify: `src/universal_cutup/application/subtitle_display.py`
- Test: `tests/contract/test_subtitle_semantic_segmentation.py`

- [x] 写失败测试覆盖：标点位于 cue 中部、相邻 cue 组成一句、说话人变化、900ms 间隔、12 秒上限、英文从句边界、中文并列/功能词保护。
- [x] 运行定向测试，确认当前只检查 cue 尾部的算法失败。
- [x] 实现带时间派生的 semantic spans；无词级时间时按 source cue 内字符位置做确定性近似，并标记 `timing_precision="estimated"`，不得伪装为真实词级时间。
- [x] 验证原始 source cues 不被修改，并由候选协议校验 span 到 source cue 的覆盖映射。

### Task 3: Sidecar 格式和双语模式

**Files:**
- Modify: `src/universal_cutup/domain/specs.py`
- Modify: `src/universal_cutup/media/subtitles.py`
- Modify: `src/universal_cutup/media/executor.py`
- Test: `tests/integration/media/test_subtitle_sidecars.py`

- [x] 写失败测试覆盖 source/translated/bilingual 的 SRT、VTT、ASS 输出。
- [x] 新增 `bilingual_sidecar` 和 `sidecar_format: srt|vtt|ass`，旧 `sidecar` 保持兼容。
- [x] 为三种 sidecar 输出同一 display timeline；双语 SRT/VTT 每个时间块包含原文和译文，ASS 保持双样式。
- [x] 验证 sidecar 路径不调用 burn-in 后端；媒体基础裁切仍按 CutPlan 正常执行。

### Task 4: 样式、安全区与平台能力

**Files:**
- Modify: `src/universal_cutup/domain/specs.py`
- Create: `src/universal_cutup/media/capabilities.py`
- Modify: `src/universal_cutup/media/subtitles.py`
- Modify: `src/universal_cutup/media/render_cues.swift`
- Test: `tests/unit/test_subtitle_capabilities.py`
- Test: `tests/integration/media/test_subtitle_safe_area.py`

- [x] 写失败测试覆盖底部/顶部安全区、平台 UI inset、最大宽度、背景透明度、libass/macOS/不可用三种能力状态。
- [x] 新增可序列化安全区和样式字段；明确拒绝未知 font path，不静默替换字体。
- [x] 能力探测返回结构化 backend、限制和 fallback 原因。
- [x] 人工抽帧验证 16:9 字幕样式；自动验证 9:16 TikTok 安全区像素。真正的 9:16 成片与阶段 8 画面重构共同验收，禁止用拉伸画面替代。

### Task 5: CLI、SDK、Skill 与回归评测

**Files:**
- Modify: `src/universal_cutup/application/sdk.py`
- Modify: `src/universal_cutup/cli.py`
- Modify: `.agents/skills/cutsum-intelligence/SKILL.md`
- Create: `evaluation/subtitle-readability-cases.json`
- Create: `tests/integration/test_subtitle_readability_evaluation.py`
- Modify: `docs/progress.md`
- Modify: `docs/decisions.md`
- Modify: `docs/risk-register.md`
- Modify: `docs/release-readiness.md`

- [x] CLI 增加能力检查；CutPlan 提供 sidecar 格式；SDK 暴露语义分段、可读性和能力服务。
- [x] 建立中英最小可读性案例：Gate I 碎词、完整技术定义、阅读速度超限和无 libass。
- [x] 运行定向测试、两个 MIT 诊断成片和完整质量门。
- [x] 更新 Schema、Skill、控制文档和变更记录，以多个可回滚提交完成字幕产品化。
