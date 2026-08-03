# Four-Track Evaluation and Quality Iteration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use eval-harness and superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立访谈、剧情、教育、体育四轨统一评测证据，区分能力评测、确定性回归和人工质量复核，并执行三次连续稳定性验证。

**Architecture:** 评测层不参与候选生成。每条证据明确标记 `real_local`、`synthetic` 或 `curated_protocol`；代码 grader 只判断可确定的协议、约束、稳定性和媒体事实，开放内容质量始终进入 human review。盲测输出必须先冻结，再允许加载参考答案。

**Tech Stack:** Pydantic、现有 benchmark/blind-run harness、pytest、JSON、SHA-256。

---

### Task 1: 四轨评测协议和证据等级

**Files:**
- Modify: `src/universal_cutup/evaluation/models.py`
- Modify: `src/universal_cutup/evaluation/harness.py`
- Test: `tests/contract/test_four_track_evaluation.py`

- [x] 定义四条 track、capability/regression/human-review 类型和证据等级。
- [x] 报告保存 pass@1、pass^3、失败分类、质量声明边界和人工复核状态。
- [x] synthetic/curated_protocol 不得生成真实内容质量通过声明。
- [x] 每条 track 必须至少有一个证据记录，报告才有效。

### Task 2: 可重复四轨运行器

**Files:**
- Create: `evaluation/four-track-v1-manifest.json`
- Create: `src/universal_cutup/application/four_track_evaluation.py`
- Create: `scripts/run_four_track_evaluation.py`
- Test: `tests/integration/test_four_track_evaluation.py`

- [x] 访谈和剧情复用 standard-v1 的策展协议回归，并明确非盲测。
- [x] 教育运行真实策略 fixture，并关联 MIT 本地实跑证据。
- [x] 体育运行真实策略 synthetic fixture，并关联可播放实跑证据。
- [x] 连续运行三次，确定性路径要求 pass^3 = 100%，结构 hash 保持一致。

### Task 3: 盲测冻结与参考答案隔离

**Files:**
- Modify: `src/universal_cutup/domain/blind_runs.py`
- Modify: `src/universal_cutup/application/blind_runs.py`
- Modify: `tests/contract/test_blind_run_isolation.py`

- [x] BlindRunInput 增加四轨标识，同时兼容旧 Gate H 文件。
- [x] 参考答案加载保持 freeze-first，允许声明的 reference JSON 而非硬编码 Gate G 文件名。
- [x] 冻结 manifest 保存 suite/case identity，防止跨样本错配。
- [x] 增加参考路径、候选 ID、时间点和冻结后篡改回归。

### Task 4: 报告、质量迭代和阶段收口

**Files:**
- Modify: `docs/progress.md`
- Modify: `docs/release-readiness.md`
- Modify: `docs/risk-register.md`
- Modify: `.agents/skills/cutsum-intelligence/SKILL.md`

- [x] 运行四轨评测并生成维护者复核包。
- [x] 根据失败分类完成一轮最小质量修正或明确阻塞能力。
- [x] 运行完整质量门、更新阶段状态并提交。
