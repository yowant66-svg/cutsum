# 基础 9:16 重构实施计划

**目标：** 在不引入人物检测或跟踪模型的前提下，实现可重放的基础 9:16
中心裁切、手工焦点、模糊背景 fit、安全区和固定单人构图。

**架构：** `ReframeSpec` 保存宿主意图；媒体层将它解析为纯确定性
`ReframeDecision`，再由现有 FFmpeg 剪裁路径执行。字幕始终使用最终输出画幅的
安全区。`tracked_focus` 仍返回结构化不可用，固定单人模式只使用显式或默认固定焦点。

---

## Task 1：垂直构图协议与决策器

- [x] 扩展 ReframeSpec：9:16 安全区、fixed_subject，并严格验证焦点。
- [x] 实现 center_crop、manual_focus、fit_background、fixed_subject 的纯函数决策。
- [x] 禁止非 9:16 显式目标和静默 upscale；记录 crop/focus/anchor/safe-area。
- [x] 增加协议、边界和 FFmpeg filter 单元测试。

## Task 2：媒体执行与可播放验证

- [x] cut_media 执行 ReframeDecision，音频链路不受影响。
- [x] ExecutionRecord 记录 reframe mode、crop box、focus/anchor、safe area 和构图理由。
- [x] 字幕 sidecar/burn-in 按最终 9:16 分辨率解析安全区。
- [x] 用合成可授权素材实际生成四种可播放竖片并用 ffprobe/抽帧验证。

## Task 3：SDK、CLI 与 Skill 同核

- [x] 公共 SDK 支持从旧 CutPlan 派生 reframe CutPlan。
- [x] `cutup reframe` 既能报告能力，也能生成不覆盖的派生计划。
- [x] capabilities 报告四种已运行模式，tracked_focus 保持 unavailable。
- [x] 更新 repo-local Skill 的模式选择和能力边界。

## Task 4：阶段收口

- [x] 导出变更后的 CutPlan/ExecutionRecord Schema。
- [x] 更新进度、readiness、风险与决策文档。
- [x] 运行全量质量门并提交，随后进入可靠性与跨平台。
