# SDK、CLI、Skill 收口实施计划

**目标：** 为内部 V1 提供稳定的公共 Python SDK、与 SDK 同核的 CLI，以及能够准确选择
入口并识别不可用能力的 repo-local Skill。

**架构：** `universal_cutup.sdk` 是公开导入面，实际用例继续由
`universal_cutup.application.sdk` 编排。CLI 只负责参数/文件边界、JSON 输出和退出码，
不复制候选、选择或能力判断。当前未实现能力通过同一 `CutupError` 协议向 SDK 与 CLI
报告。

---

## Task 1：公共 SDK 与能力协议

- [x] 新增稳定的 `universal_cutup.sdk` 导入面并明确导出清单。
- [x] 定义机器可读的操作能力报告，区分 available、provider_required 和 unavailable。
- [x] 为 transcribe、translate、reframe、package 提供 SDK 级结构化能力边界。
- [x] 增加 SDK 导入兼容、错误代码和能力报告合同测试。

## Task 2：统一本地输入与策略工作流

- [x] 将 SRT/VTT/JSON transcript 文件解析移入应用层 SDK。
- [x] 提供教育 AUTO/DIRECTED 一步规划结果，包含 request、candidates、selection、CutPlan。
- [x] 提供体育 observation file AUTO/DIRECTED 一步规划结果并保留 Provider provenance。
- [x] 增加教育、体育与通用 CutPlan 的 SDK 垂直链路测试。

## Task 3：CLI 同核与结构化错误

- [x] CLI transcript 命令复用应用层加载器。
- [x] 新增 capabilities、education-plan 和 sports-plan 命令。
- [x] 既有 stub 命令改为调用 SDK 能力边界，不在 CLI 重写判断。
- [x] 验证 SDK/CLI 对不可用能力返回一致 code、category、step 和 details。

## Task 4：Skill、文档与阶段收口

- [x] 更新 repo-local Skill 的命令路由、公共 SDK 和结构化失败说明。
- [x] 更新进度、决策、风险与 readiness 文档。
- [x] 运行完整质量门并提交，随后进入基础 9:16。
