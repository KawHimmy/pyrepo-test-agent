# pyrepo-test-agent

`pyrepo-test-agent` 是面向 Python 仓库自动完成仓库扫描、行为规格推断、pytest 测试规划、
并行测试生成、测试执行、失败归因、有限轮次测试修复，并最终输出报告。

当前项目是 LLM 驱动的 Agent 流水线，默认通过 ZAI GLM API 完成规格推断、
测试规划、测试生成和测试修复。运行前需要配置 `ZAI_API_KEY`；没有 Key
或没有安装 `zai` SDK 时，CLI 会直接报错并提示补齐配置。


## 架构

```text
Repo Scanner -> Spec Inference -> Test Planner
                                     |
                                     v
                  Unit Writer + API Writer + Regression Writer
                                     |
                                     v
                    Sandbox Runner -> Failure Analyst -> Repair Agent
                                     |
                                     v
                                  Report
```

对应设计思路：

- 串行 Pipeline：仓库扫描、规格推断、测试规划有明确前后依赖。
- 并行 Writer：单元测试、API 测试、回归测试可以并发生成。
- 执行修复闭环：pytest 失败后先归因，再进行有限轮次的测试修复。
- 共享状态：各 Agent 通过 `TestGenState` 传递结构化信息。

## 安装

基础安装：

```bash
python -m pip install -e .
```

如果需要做 FastAPI 路由测试实验：

```bash
python -m pip install -e ".[api]"
```

如果需要接入 GLM：

```bash
python -m pip install -e ".[llm]"
```

也可以单独安装 LLM 依赖：

```bash
python -m pip install -r requirements-llm.txt
```

## 配置 GLM

推荐把 Key 放到项目根目录的 `.env` 文件中：

```text
ZAI_API_KEY=your-zai-api-key-here
```

CLI 启动时会自动读取：

- 当前运行目录下的 `.env`
- `--repo` 指向的目标仓库目录下的 `.env`

也可以在命令行环境中直接设置：

```bash
set ZAI_API_KEY=your-zai-api-key-here
```

`glm-4.7` 和 `glm-5` 默认都按 5 个并发额度处理。项目内部所有 Agent
共享同一个 LLM Client，并通过 `asyncio.Semaphore(5)` 控制并发，所以并行
Writer 阶段也不会超过 5 个同时请求。每次模型调用默认 120 秒超时，并对
429 等临时错误进行最多 3 次重试。

## 使用方法

扫描当前仓库：

```bash
python -m app.main --repo .
```

使用 GLM-4.7：

```bash
python -m app.main --repo . --llm-model glm-4.7 --llm-concurrency 5
```

切换到 GLM-5：

```bash
python -m app.main --repo . --llm-model glm-5 --llm-concurrency 5
```

调整单次请求超时和重试次数：

```bash
python -m app.main --repo . --llm-timeout 120 --llm-retries 3
```

扫描其他 Python 仓库，并指定变更文件用于回归测试规划：

```bash
python -m app.main --repo ../some-python-repo --changed-file src/package/module.py
```

指定输出目录：

```bash
python -m app.main --repo examples/sample_repo --output output/sample_run --changed-file calculator.py
```

输出结构如下：

```text
<repo>/.agent_test_output/
├─ generated_tests/
│  ├─ test_unit_generated.py
│  ├─ test_api_generated.py
│  └─ test_regression_generated.py
├─ coverage.json
└─ report.md
```

## 生成测试的策略

系统默认调用 GLM 完成：

- 行为规格推断。
- 测试计划生成。
- 单元测试生成。
- API 测试生成。
- 回归测试生成。
- 失败后的测试修复。

为了避免模型过度编造断言，Prompt 会要求优先生成可证明、可运行、可维护的
pytest。对于静态上下文无法确认的业务结果，测试会更倾向于验证这些稳定行为：

- 模块是否可导入。
- 函数或类是否存在。
- 函数是否可调用，类是否为类对象。
- FastAPI 风格路由是否注册。
- 变更文件中的符号是否仍可导入，用作回归保护。

模型输出会经过基础校验：提取 Python 代码块、检查语法、判断是否像 pytest
文件。校验失败时，该 Agent 会记录错误，报告会保留失败信息，便于继续调整
Prompt 或代码上下文。

## 目录结构

```text
app/
├─ agents/      # 单一职责 Agent
├─ core/        # 状态对象、Pipeline、并行执行器、修复循环
├─ llm/         # ZAI/GLM 客户端与代码提取工具
├─ parsers/     # AST 解析、Import 图、变更文件归一化
├─ prompts/     # Prompt 模板
├─ reports/     # Markdown 报告生成
├─ runners/     # pytest 子进程执行器
└─ main.py      # CLI 入口
```

## 核心模块

- `app/core/state.py`：定义 `TestGenState`、仓库信息、规格、测试计划、运行结果和失败报告。
- `app/core/pipeline.py`：串联扫描、推断、规划、并行生成和修复闭环。
- `app/core/parallel_executor.py`：使用 `asyncio.gather` 并行运行 Writer Agent。
- `app/core/repair_loop.py`：执行 pytest、分析失败、触发有限轮次修复。
- `app/llm/zai_client.py`：封装 `ZhipuAiClient`，并统一限制 GLM 并发数。
- `app/runners/pytest_runner.py`：在子进程中运行 pytest，生成 coverage JSON，并收集 stdout/stderr。
- `app/reports/report_builder.py`：输出包含规格、测试计划、覆盖率、失败归因和执行历史的 Markdown 报告。

## 验证

运行项目测试：

```bash
python -m pytest -q
```

当前测试覆盖：

- AST 解析与符号发现。
- 真实 GLM Client 驱动的 Pipeline 端到端流程。
- 生成测试执行、覆盖率采集与报告输出。

注意：测试会读取 `.env` 并真实调用 GLM API。

## 设计边界

- Repair Agent 只修生成的测试，不修改业务源代码。
- 最大修复轮次由 `--max-repair-rounds` 控制，默认 2 轮。
- 单个 Agent 失败不会直接打崩并行阶段，系统会尽量保留已有成果。
- 无 Key 或无 `zai` 包时，CLI 会直接失败并提示补齐 LLM 配置。
- 模型输出不合法时，该 Agent 会记录错误并进入报告，不再使用本地模板替代真实 LLM 输出。
