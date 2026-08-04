# V1 Release Readiness

更新时间：2026-08-03

| 能力 | 状态 | 证据或缺口 |
|---|---|---|
| CutPlan 保存与重放 | 已运行 | Gate E–J 集成测试 |
| Python SDK / CLI / Skill 同核 | 已运行 | 公共 SDK、capabilities、教育/体育规划命令、结构化错误合同和全新 venv wheel 实跑 |
| Provider 中立、无 Key 启动 | 已运行 | file/mock/确定性路径 |
| Highlight14 可替换 | 已运行 | adaptive 合同测试 |
| 教育策略 | V1 内部完成 | AUTO/DIRECTED、上下文/陈述资格、视觉依赖协议、系列拆分、MIT 三片实跑；自动视觉检测仍是后续增强 |
| 体育高光 | Alpha（已冻结） | 多模态观察协议、确定性字幕检测、六类 Profile、相邻字幕上下文、多事件、滚动去重、绝杀语义资格、AUTO/DIRECTED 和 RC2 可播放成片已运行；最终语境补丁后 293 项测试、87.76% coverage；MatchState、音频/视觉/OCR 检测与真实许可赛事评测未完成 |
| 中文字幕语义完整 | Gate J 通过 | 两个 MIT 成片与回归测试 |
| 多格式 sidecar | 已运行 | source/translated/bilingual SRT、VTT、ASS |
| 字幕安全区与后端能力 | 已运行 | macOS 实跑；libass 与 unavailable 合同测试 |
| 字幕人可读性评测 | 已运行 | semantic fragment、CPS、视觉行数压力 |
| 9:16 | 基础能力已运行 | 四种确定性模式、结构化构图元数据、平台安全区和 synthetic 可播放成片；真实人物跟踪仍不可用 |
| 四轨评测框架 | 已运行 | 四轨三次确定性回归 `pass^3=1.00`；证据等级与盲测身份冻结已运行 |
| 四轨内容质量 | 待人工复核 | 自动报告明确禁止质量声明；访谈/剧情为 curated protocol，教育/体育固定回归为 synthetic |
| 跨平台 | 远端 CI 已运行 | GitHub-hosted Ubuntu、macOS、Windows Python 3.11 全通过；Ubuntu Python 3.12/3.13、静态检查、构建和 85% branch coverage 门禁全通过 |
| 许可证与 REUSE | Alpha 工程边界批准 | 版权主体 `DXBATM`、完整 Apache-2.0、DCO 1.1、Contributor Covenant 2.1 与维护者批准记录已配置；不宣称法律确权或不侵权保证 |
| 安装和外部文档 | 公开 Alpha 完成 | README、治理、安全、贡献政策和三类 synthetic 示例已发布；fresh wheel 双入口、site-packages 导入和真实 FFmpeg 裁切已验证 |
| 内部 RC | 已达到并冻结 | 历史 `universal-cutup 0.1.0rc2` 证据保持不变；体育最终补丁提交 `37ea6bf` 已定向复核通过 |
| 公开 Alpha | GitHub Release | `cutsum 0.1.0a1`：完整测试与覆盖率门禁、22 Schema、wheel/sdist、CycloneDX SBOM、SHA-256、Release manifest 和 fresh-wheel 成片链路；未上传 PyPI |
