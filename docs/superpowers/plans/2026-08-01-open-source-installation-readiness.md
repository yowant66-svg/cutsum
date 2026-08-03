# 开源、安全、文档与安装体验实施计划

**目标：** 在不公开发布的前提下，使仓库达到可供陌生维护者离线安装、理解能力边界、
运行两条真实链路，并能清楚识别尚未完成的法律和人工确认事项。

**审计结论：** wheel 仅含项目源码与 LICENSE/NOTICE，REUSE 和依赖审计通过；没有
版本化媒体、字体或密钥。主要缺口是 README 严重过期、版本化文档存在维护者绝对路径、
本地进程错误可能暴露 home 路径，以及法律主体/项目名/早期参考溯源尚待人工确认。

---

## Task 1：隐私、安全与治理合同

- [x] 命令审计记录将 home 路径稳定替换为 `<HOME>`，继续遮蔽 token/cookie/password。
- [x] 清理版本化 JSON/文档中的维护者绝对路径，改用明确的 local-evidence URI。
- [x] 治理测试阻止常见密钥模式、私人绝对路径和敏感文件进入版本控制。
- [x] SECURITY 说明本地媒体、错误报告、Provider 和漏洞报告边界。

## Task 2：许可证与工程溯源收口

- [x] 记录 Python 依赖、FFmpeg/ffprobe、Swift/AppKit、系统字体和测试素材的分发边界。
- [x] 核验 wheel/sdist 的 LICENSE、NOTICE 和文件清单。
- [x] 明示版权主体、项目名/商标、早期私有参考实现仍需维护者/法律确认。
- [x] 不把 REUSE 通过写成最终法律确权。

## Task 3：陌生用户文档与安装体验

- [x] 重写 README：定位、安装、系统依赖、Quickstart、CLI/SDK/Skill、输入输出、边界。
- [x] 更新 CHANGELOG、NOTICE、CONTRIBUTING、CODE_OF_CONDUCT 与 SECURITY 的内部 V1 状态。
- [x] 文档禁止声称真实人物跟踪、体育检测器、内容质量通过或云端三平台已验证。

## Task 4：两条干净环境离线链路

- [x] 从 fresh wheel 在两个临时 venv 中离线安装，不从源码导入。
- [x] 链路 A：SRT + 自生成媒体 → education AUTO CutPlan → 可播放横屏成片。
- [x] 链路 B：已保存 CutPlan → 9:16 派生计划 → 可播放竖屏成片。
- [x] 保存命令、版本、hash、ffprobe 与 execution record 到 repo 外证据目录。

## Task 5：阶段收口

- [x] 更新风险、决策、进度、readiness 和主计划。
- [x] 运行全量质量门并提交，随后进入内部 RC 冻结。
