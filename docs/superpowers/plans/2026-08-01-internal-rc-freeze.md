# 内部 0.1.0rc1 冻结计划

**目标：** 不增加新功能，把已经通过的能力、协议、构建、评测证据和开放风险冻结成
可重复构建、可安装、可审查的内部 Release Candidate。

**边界：** 不推送、不打远程 tag、不创建 GitHub/PyPI Release、不公开仓库、不上传
媒体、不提交 Codex for Open Source 申请。

---

## Task 1：版本与协议冻结

- [x] distribution version 统一为 `0.1.0rc1`，策略版本和 Schema version 保持独立。
- [x] 重新导出全部 Schema，验证 manifest hash 与第二次导出字节一致。
- [x] 增加冻结合同，阻止包版本、运行记录和构建元数据漂移。

## Task 2：最终评测与构建证明

- [x] 全量质量门最终通过，并保存测试数、REUSE、依赖审计和构建结果。
- [x] wheel/sdist 连续构建两次 SHA-256 一致。
- [x] fresh venv 从最终 RC wheel 安装并实跑 capabilities、education plan 和 9:16 chain。
- [x] 校验 wheel/sdist 许可证与内容边界。

## Task 3：内部复核包

- [x] 生成 RC 证据索引：阶段提交、能力状态、证据 URI、Schema hash、构建 hash。
- [x] 列出禁止夸大的能力和所有公开前开放项。
- [x] 仓库外生成包含 wheel、sdist、Schema manifest、readiness、risk、provenance 和安装
  证据 manifest 的内部复核 ZIP；不包含媒体和凭据。

## Task 4：完成长期目标

- [x] 更新主计划、progress、readiness、decisions 和 changelog。
- [x] 提交最终 RC 节点，确认工作树干净。
- [x] 只把长期目标标记为内部 RC 完成，不把公开发布或申请标记完成。
