# Sports Highlight Alpha Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立运动项目中立的 `sports_highlight` Alpha：以可追溯多模态观察为输入，形成完整事件、AUTO/DIRECTED 选择和可执行 CutPlan，并用合成体育素材验证成片。

**Architecture:** 检测 Provider 只输出带时间与置信度的观察，不直接决定高光；核心把音频、镜头、回放、OCR/计分牌、解说和运动强度观察聚合为事件，再验证事件前因、核心动作、结果和反应完整性。体育资格独立于 Highlight14，媒体层仍只执行 CutPlan。

**Tech Stack:** Pydantic、Protocol、现有 CutCandidate/CutPlan、pytest、FFmpeg。

---

### Task 1: 多模态体育协议与 Provider 边界

**Files:**
- Create: `src/universal_cutup/domain/sports.py`
- Modify: `src/universal_cutup/domain/candidates.py`
- Create: `src/universal_cutup/providers/sports.py`
- Modify: `src/universal_cutup/schema.py`
- Test: `tests/contract/test_sports_protocol.py`

- [x] 定义运动项目中立的 observation、event、candidate profile、task request 和 selection result。
- [x] observation 支持 audio peak、shot change、replay、OCR/scoreboard、commentary、motion 等来源和 Provider provenance。
- [x] 回放必须显式关联主事件；单一音量峰值不得自动构成高光。
- [x] 导出正式 Schema，文件 Provider 严格验证输入，不伪装真实检测能力。

### Task 2: 事件聚合、完整性与 AUTO/DIRECTED

**Files:**
- Create: `src/universal_cutup/strategies/sports.py`
- Create: `src/universal_cutup/application/sports.py`
- Modify: `src/universal_cutup/application/sdk.py`
- Test: `tests/contract/test_sports_strategy.py`

- [x] 按时间邻近和显式关联聚合跨模态观察，保留 buildup / action / outcome / reaction 角色。
- [x] AUTO 要求至少两个独立模态或一个强计分结果，并去重主事件与回放。
- [x] DIRECTED 解析中英文得分、扑救、超越、终场、争议、庆祝及“不要回放”等目标。
- [x] 默认保留事件前后上下文，生成 8–60 秒候选和可重放 CutPlan。

### Task 3: 合成评测与可播放诊断片

**Files:**
- Create: `evaluation/sports-alpha-observations.json`
- Create: `scripts/generate_sports_alpha_fixture.py`
- Create: `scripts/run_sports_diagnostic.py`
- Create: `tests/integration/test_sports_alpha_evaluation.py`

- [x] 生成明确标记为 synthetic 的短视频，包含两个事件、一次回放和一个单独噪声峰。
- [x] AUTO 不得选择单独噪声峰或把回放重复成第二个主高光。
- [x] 纯自然语言 DIRECTED 能只取指定事件并排除回放。
- [x] 生成 1–3 个可播放诊断片，保存观察、事件、计划、执行记录和抽帧证据。

### Task 4: Skill、文档、风险与质量门

**Files:**
- Modify: `.agents/skills/cutsum-intelligence/SKILL.md`
- Modify: `.agents/skills/cutsum-intelligence/references/protocol-workflow.md`
- Modify: `docs/progress.md`
- Modify: `docs/release-readiness.md`
- Modify: `docs/risk-register.md`

- [x] 明确体育多模态输入和 transcript-only 不足，禁止宣称未实现的自动检测器。
- [x] 更新 SDK/Skill/Schema、评测证据、决策和风险记录。
- [x] 运行完整质量门并提交，随后进入四轨评测。
