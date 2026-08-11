# CutSum Adoption-First Alpha Design

## 1. 目标

以 `CutSum 0.1.0a4` 为首个 PyPI Alpha，把当前已经通过工程验证的能力变成可被外部用户安装、运行、反馈和复核的产品入口。本轮成功标准不是增加体育、视觉或语言能力，而是让陌生用户从 `pip install cutsum` 开始，在不下载第三方媒体、不配置模型密钥的条件下，一条命令生成可播放的访谈、教育和体育示例，并让发布来源和执行结果可核验。

## 2. 本轮范围

### 2.1 必须交付

1. `cutsum demo OUTPUT`：在用户本机生成维护者原创的合成媒体和字幕，调用已发布的 SDK/CLI 同核路径，产出三条可播放示例与机器可读报告。
2. ProcessRunner 有界输出：子进程 stdout/stderr 必须持续排空，内存中只保留确定大小的头尾内容，并记录是否截断、总字节数和退出状态。
3. PyPI 安全发布：使用 GitHub Actions OIDC Trusted Publishing、独立 `pypi` environment 和人工批准；不保存长期 PyPI API Token。
4. 发布物同一性：GitHub Release、TestPyPI 和 PyPI 必须发布同一构建生成的 wheel/sdist，哈希与 Release manifest 对得上。
5. Plugin 分发准备：把现有 repo-local Skill 包装为符合 OpenAI Plugin 分发结构的独立目录，增加 `agents/openai.yaml` 和必要元数据；本轮只证明本地打包、发现和调用，不宣称已经获得官方目录收录。
6. 公共入口完善：README 增加 CI、PyPI、Python 和 License Badge，安装方式改为 PyPI 优先、GitHub Release 校验安装为安全替代路径。
7. 反馈闭环：保留现有 Bug、Feature、Trial Feedback 模板，启用 Discussions，并明确试用者如何提交可复现报告而不上传私人媒体。

### 2.2 明确不做

- 不修改体育识别、体育权重或 MatchState 口径。
- 不增加音频峰值、视觉、OCR、人脸或运动跟踪 Provider。
- 不修改 Highlight14、教育策略、字幕策略或 9:16 构图算法。
- 不捆绑第三方媒体、字体、模型权重或 CC0 二进制素材。
- 不宣称 PyPI 发布、Plugin 打包或自动测试证明内容质量。
- 不把 `0.1.0a4` 宣传为 Beta 或稳定版本。

## 3. 版本与发布边界

- 版本号：`0.1.0a4`。
- 发布渠道：GitHub prerelease、TestPyPI 验证、PyPI prerelease。
- Python：保持 `>=3.11,<3.14`。
- 媒体执行：继续要求系统提供 FFmpeg/ffprobe。
- 发布授权主体：`DXBATM <yowant66@gmail.com>`。
- PyPI 项目名：`cutsum`。发布前必须再次确认项目名仍未被占用。
- PyPI 文件不可覆盖；任何发布前失败都必须发生在正式上传之前。正式 PyPI 上传完成后只能发布新版本修复，不能替换 `0.1.0a4` 文件。

## 4. 架构设计

### 4.1 一键 Demo

新增应用层 Demo 服务，负责：

1. 验证目标目录不存在；
2. 验证 FFmpeg/ffprobe 能力；
3. 生成固定时长、固定画布、维护者原创的合成视频和音频；
4. 物化三份维护者原创 transcript；
5. 通过公共 SDK 创建并执行访谈、教育和体育 CutPlan；
6. ffprobe 每个成片；
7. 写入 `demo-report.json`，记录 CutSum 版本、平台、Python、FFmpeg 能力、输入哈希、计划路径、ExecutionRecord、成片哈希和 `network_provider_calls=0`。

CLI 只负责参数解析和结构化错误输出，不复制生成、规划或执行逻辑。现有 `examples/run_quickstart.py` 改为调用同一应用服务，避免仓库示例和已安装命令发生行为漂移。

Demo 不把 MP4 放进 wheel。生成器、短 transcript 模板和必要的 Python 资源随包发布，媒体在用户机器上即时生成。

### 4.2 ProcessRunner 有界输出

ProcessRunner 保持同步公共接口，但内部改为两个并行读取器持续消费 stdout/stderr。每条流使用有界头尾缓冲：

- 默认最大保留量：每条流 1 MiB；
- 保留前半和后半，中间用确定性截断标记代替；
- 始终读取到 EOF，不能因达到上限而停止排空管道；
- 记录每条流实际读取的 UTF-8 字节总量与 `truncated` 状态；
- 解码继续使用 UTF-8 `errors=replace`；
- 超时和取消先终止进程，短暂等待后再 kill，并等待读取器排空退出；
- POSIX 负返回码转换为可选信号名；Windows 仅保留原始返回码，不假设 POSIX 信号语义。

`ProcessOutcome` 增加兼容性安全的默认字段：`stdout_truncated`、`stderr_truncated`、`stdout_bytes`、`stderr_bytes`、`termination_signal`。既有调用方读取 `stdout`、`stderr`、`return_code` 的行为保持不变。

### 4.3 发布流水线

新增独立 release workflow，采用最小权限：

1. 只接受受保护标签 `v*` 或显式人工触发；
2. checkout 固定 SHA 的 Action；
3. 从标签对应提交构建一次 wheel/sdist；
4. 运行完整测试、覆盖率、REUSE、依赖审计、Schema 漂移、fresh-wheel demo；
5. 生成 SBOM、Release manifest 和 SHA-256；
6. 上传不可变 workflow artifact；
7. TestPyPI job 下载该 artifact 并发布；
8. 从 TestPyPI 在全新环境安装并运行不依赖下载延迟的最小能力检查；
9. PyPI job 使用独立 `pypi` environment 和人工批准，下载同一个 artifact 后发布；
10. GitHub Release 上传同一 artifact 集合。

OIDC 权限只授予实际发布 job。测试和构建 job 不持有 `id-token: write`。正式发布 workflow 不允许 pull request 上下文触发。

### 4.4 Plugin 包装

保留 `.agents/skills/cutsum-intelligence/` 作为仓库开发入口，另在
`distribution/openai-plugin/` 建立可分发 Plugin 包：

- `.codex-plugin/plugin.json` 描述名称、版本、维护者、Apache-2.0 许可证、仓库、关键词、
  Skill 目录和产品能力边界；
- `skills/cutsum-intelligence/` 保存可分发 Skill；
- Skill 内容以单一来源同步或构建时复制，禁止维护两套独立规则；
- `skills/cutsum-intelligence/agents/openai.yaml` 提供显示名称、简述、品牌色和默认提示；
  本轮不提供尚未设计和审查的图标，也不声明未配置的 MCP 依赖；
- Plugin 不内嵌 wheel，不访问凭据，不自动下载媒体，不触发付费 Provider；
- 本地合同测试验证 Plugin 元数据、Skill 路径、描述触发词和禁止事项。

若 OpenAI Plugin 提交流程需要远端 MCP 或额外审查，本轮将其记录为外部发布后续项，不伪造“已上架”状态。

## 5. 错误处理

- Demo 目标已存在：返回 `OUTPUT_EXISTS`，不覆盖任何文件。
- FFmpeg/ffprobe 缺失：返回 `CAPABILITY_UNAVAILABLE` 并给出缺失工具名。
- Demo 中任一轨道失败：保留已完成轨道的审计记录，整体报告标记失败，不把部分成功写成全部成功。
- ProcessRunner 读取器异常：终止子进程并返回 `MEDIA_PROCESS_FAILED`，不得无限等待。
- TestPyPI/PyPI 包名冲突、OIDC 不匹配或上传拒绝：停止发布链路，不自动更名、不使用临时 Token 绕过。
- PyPI 正式上传后验证失败：禁止覆盖已上传文件，立即创建公开 Issue 并准备递增版本修复。

## 6. 测试与验收

### 6.1 Demo

- 单元测试：目录边界、合成 transcript、报告哈希、错误映射。
- 集成测试：本机 FFmpeg 真实生成并执行三条轨道。
- fresh-wheel：不设置 `PYTHONPATH`，在全新 venv 中安装 wheel 后执行 `cutsum demo`。
- 跨平台：Ubuntu、macOS、Windows 均验证命令入口和可播放输出。

### 6.2 ProcessRunner

- 同时产生超过上限的 stdout 和 stderr，确认无死锁、内存保留有界、头尾存在、总字节数正确。
- 无换行的大块输出、非法 UTF-8、正常退出、非零退出、启动失败、超时、取消。
- POSIX 信号终止测试只在 POSIX 运行；Windows 运行返回码兼容测试。

### 6.3 发布与 Plugin

- wheel/sdist 两次构建字节一致；
- Schema 重导出无漂移；
- GitHub artifact、Release、TestPyPI、PyPI 文件 SHA-256 一致；
- PyPI 安装后的版本、入口和 demo 报告均为 `0.1.0a4`；
- Plugin manifest 与 Skill 元数据合同测试通过；
- 当前完整测试和 85% branch coverage 门禁保持通过。

## 7. 成功判定

只有同时满足以下条件，本轮才算完成：

1. 陌生环境能执行 `pip install cutsum==0.1.0a4`；
2. `cutsum demo cutsum-demo` 生成三条可播放示例和成功报告；
3. ProcessRunner 大输出测试证明无死锁且内存保留有界；
4. GitHub `main`、标签和 release workflow 全绿；
5. TestPyPI、PyPI、GitHub Release 的发行文件来自同一构建且哈希一致；
6. repo-local Skill 保持可用，可分发 Plugin 包通过本地合同测试；
7. README 没有夸大体育、视觉、内容质量或 Plugin 收录状态；
8. 至少开放一个明确的公开试用反馈入口。

外部 Star、Fork、Issue、PR 或 testimonial 是后续采用证据，不作为本轮可以伪造或强制完成的验收条件。

## 8. 风险控制

- PyPI 发布不可逆：正式上传前必须完成所有本地、远端和 TestPyPI 门禁。
- 供应链：发布 Action 固定版本，使用 OIDC 和最小权限，不保存长期发布 Token。
- 资源占用：Demo 时长保持短小；ProcessRunner 以字节而非字符限制内存。
- 跨平台：不把 POSIX 信号语义强加到 Windows。
- 权利：只生成维护者原创合成素材，不下载或捆绑第三方媒体。
- 产品边界：本轮不借“生态升级”重新开启体育、教育、字幕或竖屏算法修改。

## 9. 后续阶段

完成 `0.1.0a4` 并获得真实试用反馈后，再以独立设计处理：

1. 体育真实许可评测集和人工标注；
2. 音频显著性 Observation Provider；
3. 可选视觉跟踪 Provider；
4. 安全的可配置 Sports Profile；
5. 日语、韩语等语言包与真实样本评测。
