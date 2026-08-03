# CutSum 长期目标进度

更新时间：2026-08-03

## 当前状态

- 长期目标：从已冻结内部 RC 推进到可公开验证、可持续维护的 CutSum Alpha
- 当前阶段：准备 `cutsum 0.1.0a1` 本地公开发布候选；尚未创建远端或发布
- 当前质量门：CutSum 候选 293 tests passed、87.76% coverage；Ruff、strict mypy、REUSE、
  pip-audit、Schema 对照、可复现构建和 fresh-wheel 双 CLI 验证通过

## 已完成

- Gate A–I：协议、计划/执行解耦、盲测、输出验收等基础。
- Gate J：字幕语义显示单元、上下文翻译、教育 Alpha、两个 MIT 诊断片。
- Gate J 最终质量门：157 tests passed；Ruff、mypy、Swift、REUSE、pip-audit、build 通过。

## 阶段 5–6 完成

- 访谈、剧情、教育、体育使用统一评测协议，明确区分 capability、deterministic
  regression 和 human review。
- 四轨连续三次确定性运行均为 `pass@1=1.00`、`pass^3=1.00`，同时统一保持
  `quality_claim_allowed=false` 和人工复核待定。
- 访谈/剧情证据等级为 `curated_protocol`，教育/体育固定回归为 `synthetic`；
  真实本地成片只作为补充材料，不被自动升级为内容质量结论。
- 盲测冻结 manifest 绑定 suite、case 和 track；参考答案只能在冻结后加载且必须身份匹配。
- 第一轮评测纠正了“合法空选被判失败”的剧情 grader，并将教育语义理解窗口与
  12 秒字幕显示窗口解耦。
- MIT 质量迭代实跑输出例题、定义、完整归纳步骤三片，证据引用为
  `local-evidence://education-v1/quality-iteration/`。
- 四轨报告、证据记录和维护者复核表引用为
  `local-evidence://four-track-v1/`。
- 阶段 5–6 最终质量门：221 tests passed；Ruff、mypy、REUSE、pip-audit、
  wheel/sdist build、diff-check 通过。

## 阶段 7 完成

- 新增稳定公共导入面 `universal_cutup.sdk`，内部应用层仍是用例权威。
- `cutup capabilities` 统一报告 available、provider_required 和 unavailable。
- transcribe、translate、reframe 和 package 的 CLI 与 SDK 共用同一 `CutupError`
  边界及 code/category/step/details。
- SRT/VTT/JSON transcript 加载收入 SDK，CLI 不再复制解析选择。
- `education-plan` 与 `sports-plan` 正式暴露 AUTO/DIRECTED 规划链路，返回
  request、candidates、selection 和便携 CutPlan。
- 体育入口保留 observation file 的 Provider provenance 和 fixture 警告。
- wheel 已在全新临时 venv 中离线安装；公共 SDK 从 site-packages 导入，
  capabilities/education-plan/sports-plan 可见，transcribe 结构化失败实跑通过。
- 当前项目 `.venv` 曾因 macOS hidden 标志导致 editable `.pth` 被 Python 跳过；
  改为 uv non-editable 安装后真实 CLI 恢复。这是本地环境状态，不冒充 wheel 缺陷。
- 阶段 7 最终质量门：233 tests passed；Ruff、mypy、REUSE、pip-audit、
  wheel/sdist build、diff-check 通过。

## 阶段 8 完成

- `center_crop`、`manual_focus`、`fit_background` 和 `fixed_subject` 四种基础
  9:16 模式已通过同一确定性 FFmpeg 执行链路生成可播放竖片。
- 显式目标必须同时满足偶数像素和 9:16；默认禁止静默放大，裁剪几何保持
  codec-safe 偶数坐标。
- ExecutionRecord 以结构化字段记录 crop box、归一化焦点、输出锚点、安全区和
  构图理由；字幕使用最终竖屏画布与同一平台安全区。
- 公共 SDK、CLI 与 repo-local Skill 共用派生 CutPlan 路径；旧计划不被覆盖，
  `tracked_focus` 明确保持 unavailable。
- `fixed_subject` 只使用显式或默认固定焦点，不声称人物检测或跟踪；默认居中时允许
  与 center crop 产生相同画面。
- 合成自有素材的四种成片、CutPlan、ExecutionRecord 和人工检查帧引用为
  `local-evidence://basic-9x16-v2/`。
- 阶段 8 最终质量门：247 tests passed；Ruff、mypy、REUSE、pip-audit、
  wheel/sdist build、diff-check 通过。

## 阶段 9 完成

- 全部候选输出在媒体渲染前统一预检；确定性的既有输出冲突不会先生成半套结果。
- 多文件发布只回滚本次 execution 实际创建且设备号/inode 仍匹配的文件；竞争注入证明
  既有文件和被外部进程替换的路径不会被误删。
- Windows drive、UNC 和反斜杠父目录穿越在所有宿主平台保持相同拒绝语义；原有
  POSIX 与符号链接逃逸测试继续通过。
- ProcessRunner 将 executable 缺失结构化为可恢复失败，运行中取消采用有界
  terminate→kill；失败、超时和取消后无 `.cutup-*` 临时目录残留。
- `capabilities` 同时报告 FFmpeg 与 ffprobe，因此安装不完整不会被写成媒体执行可用。
- 新增只读 GitHub Actions：三平台均安装 FFmpeg 并跑完整测试；Ubuntu 额外覆盖
  Python 3.12/3.13；第三方 Actions 固定到 commit SHA，且没有发布步骤。
- CI workflow 已通过本地合同测试，但因当前禁止推送，尚未在 GitHub-hosted
  Linux/macOS/Windows runner 实际执行，不能声称三平台已经云端通过。
- 阶段 9 最终质量门：258 tests passed；Ruff、mypy、REUSE、pip-audit、
  wheel/sdist build、diff-check 通过。

## 阶段 10–11 完成

- README 已从 Gate 草稿重写为陌生用户文档，覆盖真实能力、系统依赖、wheel/源码安装、
  教育横屏链路、9:16 派生链路、SDK/CLI/Skill、隐私、rights 和能力限制。
- 公共 SDK 新增结构化 `load_cut_plan`；CLI 复用该入口。媒体、transcript 和计划文件
  读取失败只返回 basename，不泄露父目录。
- subprocess 审计命令继续遮蔽凭据参数，并把本机 home 前缀替换为 `<HOME>`。
- 版本化评测/进度文件已改用 `local-evidence://`；治理合同阻止常见密钥、私人 home
  路径和敏感文件名进入 Git。
- `docs/open-source-readiness.md` 记录运行依赖、系统工具、字体、素材和 wheel 分发边界；
  工程证据支持未发现明显外部复制，但版权主体、项目名/商标、早期私有参考记录和
  benchmark 权利仍需人工或法律确认。
- wheel 含项目包与 LICENSE/NOTICE，不含 benchmark、evaluation、repo-local Skill、媒体、
  字体、凭据或本地证据；sdist 含治理文档，分发清单已实际核验。
- 两个 Python 3.12.11 fresh venv 从 wheel 与本机缓存离线安装 14 个包，均从
  site-packages 导入 `0.1.0a1`。链路 A 生成 3 个 640×360 横片；链路 B 从保存计划
  派生并生成 3 个 202×360 的 9:16 竖片，全部 H.264/AAC、16 秒并有 ffprobe/hash。
- Python 3.11 离线尝试因本机缓存缺少对应二进制依赖而正确失败；这不是 wheel 失败，
  说明完全离线安装必须预备匹配 Python/OS/架构的 wheelhouse。
- 完整成功证据引用为 `local-evidence://install-v3/`；首次缓存失败和早期成功记录分别
  保留为 `local-evidence://install-v1/`、`local-evidence://install-v2/`。
- 阶段 10–11 最终质量门：263 tests passed；Ruff、mypy、REUSE、pip-audit、
  wheel/sdist build、分发清单和 diff-check 通过。

## 正在执行

- CutSum 本地公开发布候选复核包与维护者交接。
- 不重新打开体育 Alpha，不创建远端、不推送、不发布、不提交 Codex for Open Source 申请。

## 阶段 14 完成：CutSum 公开 Alpha 候选准备

- 公开项目名与 Python distribution 确定为 `CutSum` / `cutsum`；版权主体为 `DXBATM`，
  维护者、安全和行为准则联系人为 `yowant66@gmail.com`。
- 采用 DCO 1.1 commit sign-off 和 Contributor Covenant 2.1。
- `cutsum` 成为品牌 CLI，继续保留 `cutup`；Python 导入名 `universal_cutup` 和既有协议、
  证据身份保持兼容，避免把品牌调整扩大为破坏性 API 迁移。
- 历史 RC 证据不改名、不重算、不冒充 CutSum Alpha 证据；本轮将生成独立的新候选证据。
- 新发行在隔离 Python 3.12 环境从 wheel 安装；`cutsum` 与兼容 `cutup` 的 capability
  输出逐字节一致，导入路径来自 site-packages。
- 两次固定构建时间的 wheel/sdist 字节一致；22 个 Schema 重导出与冻结文件一致。
- 最终本地质量门：293 tests passed、87.76% branch coverage、Ruff、strict mypy、REUSE
  215/215、依赖审计和 diff-check 通过。

## 阶段 15 完成：干净公开历史候选

- 从已审查 tree 导出全新仓库，未复制旧 `.git`、旧分支、tag 或私有完整历史 bundle。
- 默认分支为 `main`，公共历史只包含一个由 `DXBATM <yowant66@gmail.com>` DCO 签署的
  根提交；旧 79 提交历史继续仅作为私有工程证据保存。
- CI 新增独立 Ubuntu / Python 3.12 branch coverage job，显式执行
  `--cov-branch --cov-fail-under=85`；远端未实际运行前仍不宣称跨平台通过。

## 阶段 13 完成：GPT 全面审计后的体育加固

- 将歧义 rugby `try`、cricket `six` 和 football 名词 `score` 固化为负例，同时保留明确
  得分语言正例。
- 本地 transcript Provider 增加 1.5 秒相邻 cue 语境、同段多事件、跨 cue 取消结果和
  rolling caption 去重。
- DIRECTED `绝杀`/`压哨`/`buzzer beater`/`game winner` 要求明确
  `decisive_score` narrative cue，普通得分不再通过该语义资格。
- 体育 CutPlan 新增正式 StrategyRecord、逐候选资格失败原因和有长度上限的 transcript
  evidence excerpt；仍明确不具备 MatchState、比分/时钟/领先变化或跨模态确认。
- distribution 提升为内部 `0.1.0rc2`，避免修正版与已冻结 RC1 产生同名异哈希。
- 最终质量门：287 tests passed；87.70% branch coverage；Ruff、strict mypy、REUSE
  210/210、pip-audit、两次可复现 wheel/sdist build 和 fresh-wheel 体育成片链路通过。
- 证据引用为 `local-evidence://sports-hardening-2026-08-01/`；没有推送、tag、公开
  Release、PyPI 发布或 Codex for Open Source 申请。

## 阶段 12 完成

- distribution version 从 `0.1.0a1` 冻结为 `0.1.0rc1`；Schema version 继续为
  `0.1.0`，教育/体育 Alpha 策略版本保持原身份，不借 RC 改名冒充最终策略。
- 22 个 Schema 在两个独立目录导出结果字节一致，并逐文件匹配
  `schemas/manifest.json`。
- 最终质量门：265 tests passed；Ruff、mypy、REUSE 205/205、第三方依赖 audit、
  wheel/sdist build、diff-check 通过。当前环境也已重装并确认 package metadata 与 import
  都是 `0.1.0rc1`。
- wheel 连续构建 SHA-256：
  `67a9ea776b7661cd49f0204130c542f7b745237b718d7eb16c22860fd2b45fa1`；sdist
  的最终 SHA 只写入仓库外 bundle manifest，避免归档自引用改变自身 hash。
- 最终 RC wheel 在两个 fresh Python 3.12.11 venv 中离线安装并重跑 education AUTO
  横屏三片与保存计划派生 9:16 三片；证据引用为 `local-evidence://install-rc1/`。
- 最终索引为 `docs/internal-rc-evidence-index.md`；内部复核包引用为
  `local-evidence://universal-cutup-internal-0.1.0rc1.zip`，不包含媒体或凭据。
- 本结论只完成内部 RC。没有推送、tag、GitHub/PyPI Release、公开仓库、媒体上传、
  Codex for Open Source 申请或内容质量/法律确权声明。

## 阶段 4 完成

- 新增运动项目中立的 observation / event / profile / task / selection 协议及正式 Schema。
- 音频、镜头、动作、OCR/计分牌、解说、元数据和回放通过可替换 Provider 观察进入核心。
- AUTO 要求跨模态确认或强计分结果，默认去重回放；DIRECTED 支持中英文事件类型、数量和回放控制。
- file Provider 保留真实 provenance，并明确 fixture 不是实际检测器输出。
- 60 秒 synthetic 素材含两个主事件、一次回放和一个独立噪声峰；AUTO 实际渲染得分与扑救两片，DIRECTED “只要一个进球，不要回放”实际渲染一片。
- 独立噪声峰实测音量高于主事件，仍未入选，证明 Alpha 不按单一音量排序。
- 成片、观察、CutPlan、ExecutionRecord 和抽帧证据引用为 `local-evidence://sports-alpha/`。
- 阶段 4 最终质量门：213 tests passed；Ruff、mypy、REUSE、pip-audit、wheel/sdist build、diff-check 通过。

## 阶段 3 完成

- 原始 transcript 可自主生成可追溯教育候选，不读取候选 ID 或参考时间点。
- AUTO 先做上下文、陈述完整性和 transcript 可靠性资格，再按不同知识类型选择。
- DIRECTED 支持纯自然语言数量、必选类型和排除类型。
- 教育 CutPlan 构建与 SDK 入口完成；诊断脚本可从 transcript 直接规划并执行。
- source burn-in 现在优先使用语义 span，避免重新退化为 ASR 微型碎词。
- MIT 6.006 最终 AUTO 成片为例题、算法定义、归纳推理三片，约 16 秒/片；执行与抽帧证据引用为 `local-evidence://education-v1/final-verified/`。
- 定义、步骤、例题、难点、常见错误、视觉依赖和上下文失败案例均有合同或集成评测。
- 阶段 3 最终质量门：200 tests passed；Ruff、mypy、REUSE、pip-audit、wheel/sdist build、diff-check 通过。

## 阶段 3 已完成单元

- 教育信号保存 key terms 和上下文角色。
- 教育视觉依赖支持 slide / blackboard / code / formula / diagram。
- `EducationalCandidateProfile` 对结构信号、上下文和视觉依赖建立正式协议。
- 视觉依赖必须引用候选 evidence。
- semantic spans 优先提取 key terms；AUTO 排除缺少前文或后文的伪独立知识片。
- AUTO 自主选择 1–3 个结构完整知识片；DIRECTED 解析中英文定义/例题/步骤/难点/错误目标与排除项。
- 60–120 秒记录教育上下文延长；超过 120 秒按 cue 拆 Part 并重建 evidence/profile。
- 教育任务请求与选择结果导出正式 Schema；194 tests passed。

## 阶段 2 已完成单元

- 字幕 timing precision：`exact|estimated`。
- display semantic level：`sentence|clause|phrase`。
- `SubtitleWordTiming` 与 source cue 覆盖校验。
- `SubtitleSemanticSpan` 支持 cue 内句界、跨 cue 句子、说话人/间隔和从句时长边界。
- cue 内派生时间明确标记 `estimated`，完整 cue 覆盖保持 `exact`。
- 人可读性报告：CPS 与视觉行数压力。
- source / translated / bilingual sidecar 支持 SRT、VTT、ASS。
- 字幕安全区支持 none / YouTube Shorts / TikTok / Instagram Reels、顶部/底部位置、最大宽度和背景透明度。
- 跨平台能力探测明确返回 ffmpeg-libass / macos-system-overlay / unavailable。
- 16:9 MIT 真实抽帧通过；证据引用为 `local-evidence://subtitle-layout/`。
- CLI `subtitle-capabilities`、SDK 语义分段/可读性/能力服务和 repo-local Skill 已同核。
- 人可读性评测覆盖 Gate I 碎词、完整技术定义与阅读速度超限。
- 181 tests passed。

## 后续顺序

教育 V1 → 体育 Alpha → 四轨评测 → SDK/CLI/Skill → 9:16 → 可靠性/跨平台 → 法务安全文档 → 内部 RC。
