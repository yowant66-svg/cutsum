# CutSum Adoption-First Alpha Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 发布可从 PyPI 安装并以 `cutsum demo` 一键实跑的 CutSum `0.1.0a4`，同时加固子进程输出边界并准备可分发 OpenAI Plugin。

**Architecture:** 保持现有领域、策略和媒体执行边界不变；新增独立 Demo 应用服务复用公共 SDK，ProcessRunner 内部改为持续排空的有界字节捕获，发布流水线只构建一次并通过 OIDC 把同一 wheel/sdist 分发到 TestPyPI、PyPI 和 GitHub Release。Plugin 在构建时从 repo-local Skill 单一来源物化，避免维护两份指令。

**Tech Stack:** Python 3.11–3.13、Typer、Pydantic v2、FFmpeg/ffprobe、pytest、GitHub Actions、PyPI Trusted Publishing、OpenAI Agent Skills/Plugin manifest。

---

## 文件结构

- `src/universal_cutup/media/process.py`：有界 stdout/stderr 捕获、终止与信号分类。
- `src/universal_cutup/application/demo.py`：合成素材、三轨规划执行和 Demo 报告的唯一应用服务。
- `src/universal_cutup/cli.py`：新增 `cutsum demo` 参数与结构化错误映射。
- `examples/generate_demo_media.py`、`examples/run_quickstart.py`：薄包装，调用应用服务。
- `.agents/skills/cutsum-intelligence/agents/openai.yaml`：repo-local Skill 的界面元数据单一来源。
- `distribution/openai-plugin/.codex-plugin/plugin.json`：Plugin manifest 模板。
- `scripts/build_openai_plugin.py`：复制单一 Skill 来源并生成确定性 Plugin ZIP。
- `scripts/verify_published_release.py`：核对 PyPI JSON 中 wheel/sdist 的版本与 SHA-256。
- `.github/workflows/release.yml`：一次构建、TestPyPI、PyPI、GitHub Release 发布链路。
- `tests/unit/test_process_runner.py`：大输出、无换行、非法 UTF-8、信号与兼容回归。
- `tests/unit/test_demo.py`：Demo 输入、边界和报告单元测试。
- `tests/integration/media/test_demo_cli.py`：真实 FFmpeg 三轨 CLI 测试。
- `tests/contract/test_openai_plugin.py`：Plugin manifest、Skill 同源和边界合同。
- `tests/contract/test_release_workflow.py`：发布触发器、权限、固定 Action SHA 和同一 artifact 合同。

### Task 1: ProcessRunner 有界输出

**Files:**
- Modify: `src/universal_cutup/media/process.py:1-196`
- Modify: `tests/unit/test_process_runner.py`

- [ ] **Step 1: 写入同时覆盖 stdout/stderr 的失败测试**

在 `tests/unit/test_process_runner.py` 增加：

```python
def test_large_stdout_and_stderr_are_drained_and_bounded() -> None:
    size = 2 * 1024 * 1024
    result = ProcessRunner(max_output_bytes=64 * 1024).run(
        [
            sys.executable,
            "-c",
            (f"import os,sys; os.write(1, b'A' * {size}); os.write(2, b'B' * {size}); sys.exit(7)"),
        ],
        timeout_seconds=10,
    )

    assert result.status is ProcessStatus.FAILED
    assert result.return_code == 7
    assert result.stdout_bytes == size
    assert result.stderr_bytes == size
    assert result.stdout_truncated is True
    assert result.stderr_truncated is True
    assert len(result.stdout.encode("utf-8")) <= 64 * 1024 + 128
    assert len(result.stderr.encode("utf-8")) <= 64 * 1024 + 128
    assert result.stdout.startswith("A" * 100)
    assert result.stdout.endswith("A" * 100)
    assert "[output truncated]" in result.stdout
```

另加无换行大块、默认字段和 POSIX 信号测试：

```python
def test_small_output_is_not_marked_truncated() -> None:
    result = ProcessRunner(max_output_bytes=1024).run(
        [sys.executable, "-c", "print('ok')"], timeout_seconds=2
    )
    assert result.stdout == "ok\n"
    assert result.stdout_bytes == 3
    assert result.stdout_truncated is False


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal semantics")
def test_negative_return_code_records_signal_name() -> None:
    result = ProcessRunner().run(
        [sys.executable, "-c", "import os,signal; os.kill(os.getpid(), signal.SIGTERM)"],
        timeout_seconds=2,
    )
    assert result.status is ProcessStatus.FAILED
    assert result.termination_signal == "SIGTERM"
```

- [ ] **Step 2: 运行测试确认旧实现失败**

Run: `uv run pytest -q tests/unit/test_process_runner.py`

Expected: FAIL，原因包括 `ProcessRunner` 不接受 `max_output_bytes`，且 `ProcessOutcome` 缺少字节数、截断和信号字段。

- [ ] **Step 3: 实现持续排空的有界字节缓冲**

在 `src/universal_cutup/media/process.py` 增加以下核心类型；截断标记必须计入最终保留文本，但不计入原始字节总数：

```python
import os
import signal
from threading import Thread
from typing import BinaryIO

TRUNCATION_MARKER = b"\n... [output truncated] ...\n"
DEFAULT_MAX_OUTPUT_BYTES = 1024 * 1024


class _BoundedCapture:
    def __init__(self, limit: int) -> None:
        if limit < len(TRUNCATION_MARKER) + 2:
            raise ValueError("max_output_bytes is too small")
        self._limit = limit
        self._head_limit = (limit - len(TRUNCATION_MARKER)) // 2
        self._tail_limit = limit - len(TRUNCATION_MARKER) - self._head_limit
        self._head = bytearray()
        self._tail = bytearray()
        self.total_bytes = 0

    def feed(self, chunk: bytes) -> None:
        self.total_bytes += len(chunk)
        head_missing = self._head_limit - len(self._head)
        if head_missing > 0:
            self._head.extend(chunk[:head_missing])
            chunk = chunk[head_missing:]
        if chunk:
            self._tail.extend(chunk)
            if len(self._tail) > self._tail_limit:
                del self._tail[: -self._tail_limit]

    @property
    def truncated(self) -> bool:
        return self.total_bytes > self._limit

    def text(self) -> str:
        payload = (
            bytes(self._head) + TRUNCATION_MARKER + bytes(self._tail)
            if self.truncated
            else bytes(self._head) + bytes(self._tail)
        )
        return payload.decode("utf-8", errors="replace")


def _drain(stream: BinaryIO, capture: _BoundedCapture) -> None:
    for chunk in iter(lambda: stream.read(64 * 1024), b""):
        capture.feed(chunk)
```

把 `ProcessOutcome` 扩展为：

```python
stdout_truncated: bool = False
stderr_truncated: bool = False
stdout_bytes: int = 0
stderr_bytes: int = 0
termination_signal: str | None = None
```

把 `ProcessRunner` 构造器和执行实现改为二进制管道＋两个读取线程：

```python
def __init__(self, *, max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES) -> None:
    if max_output_bytes < len(TRUNCATION_MARKER) + 2:
        raise ValueError("max_output_bytes is too small")
    self.max_output_bytes = max_output_bytes
```

`Popen` 使用 `text=False`；启动后分别创建 daemon reader thread，主线程用 `process.poll()`、取消事件和 deadline 控制进程。进程结束后 `wait()`，再 `join(timeout=2)`；任一读取线程仍存活时 kill 子进程并返回 `FAILED`。POSIX 下仅在 `return_code < 0` 时通过 `signal.Signals(-return_code).name` 填充 `termination_signal`，Windows 保持 `None`。

- [ ] **Step 4: 运行 ProcessRunner 回归**

Run: `uv run pytest -q tests/unit/test_process_runner.py`

Expected: PASS，且大输出测试在 10 秒内结束。

- [ ] **Step 5: 运行媒体进程相关测试**

Run: `uv run pytest -q tests/unit/test_process_runner.py tests/integration/media/test_media_execution.py tests/integration/media/test_vertical_reframe_execution.py`

Expected: PASS，既有错误码和媒体执行不漂移。

- [ ] **Step 6: 提交**

```bash
git add src/universal_cutup/media/process.py tests/unit/test_process_runner.py
git commit -s -m "fix: bound subprocess diagnostic output"
```

### Task 2: 安装后一键 Demo 应用服务

**Files:**
- Create: `src/universal_cutup/application/demo.py`
- Create: `tests/unit/test_demo.py`
- Create: `tests/integration/media/test_demo_cli.py`
- Modify: `src/universal_cutup/cli.py`
- Modify: `examples/generate_demo_media.py`
- Modify: `examples/run_quickstart.py`
- Modify: `tests/integration/test_public_examples.py`

- [ ] **Step 1: 写 Demo 应用合同失败测试**

`tests/unit/test_demo.py` 必须覆盖：

```python
def test_demo_rejects_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(CutupError) as raised:
        run_demo(output)
    assert raised.value.code is ErrorCode.OUTPUT_EXISTS
    assert raised.value.step == "demo_preflight"


def test_demo_transcripts_are_maintainer_authored_and_bounded() -> None:
    assert set(DEMO_TRANSCRIPTS) == {"interview", "education", "sports"}
    assert all("00:01:00,000" in content for content in DEMO_TRANSCRIPTS.values())
    assert all(len(content.encode("utf-8")) < 4096 for content in DEMO_TRANSCRIPTS.values())
```

`tests/integration/media/test_demo_cli.py` 使用真实 FFmpeg：

```python
@pytest.mark.timeout(180)
def test_installed_style_demo_generates_three_playable_tracks(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg runtime is unavailable")
    output = tmp_path / "demo"
    result = CliRunner().invoke(app, ["demo", str(output)])
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    report = json.loads((output / "demo-report.json").read_text(encoding="utf-8"))
    assert payload["result"] == "success"
    assert report["cutsum_version"] == __version__
    assert report["network_provider_calls"] == 0
    assert set(report["tracks"]) == {"interview", "education", "sports"}
    assert all(item["status"] == "success" for item in report["tracks"].values())
```

- [ ] **Step 2: 运行测试确认命令和模块不存在**

Run: `uv run pytest -q tests/unit/test_demo.py tests/integration/media/test_demo_cli.py`

Expected: FAIL，`universal_cutup.application.demo` 或 `demo` 命令不存在。

- [ ] **Step 3: 实现 Demo 服务**

`src/universal_cutup/application/demo.py` 定义：

```python
DEMO_TRACKS = ("interview", "education", "sports")
DEMO_DURATION_SECONDS = 60
DEMO_TRANSCRIPTS: dict[str, str] = {
    "interview": INTERVIEW_SRT,
    "education": EDUCATION_SRT,
    "sports": SPORTS_SRT,
}


@dataclass(frozen=True, slots=True)
class DemoResult:
    output_root: Path
    report_path: Path
    report: dict[str, Any]


def generate_demo_media(output: Path, *, duration_seconds: int = 60) -> None: ...
def run_demo(
    output_root: Path, *, selected_tracks: tuple[str, ...] = DEMO_TRACKS
) -> DemoResult: ...
```

三个 SRT 常量逐字采用当前 `examples/transcripts/*.srt` 的维护者原创内容。媒体命令继续使用 `testsrc2`、`sine`、H.264、AAC 和 `-n`，但通过 `ProcessRunner` 执行；失败时映射为 `FFMPEG_NOT_FOUND`、`MEDIA_PROCESS_TIMEOUT` 或 `MEDIA_PROCESS_FAILED`。

`run_demo` 依次：物化 transcript、`inspect_source(..., rights_attestation=OWNED)`、`load_transcript`、公共 SDK 规划、`execute_cut_plan`、读取 ExecutionRecord、ffprobe 成片、计算 SHA-256，最后用 `open("x")` 写 `demo-report.json`。输出报告不得包含绝对路径。

访谈使用 `create_plan`，教育使用 `plan_educational_content(ControlMode.AUTO, "")`，体育使用 `plan_sports_transcript(profile=BASKETBALL, control_mode=DIRECTED, raw_instruction="只要一个绝杀")`。三轨统一使用 preview/360p；访谈保留 source SRT sidecar。

- [ ] **Step 4: 新增 Typer 命令并保持结构化错误**

在 `src/universal_cutup/cli.py` 导入 `run_demo`，增加：

```python
@app.command("demo")
def demo(
    output: Path,
    track: list[str] | None = typer.Option(None, "--track"),
) -> None:
    """Generate and run rights-safe local CutSum examples."""
    try:
        selected_tracks = tuple(track) if track else DEMO_TRACKS
        result = run_demo(output.resolve(), selected_tracks=selected_tracks)
        _emit(result.report)
    except Exception as error:
        _error(error)
```

空 `--track` 代表全部轨道；显式轨道必须属于 `DEMO_TRACKS`，重复值确定性去重，未知值返回 `PROTOCOL_INVALID`。

- [ ] **Step 5: 把仓库 examples 改成薄包装**

`examples/generate_demo_media.py` 只导入并调用应用服务生成器；`examples/run_quickstart.py` 只解析 `--track`，调用 `run_demo` 并打印报告路径。更新 `tests/integration/test_public_examples.py` 断言 `quickstart-report.json` 改为 `demo-report.json`，并验证 examples 与 CLI 使用同一应用逻辑。

- [ ] **Step 6: 运行 Demo 全套测试**

Run: `uv run pytest -q tests/unit/test_demo.py tests/integration/media/test_demo_cli.py tests/integration/test_public_examples.py`

Expected: PASS，三条轨道至少各有一个可播放视频。

- [ ] **Step 7: 提交**

```bash
git add src/universal_cutup/application/demo.py src/universal_cutup/cli.py examples tests/unit/test_demo.py tests/integration/media/test_demo_cli.py tests/integration/test_public_examples.py
git commit -s -m "feat: add installed rights-safe demo"
```

### Task 3: OpenAI Plugin 确定性物化

**Files:**
- Create: `.agents/skills/cutsum-intelligence/agents/openai.yaml`
- Create: `distribution/openai-plugin/.codex-plugin/plugin.json`
- Create: `distribution/openai-plugin/README.md`
- Create: `scripts/build_openai_plugin.py`
- Create: `tests/contract/test_openai_plugin.py`
- Modify: `pyproject.toml` mypy files only if the new script is not already included

- [ ] **Step 1: 写 Plugin 合同失败测试**

```python
def test_plugin_build_copies_repo_skill_byte_for_byte(tmp_path: Path) -> None:
    archive = build_openai_plugin(REPOSITORY_ROOT, tmp_path / "plugin-build")
    with zipfile.ZipFile(archive) as package:
        names = set(package.namelist())
        assert "cutsum/.codex-plugin/plugin.json" in names
        assert "cutsum/skills/cutsum-intelligence/SKILL.md" in names
        assert (
            package.read("cutsum/skills/cutsum-intelligence/SKILL.md")
            == (REPOSITORY_ROOT / ".agents/skills/cutsum-intelligence/SKILL.md").read_bytes()
        )


def test_plugin_manifest_keeps_capability_boundary() -> None:
    manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["name"] == "cutsum"
    assert manifest["license"] == "Apache-2.0"
    assert manifest["skills"] == "./skills/"
    assert "transcript" in manifest["description"].lower()
    assert "visual tracking" not in manifest["description"].lower()
```

- [ ] **Step 2: 运行测试确认构建器不存在**

Run: `uv run pytest -q tests/contract/test_openai_plugin.py`

Expected: FAIL，缺少 manifest、metadata 和构建函数。

- [ ] **Step 3: 增加 Skill UI 元数据**

`.agents/skills/cutsum-intelligence/agents/openai.yaml` 内容固定为：

```yaml
interface:
  display_name: "CutSum Intelligence"
  short_description: "Plan and execute auditable long-video cuts"
  brand_color: "#315C47"
  default_prompt: "Use $cutsum-intelligence to analyze this authorized transcript and create a validated CutSum plan without overstating unavailable capabilities."
policy:
  allow_implicit_invocation: true
```

- [ ] **Step 4: 增加 Plugin manifest 和确定性 ZIP 构建器**

`distribution/openai-plugin/.codex-plugin/plugin.json` 使用 `name=cutsum`、`version=0.1.0a4`、维护者 DXBATM、Apache-2.0、GitHub repository/homepage、`skills=./skills/`，interface 仅声明本地规划、审计和媒体执行，不声明 MCP、下载、发布、视觉跟踪或云 Provider。

`scripts/build_openai_plugin.py`：

```python
def build_openai_plugin(repository: Path, output_directory: Path) -> Path:
    if output_directory.exists():
        raise FileExistsError(f"plugin output already exists: {output_directory.name}")
    output_directory.mkdir(parents=True)
    staging = output_directory / "cutsum"
    shutil.copytree(repository / "distribution/openai-plugin", staging)
    shutil.copytree(
        repository / ".agents/skills/cutsum-intelligence",
        staging / "skills/cutsum-intelligence",
    )
    archive = output_directory.with_suffix(".zip")
    write_reproducible_zip(staging, archive, timestamp=(2026, 8, 11, 0, 0, 0))
    return archive
```

ZIP 条目按 POSIX 路径排序，权限固定为 `0644`，时间固定，连续两次构建 SHA-256 必须一致。

- [ ] **Step 5: 运行 Plugin 合同和双构建测试**

Run: `uv run pytest -q tests/contract/test_openai_plugin.py`

Expected: PASS，repo Skill 与 ZIP Skill 字节一致。

- [ ] **Step 6: 提交**

```bash
git add .agents/skills/cutsum-intelligence/agents distribution/openai-plugin scripts/build_openai_plugin.py tests/contract/test_openai_plugin.py
git commit -s -m "feat: package CutSum intelligence plugin"
```

### Task 4: 版本、发行清单和公共文档

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `src/universal_cutup/__init__.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `SECURITY.md`
- Modify: `docs/quickstart.md`
- Modify: `docs/maintainer-release-approval.md`
- Create: `docs/releases/0.1.0a4.md`
- Modify: `scripts/build_public_release.py`
- Modify: `tests/test_governance.py`
- Modify: `tests/unit/test_build_public_release.py`

- [ ] **Step 1: 先更新版本一致性测试为 `0.1.0a4` 并确认失败**

将治理与发行测试中的预期版本改为 `0.1.0a4`，发行清单增加：

```python
assert manifest["publication_targets"] == ["github", "pypi", "testpypi"]
assert manifest["pypi_published"] is False
assert "cutsum-0.1.0a4-openai-plugin.zip" in manifest["assets"]
```

Run: `uv run pytest -q tests/test_governance.py tests/unit/test_build_public_release.py`

Expected: FAIL，当前源码仍为 `0.1.0a3` 且发行器不含 Plugin。

- [ ] **Step 2: 更新所有版本事实源**

把 `pyproject.toml`、`uv.lock`、`src/universal_cutup/__init__.py` 更新为 `0.1.0a4`。运行 `uv lock` 只允许项目自身版本变化。

- [ ] **Step 3: 扩展发行资产构建器**

`scripts/build_public_release.py` 接受 `plugin_archive`，把 ZIP 纳入 assets、SBOM 附件清单和 `SHA256SUMS.txt`。保留 `pypi_published=false` 表示构建时尚未发布，并增加：

```python
"publication_targets": ["github", "pypi", "testpypi"],
"publication_state": "built_not_published",
```

正式发布后的状态不修改该不可变构建清单，而由 Task 7 的远端核验结果证明。

- [ ] **Step 4: 更新公共文档**

README 顶部加入 CI、PyPI、Python、Apache-2.0 Badge；安装首选改为：

```bash
python -m pip install --pre cutsum==0.1.0a4
cutsum demo cutsum-demo
```

保留 GitHub wheel＋SHA-256 作为校验安装路径。明确 PyPI 是 Alpha、FFmpeg 仍为系统依赖、Plugin 只是可安装分发包而非官方收录。更新 quickstart、CHANGELOG、SECURITY、维护者授权和 `docs/releases/0.1.0a4.md`。

- [ ] **Step 5: 运行版本、发行和文档合同测试**

Run: `uv run pytest -q tests/test_governance.py tests/unit/test_build_public_release.py tests/contract/test_openai_plugin.py`

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add pyproject.toml uv.lock src/universal_cutup/__init__.py README.md CHANGELOG.md SECURITY.md docs scripts/build_public_release.py tests/test_governance.py tests/unit/test_build_public_release.py
git commit -s -m "chore: prepare CutSum 0.1.0a4"
```

### Task 5: OIDC 发布工作流合同

**Files:**
- Create: `.github/workflows/release.yml`
- Create: `scripts/verify_published_release.py`
- Create: `tests/contract/test_release_workflow.py`
- Create: `tests/unit/test_verify_published_release.py`

- [ ] **Step 1: 写发布安全合同失败测试**

```python
def test_release_workflow_uses_one_artifact_and_job_scoped_oidc() -> None:
    workflow = yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    assert workflow[True] == {"push": {"tags": ["v*"]}, "workflow_dispatch": {}}
    jobs = workflow["jobs"]
    assert jobs["build"]["permissions"] == {"contents": "read"}
    assert jobs["publish-testpypi"]["permissions"] == {"id-token": "write"}
    assert jobs["publish-pypi"]["permissions"] == {"id-token": "write"}
    assert "startsWith(github.ref, 'refs/tags/v')" in jobs["publish-testpypi"]["if"]
    assert "startsWith(github.ref, 'refs/tags/v')" in jobs["publish-pypi"]["if"]
    assert jobs["publish-pypi"]["environment"] == "pypi"
    assert jobs["publish-testpypi"]["environment"] == "testpypi"
    assert "needs" in jobs["publish-pypi"]


def test_release_actions_are_pinned_to_full_shas() -> None:
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    for uses in re.findall(r"uses:\s+([^\s]+)", text):
        assert re.search(r"@[0-9a-f]{40}$", uses), uses
```

- [ ] **Step 2: 运行合同测试确认 workflow 不存在**

Run: `uv run pytest -q tests/contract/test_release_workflow.py tests/unit/test_verify_published_release.py`

Expected: FAIL。

- [ ] **Step 3: 实现发布物核验脚本**

`scripts/verify_published_release.py` 使用 `urllib.request` 读取 PyPI JSON，不安装新运行依赖：

```python
def verify_pypi_release(
    *, repository_url: str, version: str, expected_hashes: dict[str, str]
) -> dict[str, str]:
    with urlopen(
        f"{repository_url.rstrip('/')}/pypi/cutsum/{version}/json", timeout=30
    ) as response:
        payload = json.load(response)
    observed = {item["filename"]: item["digests"]["sha256"] for item in payload["urls"]}
    if observed != expected_hashes:
        raise ValueError("published distribution hashes do not match the release build")
    return observed
```

测试使用内存 JSON fixture mock `urlopen`，覆盖一致、缺文件和哈希漂移。

- [ ] **Step 4: 实现一次构建的 release workflow**

`.github/workflows/release.yml` 使用以下固定 Action SHA：

- checkout：`d23441a48e516b6c34aea4fa41551a30e30af803`
- setup-uv：`08807647e7069bb48b6ef5acd8ec9567f424441b`
- upload-artifact：`ea165f8d65b6e75b540449e92b4886f43607fa02`
- download-artifact：`d3f86a106a0bac45b974a628896c90dbdf5c8093`
- gh-action-pypi-publish：`dc37677b2e1c63e2034f94d8a5b11f265b73ba33`

`build` job 运行完整门禁、构建 wheel/sdist、Plugin ZIP 和 release assets，然后上传名为 `cutsum-release-${{ github.ref_name }}` 的 artifact。`workflow_dispatch` 仅用于构建演练；所有发布 job 必须额外用 `startsWith(github.ref, 'refs/tags/v')` 防止从分支手动触发外部发布。TestPyPI 和 PyPI job 只下载该 artifact，并把 `cutsum-*.whl` 与 `cutsum-*.tar.gz` 复制到独立 `dist/` 后发布。PyPI job `needs` TestPyPI smoke test，环境为 `pypi`；GitHub Release job `needs` PyPI 核验，使用 `gh release create --prerelease --verify-tag` 上传原始 artifact。

- [ ] **Step 5: 运行 workflow 合同和 YAML 解析测试**

Run: `uv run pytest -q tests/contract/test_release_workflow.py tests/unit/test_verify_published_release.py`

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add .github/workflows/release.yml scripts/verify_published_release.py tests/contract/test_release_workflow.py tests/unit/test_verify_published_release.py
git commit -s -m "ci: add trusted PyPI release workflow"
```

### Task 6: 全量本地验证、PR 与远端 CI

**Files:**
- Inspect: all changed files
- No new production files unless a failing gate identifies a scoped defect

- [ ] **Step 1: 运行格式、静态、类型、许可证和漏洞门禁**

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests scripts examples
uv run reuse lint
uv run pip-audit
```

Expected: 全部 PASS；`pip-audit` 仅允许报告当前未上 PyPI 的本项目跳过，不允许依赖漏洞。

- [ ] **Step 2: 运行完整测试与覆盖率**

```bash
uv run pytest -q --cov=universal_cutup --cov-branch --cov-report=term --cov-fail-under=85
```

Expected: 全部 PASS，branch coverage ≥ 85%。

- [ ] **Step 3: 验证 Schema、可复现构建和 fresh-wheel Demo**

两次设置相同 `SOURCE_DATE_EPOCH` 构建 wheel/sdist/Plugin ZIP并逐字节 `cmp`；临时导出 Schema 后与 `schemas/` 执行 `diff -ru`；在全新 venv、无 `PYTHONPATH` 条件下安装 wheel 并运行：

```bash
cutsum capabilities
cutsum demo /tmp/cutsum-a4-fresh-demo
```

Expected: 三轨成功、版本 `0.1.0a4`、`network_provider_calls=0`、所有成片可由 ffprobe 解码。

- [ ] **Step 4: 隐私和发行边界扫描**

扫描所有可达 Git 对象和构建资产，拒绝用户绝对路径、Token、Cookie、私钥、私人媒体和 Holdout。验证体育核心文件相对 `v0.1.0a3` 未变化。

- [ ] **Step 5: 推送分支、创建 PR 并等待所有检查**

```bash
git push -u origin agent/adoption-release-0.1.0a4
gh pr create --base main --head agent/adoption-release-0.1.0a4 --title "release: CutSum 0.1.0a4 adoption alpha" --body-file /tmp/cutsum-a4-pr.md
gh pr checks --watch
```

Expected: DCO、Ubuntu、macOS、Windows、Python 3.11–3.13、coverage、REUSE、audit 和 build 全绿。

- [ ] **Step 6: 合并并验证 `main`**

使用 GitHub 允许的合并方式合并；确认最终提交含 DXBATM DCO sign-off，重新运行 `main` CI，并从最终提交重新构建待发布 artifact。

### Task 7: TestPyPI、PyPI 和 GitHub Release 发布

**Files:**
- External configuration: GitHub environments `testpypi`, `pypi`
- External configuration: TestPyPI/PyPI pending trusted publisher for `yowant66-svg/cutsum` and `.github/workflows/release.yml`
- 除非外部平台验证暴露真实缺陷，否则不修改源码

- [ ] **Step 1: 再次确认 PyPI 名称和远端环境**

确认 `https://pypi.org/project/cutsum/` 仍为未占用或已由 DXBATM 控制；创建 GitHub `testpypi` 和 `pypi` environment，正式 `pypi` environment 启用维护者人工批准。

- [ ] **Step 2: 配置 Pending Trusted Publishers**

在 TestPyPI 与 PyPI 中配置：Owner `yowant66-svg`、Repository `cutsum`、Workflow `release.yml`、对应 environment。不得生成或保存长期 API Token。

- [ ] **Step 3: 创建并推送最终标签**

```bash
git tag -a v0.1.0a4 FINAL_MAIN_SHA -m "CutSum 0.1.0a4 public Alpha"
git push origin v0.1.0a4
```

Expected: release workflow 从标签提交启动，artifact source commit 与标签解析提交一致。

- [ ] **Step 4: 验证 TestPyPI 后批准 PyPI environment**

TestPyPI 上传完成后，在全新虚拟环境运行：

```bash
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ cutsum==0.1.0a4
cutsum capabilities
```

核对 wheel/sdist SHA-256。全部通过后才批准 `pypi` environment。

- [ ] **Step 5: 验证正式 PyPI 与 GitHub Release**

运行 `scripts/verify_published_release.py` 对比正式 PyPI JSON、TestPyPI JSON 与构建清单。下载 GitHub Release 全部资产并执行 `shasum -a 256 -c SHA256SUMS.txt`。全新 venv 从 PyPI 安装并执行 `cutsum demo`。

- [ ] **Step 6: 启用公开反馈入口并记录结果**

启用 GitHub Discussions，创建不包含虚假用户数据的欢迎帖，链接现有 Trial Feedback Issue 模板。公开记录版本、PyPI URL、Release URL、最终 SHA、CI run、wheel/sdist/Plugin SHA-256 和 fresh-PyPI Demo 结果。

- [ ] **Step 7: 完成条件核验**

逐项对照设计文档第 7 节。若 PyPI、GitHub Release、fresh install、三轨 Demo 或哈希同一性任一失败，本轮保持未完成；不得以“代码已合并”代替发布完成。
