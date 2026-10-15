# COMSOL 本地智能建模与仿真平台：智能建模工作台

这个目录提供一个本地可运行的小系统，用于：

- 阅读 COMSOL LiveLink for MATLAB 脚本 `.m`，提取参数、物理场、研究和结果设置。
- 用 JSON 描述建模限制和约束，生成新的 COMSOL LiveLink MATLAB 建模脚本。
- 读取 COMSOL 参数扫描导出的 CSV，训练一个小型代理模型，用输入参数预测仿真结果。
- 通过 MATLAB 辅助脚本读取 `.mph` 模型摘要。完整读取 `.mph` 需要 COMSOL + LiveLink/API。
- 通过本地网页或者 Windows 批处理脚本打开一个可操作界面。

项目主线已经调整为“从自然语言工程需求到可执行、可验证 COMSOL 模型”。总体路线位于 `EDA_PUBLICATION_ROADMAP.md`，逐项实施和验收计划位于 `AUTO_MODELING_IMPLEMENTATION_PLAN.md`。三维母排电热模型继续作为高完成度验证案例；代理模型和设计优化属于自动建模完成后的扩展能力。

## P0 自动建模基础

P0 已建立统一的建模任务合同和十阶段工作流：

1. 需求目标与完成标准。
2. 物理场、耦合和研究类型。
3. 几何与参数。
4. 材料与属性来源。
5. 边界条件和初始条件。
6. 网格和网格无关性计划。
7. 研究步骤和求解器。
8. 结果、派生量和物理验收规则。
9. 代码生成和静态审计。
10. COMSOL 执行、验证和受控修正。

建模合同 Schema 位于 `configs/modeling_contract.schema.json`，示例位于 `configs/modeling_contract.example.json`。合同记录几何、材料、物理接口、边界、单位、输出、验证规则、信息缺口、证据等级和自动执行风险。关键条件缺失时，平台会集中给出追问；`proposed` 建议不能直接绕过验证门进入自动求解。

需求完整性基准包含 30 个完整、缺失、冲突和单位不完整的任务，运行命令为：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_requirement_completeness_benchmark.py
```

P0 环境、资产、测试和历史 COMSOL 证据基线可通过 `scripts/build_auto_modeling_baseline.py` 重新生成，输出到 `generated/baselines/`。

## P2 评测与发布候选

P2 已把十阶段流程整合到网页任务向导。任务合同和当前阶段会写入 `generated/staged_workflows`，页面刷新或服务重启后可以从“已保存任务”恢复；验证失败的任务可以从失败阶段重提；当前工作流和已生成代码、审计与说明可下载为 ZIP 任务包。

固定端到端矩阵包含六领域 60 条需求：24 条完整需求、18 条信息不完整需求、12 条参数化或耦合需求和 6 条显式冲突需求。重新评测：

```powershell
.\.venv\Scripts\python.exe .\scripts\build_p2_task_matrix.py
.\.venv\Scripts\python.exe .\scripts\run_p2_end_to_end_benchmark.py
```

当前固定集的物理/耦合选择、研究类型、关键缺失召回与精确率均为 100%，36/36 可执行需求可进入模板代码生成，24 个应阻断任务的 false-safe 为 0。COMSOL 构建、网格、求解、导出和物理验证率引用六个代表模板的实机证据；该报告不会把证据复用表述为 60 次新求解。报告位于 `generated/p2/end_to_end_benchmark.json`。

发布与迁移入口：

```powershell
.\.venv\Scripts\python.exe .\scripts\run_p2_migration_acceptance.py --run-tests
.\.venv\Scripts\python.exe .\scripts\build_p2_release_package.py
```

发布包、清单和摘要位于 `generated/p2/release/`，详细步骤见 `RELEASE_MIGRATION_GUIDE.md`。在目标 Windows 电脑上仍需重新执行一个最小 COMSOL 模板，历史 MPH 不能替代目标机兼容性验收。

## DAC 2027 P3 前瞻多案例评测

DAC P3 已冻结独立多案例评测协议和统计管线。它等待 P0 收集的 24 条第三方盲测任务，并强制检查 8 个案例族与全部开发、验证和 P2 集合无重叠。Direct LLM 与 Retrieval LLM 各重复 3 次，Existing Selector 与 Contract Dependency v1.1 各运行 1 次，共需 192 条实测。报告包含任务共识、案例级结果、Wilson 区间、McNemar 检验、重复一致性和失败类型。

```powershell
.\.venv\Scripts\python.exe .\scripts\prepare_dac2027_p3.py
.\.venv\Scripts\python.exe .\scripts\freeze_dac2027_p3.py
# 外部任务通过 P0 校验后：
.\.venv\Scripts\python.exe .\scripts\prepare_dac2027_p3.py --seal
# 自动运行四方法、LLM 三次重复并断点保存：
.\.venv\Scripts\python.exe .\scripts\run_dac2027_p3.py --llm-workers 4
# 192 条实测完成后：
.\.venv\Scripts\python.exe .\scripts\evaluate_dac2027_p3.py
```

当前状态是“基础设施门通过、独立主结果门等待真实第三方数据”。模板、合成记录、项目自编任务和部分运行均不会计入主结果。主页面提供“检查并密封 P3”按钮；外部任务不齐时会拒绝密封并保留现有状态。详细状态见 `DAC2027_P3_STATUS.md`，第三方执行步骤见 `DAC2027_P3_EXTERNAL_CAMPAIGN_GUIDE.md`。

### DAC 2027 P4：双盲稿件与匿名复现包

DAC P4 已生成 5 页正文加 1 页参考文献的 Letter 双栏匿名稿件，并完成相关工作矩阵、AI 内容声明、投稿检查表、格式与双盲自动检查和匿名复现包。机器检查验证页面限制、Letter 尺寸、参考文献独立页、必需章节、空作者元数据、个人路径扫描，以及复现包内 24 个文件的 SHA-256。

P4 本机基础设施门已经通过。最终投稿门仍保持关闭，因为 P3 外部评测为 0/24 条任务和 0/192 条观测，且作者尚未核对最终主结果、引用、冲突、作者记录和 AI 声明。稿件位于 `paper_draft/dac2027_contract_guided_comsol_submission.pdf`，状态见 `DAC2027_P4_STATUS.md`，匿名复现包位于 `generated/dac2027/p4/reproducibility/dac2027_p4_anonymous_reproducibility.zip`。

P4 稿件生成器会验证 P3 报告的发布标志、24 条任务、8 个案例族、192 条观测及 SHA-256，全部通过后才自动写入外部结果表。网页中的“检查最终化条件”会运行 `scripts/finalize_dac2027_p4.py`；当前证据不足时明确阻塞，证据齐全后生成绑定最终 PDF 与 P3 报告哈希的作者批准模板。只有六项人工核对全部完成，最终投稿门才会通过。

## P3 固定电流母排设计优化

P3 把母排案例改为 160 A 固定端电流比较，定义长度、宽度、厚度、孔半径、电流、换热系数和环境温度七个变量，并完成 80 个初始设计、5 个候选复核、60 个封存域内测试和 20 个封存域外测试的真实 COMSOL 求解。3 个复核方案形成真实 Pareto 集；结果位于 `generated/p3/pareto_verification/verified_pareto.csv`。

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
.\.venv\Scripts\python.exe .\scripts\build_p3_design_package.py
.\.venv\Scripts\python.exe .\scripts\run_p3_current_drive_baseline.py
.\.venv\Scripts\python.exe .\scripts\run_p3_initial_design.py
.\.venv\Scripts\python.exe .\scripts\run_p3_surrogate_optimization.py
.\.venv\Scripts\python.exe .\scripts\run_p3_pareto_verification.py
.\.venv\Scripts\python.exe .\scripts\run_p3_final_evaluation.py
```

最终独立评估完整执行通过，但代理模型发布门未通过：温度 RMSE 为 31.531 K，功率 RMSE 为 0.881 W。声明参数边界的域外检测 AUROC 为 1.000；保守 95% 约束门拒绝所有代理发布，因此网页只显示真实 COMSOL 验证方案，不开放该七变量代理的直接预测。已经解封的最终集不得用于调参后再次充当独立证据。

运行 `.\.venv\Scripts\python.exe .\scripts\build_p3_release_package.py` 可生成 `generated/p3/release/comsol_auto_modeling_p3_release.zip`。ZIP 包含源码、紧凑 CSV/JSON 证据、冻结代理、论文和 SHA-256 清单；大体积 MPH 文件保留在本地 `generated/p3/`，不放入迁移包。

## P4 自适应代理修复

P4 将已经解封的 P3 域内最终集降级为诊断训练数据，并加入物理特征、逐输出模型选择和四轮自适应补样。每轮选择 20 个高不确定度、约束邻近且保持空间分散的候选，共新增 80 个真实 COMSOL 结果；最终训练集包含 220 行。

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
.\.venv\Scripts\python.exe .\scripts\benchmark_p4_candidate_models.py
.\.venv\Scripts\python.exe .\scripts\run_p4_adaptive_training.py
.\.venv\Scripts\python.exe .\scripts\run_p4_final_evaluation.py
```

全新封存终评的 60 个域内与 20 个域外工况全部完成。最高温度 RMSE 降至 8.925 K，功率 RMSE 降至 0.338 W，域外 AUROC 为 1.000，保守门控 false-safe 为 0。五个输出的区间覆盖达到预设门槛，但对称 95% 区间较宽，只安全放行 2/60 个域内点，3.33% 低于预先规定的 10%。因此网页显示“预测精度通过、代理发布未通过”，直接预测仍关闭。完整结论见 `P4_COMPLETION_REPORT.md`。

## P5 单侧安全校准与受控发布

P5 保持 P4 回归模型不变，将不适合上限约束的对称区间替换为局部缩放单侧 95% 上界。P4 已开封最终集只用于在两个预定义候选中选方法；选中的 `normalized_one_sided` 方法、模型、门槛和 SHA-256 冻结后，才生成另一套 60+20 封存最终集。

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
.\.venv\Scripts\python.exe .\scripts\prepare_p5_calibration.py
.\.venv\Scripts\python.exe .\scripts\run_p5_final_evaluation.py
```

P5 的 80/80 个新工况全部完成。最高温度 RMSE 为 11.807 K，三个约束上界覆盖率为 95%–100%，域外 AUROC 为 1.000。保守门安全放行 10/60 个域内点，覆盖率 16.67%，没有 false-safe，全部预声明发布门槛通过。发布只适用于配置文件声明的七变量域和固定物理假设；域外输入继续拒绝并要求 COMSOL。完整结论见 `P5_COMPLETION_REPORT.md`。

运行以下命令生成经过哈希校验的 P5 发布包：

```powershell
.\.venv\Scripts\python.exe .\scripts\build_p5_release_package.py
```

发布包位于 `generated/p5/release/comsol_auto_modeling_p5_release.zip`。包内包含 P0–P5 源码、紧凑验证证据、冻结代理模型、论文和 SHA-256 清单；大体积 MPH 和临时日志保留在本机，不写入迁移包。

## 快速启动网页

双击：

```text
start_windows.bat
```

启动脚本会检查或复用 `mphserver` 和本地执行 Worker，启动网页并打开 `http://127.0.0.1:8880/`，同时检查或启动 DAC P0 第三方盲测采集页 `http://127.0.0.1:8891/`。案例阅读、知识库检索和已验证代理模型预测仍可在 COMSOL 暂时不可用时运行；需要真实求解、参数扫描或 LiveLink 预览时，页面会明确显示端口和 Worker 状态。

截至 2026-10-08，本机网页、执行 Worker、COMSOL 6.4 与 MATLAB R2023b Update 6 已通过真实闭环复测。兼容性测试完成了 LiveLink 连接、二维模型构建、网格、稳态求解、结果提取和 CSV 导出；随后任务队列又完成了一维导热模型的脚本生成、COMSOL 求解、MPH 保存、CSV 导出和结果校验。证据保存在 `generated/compatibility/matlab_r2023b_comsol_6_4_full_solve.json` 和对应执行任务目录。项目内的 `runtime/python312` 是独立 Python 3.12.10；当前 `.venv` 已用它重建，不再依赖 Codex 缓存。

启动器会先复用已经健康的 8880 服务；需要冷启动时，每 5 秒打印一次等待进度，并等待最多 90 秒。只有 `/api/health` 实际返回成功后才会打开浏览器并显示 `ready=true`。网页启动失败时，窗口会保留错误信息，同时给出 `generated/training_runs/web_startup.log` 的位置。scikit-learn、SciPy 等训练依赖不再阻断网页和模型观测窗启动；它们只在执行代理模型训练时使用。

Windows 启动脚本会先检查或启动 COMSOL mphserver，再启动执行 Worker 和网页服务，保证左侧观测窗可以直接使用已有模型的 LiveLink 预览导出。冷启动时会给 Worker 最多 30 秒完成 pandas 与 scikit-learn 初始化，避免节点稍后上线却被启动器误报为离线。真实 COMSOL 求解已在 `configs/execution_node.json` 中开放，但任务仍必须通过建模完整性或人工审查门槛；MATLAB 超时会终止其进程树，单实例 Worker 锁会阻止并发占用。任务进程日志位于 `generated/execution_jobs/worker_startup.log`。

已验证代理模型只能在各自模型卡声明的几何、材料、边界条件和输入范围内作快速比较。每次受控预测同时返回训练域位置、距最近训练样本的归一化距离、由独立留出误差校准的 95% 预测区间和高/中/低可信度。超出范围时，网页会拒绝外推；低可信度结果会明确要求补充真实 COMSOL 参数扫描。

## 离线模式与 AI API 模式

项目当前状态、尚未完成的研究证据和发布前任务记录在 `PROJECT_READINESS.md`，后续完善应按其中的验收条件逐项关闭。

网页顶部可以在“离线模式”和“API 模式”之间切换，并选择 `本机 Codex（免密钥）`、`Codex / OpenAI` 或 `DeepSeek`：

- 离线模式沿用本地案例记忆、规则、代理模型和任务执行功能，不向外部 AI 服务发送内容。
- API 模式把对话框中的任务发送给当前选定的远程模型，用于生成补充方案和完善建议。
- 首次启动默认使用本机已经登录的 Codex 及其默认 GPT，不要求另外填写 API 密钥。该通道使用临时、只读 Codex 会话，不允许模型修改项目文件。
- 自动建模指令始终先进入本地分步建模与人工确认流程，再考虑普通 API 对话；远程助手只能给出建议，不能把模型标记为“已求解”或“已验证”。
- 本地工具执行失败后，页面会显示“交给 API 完善”按钮。只有手动点击，或用户主动勾选“本地任务失败时自动交给当前 API 分析”，才会发送脱敏后的失败摘要。
- `start_windows.bat` 和 `start_local_8880.bat` 会同时检查并启动本地执行 worker，避免网页可打开但任务节点仍离线。

点击右上角“AI 接入设置”，可以修改提供方、API 地址、模型名称、推理强度、超时和密钥。默认配置使用 OpenAI Responses API 与 DeepSeek Chat Completions API。API 密钥保存在 `generated/local_secrets/api_assistant_keys.json`；该目录已加入 `.gitignore`，读取配置的接口只返回“是否已配置”，不会返回密钥正文，工作日志也会再次执行字段脱敏。

默认本机 Codex 的使用步骤：

1. 保持顶部“API 模式”和“本机 Codex（免密钥）”，直接在对话框输入任务。
2. 如需改用独立 OpenAI 或 DeepSeek 接口，再打开“AI 接入设置”并填写对应密钥。
3. 如需失败任务自动补充，单独勾选自动转交；该选项默认关闭。

远程 AI 只返回建议文本，不能直接修改本机文件或声称已经执行 COMSOL。需要改动文件或运行任务时，应根据建议回到本地工具执行并验证。

## COMSOL 模型观测窗

COMSOL 观测窗固定嵌入左侧栏导航下方，会显示执行节点配置中的 mphserver 地址和连接状态，并列出 `generated/execution_jobs`、`generated/benchmarks` 与 `generated/staged_workflows/final_code` 中最近生成的 MPH 文件。点击端口状态卡会自动连接已有的 mphserver；端口未启动时，系统会按 `configs/execution_node.json` 的设置启动 COMSOL mphserver，再检测 `localhost:2036`。左侧栏在桌面布局下宽 400px，模型列表与预览每 5 秒自动刷新，中间区域继续用于对话和建模。

选择一个 MPH 后点击“从 COMSOL 导出预览”，后端会通过 MATLAB LiveLink 连接 mphserver、打开该模型并导出第一个可用结果图；模型没有可导出的结果图时改为导出几何图。生成的 `<模型名>_preview.png` 会保存在 MPH 同目录并自动显示在左侧预览窗。该入口只进行读取和图片导出，由 `allow_preview_export` 单独控制，不会开启完整建模与求解任务。

MATLAB 执行包装器在保存 `<模型名>.mph` 后，会尝试导出 `<模型名>_preview.png`。它优先导出第一个 COMSOL 结果图；如果结果图导出失败，则用 `mphgeom` 导出几何图。预览失败不会使已经完成的模型求解失败。历史 MPH 没有对应 PNG 时，观测窗只显示模型文件信息。

已验证的本地模板包括固体传热、电流、电热、固体力学、二维流热和压力声学；2026-10-10 的六类统一实机验收报告位于 `generated/p1/template_maturity.json`。模板执行结果会保存为独立的 MPH 文件，并写入案例记忆库供后续中文建模需求检索。

候选案例评分和 CSV 扫描规划只会把已明确支持的单物理场，以及明确的电流-传热组合列为自动扫描候选。磁场、静电、粒子追踪、半导体、等离子体和其他复杂耦合案例必须先声明具体输出表达式并人工复核，不能根据案例名称猜测训练列。

任务中心中的“匹配已验证模板”可根据中英文需求优先选择可靠模板、提示必要参数，并自动进入 COMSOL 执行队列。

## Linux 案例源

案例阅读默认识别 `/home/lab/zhangmx/案例下载/案例下载/`。服务运行在该 Linux 主机时可以直接读取；服务运行在 Windows 时，在 `configs/case_sources.json` 中为该来源填写以下任一项：

- `windows_mirror`：已经同步到 Windows 的目录。
- `wsl_distribution`：包含该目录的 WSL 发行版名称。
- `ssh_host` 和 `cache_dir`：远程主机及同步后的本地缓存目录。

网页“检测案例源”会显示实际解析路径或缺失配置。当前项目不会把不可访问的 Linux 路径误当成本机 Windows 路径，也不会在缺少主机地址时伪造已读取状态。

或者在 PowerShell 中运行：

```powershell
# 在 comsol_training_small_model 目录中运行
.\.venv\Scripts\python.exe web_app.py --open
```

默认地址：

```text
http://127.0.0.1:8765
```

## 局域网联网运行

如果希望同一局域网内的其他电脑访问这个小模型，双击：

```text
start_network.bat
```

或手动运行：

```powershell
# 在 comsol_training_small_model 目录中运行
.\.venv\Scripts\python.exe web_app.py --lan --port 8765
```

启动后终端会打印可访问地址，例如：

```text
http://192.168.x.x:8765/?token=自动生成的访问令牌
```

其他设备需要和本机处于同一局域网，并在浏览器中访问启动器打印的**完整地址**。访问令牌会保存在
`generated/local_secrets/lan_access_token.txt` 并自动复用，不需要每次重新配置；该目录已被 Git 忽略。
如果 Windows 防火墙提示，请只允许 Python 在“专用网络/Private network”中通信。

安全提醒：局域网模式已启用令牌鉴权，但仍应只在可信网络中使用，并妥善保管完整访问地址。公网访问还需要 HTTPS 反向代理或受管隧道，不能直接做路由器端口映射。

网页中可以完成：

- 使用类似 Codex 的对话界面输入需求，系统会在消息流中返回反馈。
- 输入自然语言指令，获得建模、约束、读取或训练建议。
- 输入文件路径阅读文件，或在浏览器中选择文件读取文本内容。
- 读取 MATLAB `.m` 建模文件。
- 载入和修改约束 JSON。
- 校验约束是否满足模板要求。
- 生成 COMSOL LiveLink `.m` 建模脚本。
- 在安装训练依赖后训练本地代理模型。

## 语言指令与文件阅读

网页左侧的“语言指令”区域可以输入类似：

```text
请读取这个 MATLAB 文件，判断是否能作为 COMSOL 自动建模模板。
```

```text
根据这个 CSV 训练一个代理模型，用 k Q h L 预测 Tmax Tavg。
```

```text
读取 mph 文件并说明如何转成可训练数据。
```

“文件输入”区域支持两种方式：

- 填写一个或多个本地路径；多个路径时每行一个，也可以用英文分号 `;` 分隔。
- 点击“选择文件”，直接从浏览器选择 `.m`、`.csv`、`.json`、`.txt` 等文本文件；支持一次多选。

支持的读取反馈：

- `.m`：识别 COMSOL LiveLink 参数、物理场、研究类型和结果图组。
- `.java`：识别 COMSOL Java 导出代码中的参数、物理场、研究、结果、网格和材料线索。
- `.pdf`：识别 COMSOL 对应说明文档；安装依赖后，路径读取和浏览器二进制上传都会提取最多 50 页、约 5 万字符用于学习摘要。
- `.csv`：识别列名、行数和样例行，可用于训练代理模型。
- `.json`：识别 JSON 是否有效和顶层键，可作为约束配置或模型摘要。
- `.mph`：提示使用 COMSOL with MATLAB 的 `export_mph_summary.m` 导出摘要。

同时读取多个文件时，系统会生成一个文件集合摘要，统计 MATLAB、CSV、JSON、MPH 等文件数量，并把集合摘要带入对话反馈。例如可以同时读取：

```text
../acoustic_rectangular_cavity/build_acoustic_rectangular_cavity.m
examples/sample_comsol_data.csv
configs/thermal_constraints.json
```

点击“学习总结”后，系统会把 `.mph`、`.pdf`、`.m`、`.java`、`.csv`、`.json` 按用途分组：

- COMSOL 模型文件
- MATLAB 建模脚本
- Java 导出代码
- PDF 学习文档
- CSV 训练数据
- JSON 约束或元数据

并给出推荐实现路径：提取物理场、参数、几何、边界条件、网格、求解器和输出结果，然后校验约束、生成 LiveLink 脚本、运行 COMSOL 参数扫描、训练代理模型。

学习总结默认会写入 `generated/case_memory/case_memory.json`，并记录质量分与缺失证据。案例检索会优先使用物理场、几何、边界和来源证据更完整的条目。

分步工作流在退回某一步时会按审批意见重新生成该步方案并保留修订历史；完成审批后会输出 MATLAB、Java、理论指导和代码验证报告。验证报告中的 `ready_to_solve=false` 表示仍需在 COMSOL 中核对选择集或物理参数，不能把脚手架当成已求解模型。

新版页面布局：

- 左侧：会话入口和当前工作状态。
- 中间：对话消息流和底部输入框。
- 右侧：文件、MATLAB、约束、训练和原始响应工具区。

## 安装训练依赖

网页的 MATLAB 读取、约束校验、脚本生成不需要额外依赖。训练模型需要：

```powershell
# 在 comsol_training_small_model 目录中运行
..\runtime\python312\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`scikit-learn` 用于小模型训练；没有 GPU 也可以运行。

### 可复现环境与性能报告

当前 Windows Python 3.12 环境的精确版本保存在：

```text
requirements-lock-windows-py312.txt
```

在新的 Python 3.12 虚拟环境中重建时使用：

```powershell
python -m pip install -r requirements-lock-windows-py312.txt
```

本项目已经在全新临时虚拟环境中执行过该重建，并验证核心科学计算包可以导入。验证证据位于 `generated/environment/locked_environment_rebuild_smoke.json`。

运行代理模型性能基准：

```powershell
.\.venv\Scripts\python.exe .\scripts\benchmark_runtime.py --iterations 300 --http-iterations 60
```

当前本机结果为：直接预测中位数 3.651 ms、95 分位数 4.287 ms；本地 HTTP 预测中位数 29.890 ms、95 分位数 35.233 ms。三次队列等价 MATLAB LiveLink/COMSOL 求解耗时为 18.744、18.113 和 24.968 s，中位数为 18.744 s，三次最高温度均为 373.15 K。以该中位数计算，直接调用和 HTTP 调用的本机参考加速比分别约为 5134 倍和 627 倍。详细报告位于 `generated/benchmarks/runtime_performance_20261009.json` 和 `generated/benchmarks/comsol_repeat_20261009/repeated_comsol_performance.json`。这些结果只适用于当前电脑和固定案例。

重复运行 COMSOL 性能基准：

```powershell
.\.venv\Scripts\python.exe .\scripts\benchmark_comsol_repeated.py --runs 3
```

该脚本为每一轮保留独立 MPH、CSV 与日志，同时监控 MATLAB 进程树和持久运行的 `comsolmphserver.exe` 进程树。每轮开始前记录 mphserver 空闲基线，再报告 MATLAB、mphserver、二者同时峰值和相对基线增量。当前三轮中的 MATLAB 峰值工作集为 1808.293 MB，mphserver 峰值工作集为 1011.703 MB，二者同时峰值工作集为 2803.402 MB；二者同时峰值私有内存为 3056.199 MB。首轮服务器从冷基线加载模型，工作集增加 942.652 MB，后续暖态增量明显较小。操作系统其他进程未计入这些数值。

运行三维母排多物理场完整验证扫描：

```powershell
.\.venv\Scripts\python.exe .\scripts\benchmark_busbar_multiphysics_sweep.py
```

该脚本重新打开 17.3 MB 的三维母排 MPH，在“电流 + 固体传热 + 焦耳热耦合”模型中求解 3 个电压与 3 个对流换热系数的全部 9 个组合。当前实测整轮墙钟时间为 51.591 s，9 次求解时间中位数为 3.254 s、95 分位数为 3.901 s；所有工况均满足响应趋势检查，最大能量不平衡为 0.04731%。MATLAB 与 mphserver 同时峰值工作集为 3799.953 MB，同时峰值私有内存为 5017.969 MB。报告、逐工况 CSV、日志和末工况 MPH 保存在 `generated/benchmarks/busbar_multiphysics_sweep_20261009/`。这些数值只描述当前电脑上的固定几何、网格、边界与稳态求解器。

使用相同监测口径重算完整 49 工况密集训练网格：

```powershell
.\.venv\Scripts\python.exe .\scripts\benchmark_busbar_multiphysics_sweep.py --grid dense49
```

49/49 工况已通过，整轮墙钟时间为 188.039 s，单工况求解中位数为 3.048 s、95 分位数为 3.425 s。MATLAB 与 mphserver 同时峰值工作集为 3871.012 MB，同时峰值私有内存为 4915.918 MB。新结果与历史训练 CSV 的 49 个输入组合全部匹配，`Tmax` 最大绝对差异为 0.000363 K，最大能量不平衡差异为 `8.48e-10` 个百分点。报告保存在 `generated/benchmarks/busbar_dense_multiphysics_sweep_20261009/busbar_dense_multiphysics_sweep_benchmark.json`。

生成带 SHA-256 的论文与代码发布快照：

```powershell
.\.venv\Scripts\python.exe .\scripts\build_release_snapshot.py
```

快照输出到 `generated/release_snapshots/release_snapshot_20261009.json`，不包含 API 密钥和本机认证状态。

## 命令行用法

### 0. 扫描 COMSOL 官方 PDF 文档并生成知识底座

如果本机安装了 COMSOL 官方 PDF 文档，可以扫描：

```powershell
python -m src.comsol_small_model.cli scan-comsol-docs --root D:\COMSOL64\Multiphysics\doc\pdf --output-dir generated
```

会生成：

```text
generated/comsol_pdf_catalog.json
generated/comsol_modeling_logic.md
```

其中：

- `comsol_pdf_catalog.json`：记录模块目录、PDF 文件、文档角色、模块领域归类。
- `comsol_modeling_logic.md`：总结 COMSOL 建模底层逻辑，包括问题定义、几何、材料、物理场、边界条件、网格、研究求解、结果验证、代理模型训练。

这两个文件是小模型理解 COMSOL 的底层知识底座。它们不会一次全文解析所有 PDF，而是先建立模块目录、文档角色和建模逻辑框架；需要深入某个模块时，再读取对应 PDF 内容。

### 0.1. 总结一个 COMSOL 案例并补充到案例知识库

```powershell
python -m src.comsol_small_model.cli summarize-case "D:\桌面\codex\案例下载\COMSOL\母线板装配几何系列教程" --title busbar_assembly_geometry --output-dir generated\case_knowledge
```

会生成：

```text
generated/case_knowledge/busbar_assembly_geometry.case.json
generated/case_knowledge/busbar_assembly_geometry.case.md
generated/case_knowledge/case_knowledge_index.json
```

案例卡片会记录：

- 文件组成：PDF、MATLAB、Java、MPH、CSV、JSON、TXT
- 训练阶段判断：是否已有 CSV，是否可开始代理模型训练
- 提取到的参数、默认值、单位和说明
- 对案例的建模思考
- 缺口：例如缺少参数扫描 CSV、MPH 需要 LiveLink 摘要
- 实现路径：从案例阅读到约束、脚本、参数扫描和训练

### 1. 阅读 MATLAB 建模文件

```powershell
python -m src.comsol_small_model.cli inspect-matlab ..\acoustic_rectangular_cavity\build_acoustic_rectangular_cavity.m
```

输出包括：

- `model.param.set(...)` 参数
- `physics.create(...)` 物理场接口
- `study(...).create(...)` 研究类型
- `result.create(...)` 结果图组

### 2. 校验建模约束

```powershell
python -m src.comsol_small_model.cli validate configs\thermal_constraints.json
```

约束文件描述：

- 几何尺寸范围
- 材料参数范围
- 边界条件范围
- 网格尺寸范围
- 扫描参数范围
- 输出结果表达式

### 3. 根据约束生成 COMSOL LiveLink 脚本

```powershell
python -m src.comsol_small_model.cli generate-matlab configs\thermal_constraints.json generated_build_thermal.m
```

生成的 `.m` 文件需要在 COMSOL with MATLAB 环境中运行。

### 4. 训练小型代理模型

```powershell
python -m src.comsol_small_model.cli train examples\sample_comsol_data.csv model.joblib --inputs k Q h L --outputs Tmax Tavg
```

模型会保存为 `model.joblib`，并输出训练误差和测试误差。

训练器当前使用 `scikit-learn` 的 `MLPRegressor`，流程是：

```text
读取 CSV
检查输入/输出列
检查 NaN/inf
划分训练集和测试集
标准化输入 X
标准化输出 y
训练 MLP
反标准化预测结果
输出 RMSE、MAE、R2 和警告
保存 joblib 模型
```

性能注意点：

- 示例数据只有 15 行，只适合验证流程，不适合得到可靠工程模型。
- 小数据会自动使用较小网络 `(32, 32)`，避免过度复杂。
- 100 行以上数据会使用更大的默认网络 `(64, 64)`。
- 50 行以上启用 early stopping，减少过拟合。
- 如果输出不标准化，MLP 对 300K 量级温度会收敛很差；当前版本已经同时标准化 X 和 y。
- 如果报告中出现 `Dataset has only ... rows`，说明需要更多 COMSOL 参数扫描数据。

### 5. 用模型预测

```powershell
python -m src.comsol_small_model.cli predict model.joblib --inputs 16 80 35 0.045
```

### 6. 独立 COMSOL 留出集与模型发布门槛

网页“训练”区域中的“独立 COMSOL 验证训练”用于通用物理场数据集。它要求提供两份互不重叠的 CSV：训练扫描数据和未参与训练的新 COMSOL 留出集；再填写物理适用范围与最大相对误差阈值。

系统会用留出集选择候选代理模型，生成验证报告和模型卡，并登记到 `generated/surrogate_registry.json`：

- `validated_for_declared_scope`：独立 COMSOL 留出集满足用户填写的阈值，只能在模型卡声明的物理范围内快速比较。
- `needs_more_comsol_evidence`：未通过阈值、输出存在零值或证据不足，必须补充 COMSOL 数据或改用绝对误差判据。

该状态不是实验验证、规范认证或最终工程放行。几何、材料、边界、研究类型或输入范围发生变化时，仍须回到 COMSOL 重新求解。

通过状态的模型可在网页“查看已验证模型”中获取模型 ID，并使用“受控代理预测”输入与模型输入列一致的 JSON 对象。系统会再次检查注册状态和训练范围；未通过验证、缺少输入或输入越界时不会输出代理结果。

对已验证模型的越界输入，可使用“生成补充 COMSOL 工况”。它会写入 `generated/augmentation_plans`，给出需要由同一物理范围 COMSOL 模板求解的补充样本；补样后仍须使用新的、未参与重训的 COMSOL 留出集重新验证。

二维稳态传热模型在 2026-10-08 完成了扩展验证闭环：第一批 18 个边界、中心、高温和空间填充工况发现旧模型 `Tmax` 最大误差为 5.861 K，超过 5 K 门槛；这些点随后转入训练集。重新训练后的模型使用第二批 18 个未参与训练、与训练条件零重叠的 COMSOL 工况验证，最终 `Tmax` 最大绝对误差为 0.184 K，`Tavg` 为 2.744 K。最终模型、模型卡和验证报告位于：

```text
generated/execution_jobs/expanded_validation_20261008/
generated/validation/thermal_plate_final/
```

独立验证设计可重复生成：

```powershell
python scripts\build_independent_holdout.py --count 18 --seed 20261008
```

预测响应新增以下字段：

- `input_domain`：逐参数范围检查、边界距离以及可用时距最近训练样本的归一化距离。
- `uncertainty.intervals`：按输出给出 95% 预测区间，优先使用独立 COMSOL 留出残差的经验 95 分位数校准。
- `confidence`：输出高、中、低等级、0–100 分、降级原因和是否必须回到 COMSOL。

区间描述的是代理模型相对于同一 COMSOL 物理范围的数值不确定性，不代表实验测量误差，也不能替代最终工程复核。

### 7. 导入真实温度实验并做三方验证

项目已提供可执行的“实验测量—COMSOL—代理模型”三方对比流程。先复制
`examples/experimental_temperature_measurements_template.csv`，将真实记录的
`record_status` 改为 `measured`，填写输入工况、测得的 `Tmax_K`/`Tavg_K`、各自的
95% 扩展测量不确定度 `measurement_u95_*`，以及同工况的 COMSOL 结果。

```powershell
python -m src.comsol_small_model.cli validate-temperature-experiment `
  examples\experimental_temperature_measurements_template.csv `
  generated\execution_jobs\expanded_validation_20261008\thermal_plate_surrogate_expanded_validated.joblib `
  --config configs\experimental_temperature_validation.json `
  --output generated\experimental_validation\temperature_validation_report.json
```

判定规则和最少样本数位于 `configs/experimental_temperature_validation.json`；CSV
字段契约位于 `configs/experimental_temperature_measurements.schema.json`。每条记录会输出：

- 实验与 COMSOL 的偏差、绝对误差和通过状态；
- 实验与代理模型的偏差、绝对误差和通过状态；
- 实验 95% 区间是否与代理 95% 预测区间重叠；
- 输入是否仍处于代理模型验证域，以及代理可信度；
- 汇总偏差、MAE、RMSE、最大绝对误差和通过率。

模板没有真实测量时，报告固定为 `awaiting_measurements` 和 `passed=false`。网页可通过
`GET /api/experimental-validation/status` 读取状态，通过
`POST /api/experimental-validation/run` 传入项目内的 `csv_path` 重新执行验证；
`/api/health` 也会返回 `experimental_validation` 摘要。

### 8. 审计已注册代理模型

每次新增、重训或迁移代理模型包后，运行统一的运行时审计：

```powershell
python scripts\audit_registered_surrogate_runtime.py --simulate-relocation
```

审计会检查注册表中的模型、模型卡和独立验证报告是否存在，只对 `validated_for_declared_scope` 模型执行范围中点预测，并核对预测输出列。`--simulate-relocation` 还会在临时目录中模拟原绝对路径和训练 CSV 失效，验证复制后的模型包能否离线使用。报告写入：

```text
generated/models/surrogate_runtime_audit.json
```

命令退出码为 `0` 表示所有已验证模型均可预测、验证证据完整且迁移模拟通过。报告同时保存注册表 SHA-256 指纹；健康接口 `/api/health` 的 `surrogate_runtime` 字段会读取最近一次报告，不会在每次页面刷新时重新加载全部模型。注册表在审计后发生变化时，接口会返回 `state=stale`，直到重新运行审计。

`NumPy 2.5` 与 `joblib 1.5.x` 组合会在读取数组时产生重复的 `DeprecationWarning`。运行时只精确过滤这条已知的 joblib shape 提示，审计则在 `compatibility_notices` 中保留环境风险；其他模型与 sklearn 警告仍会正常记录。新部署环境通过 `requirements.txt` 使用 `NumPy <2.5`，当前环境可继续运行，无须改写已验证模型。

当后续已验证模型明确替代早期训练尝试时，应保留旧模型的原验证状态和证据，并登记模型谱系：

```powershell
python scripts\mark_surrogates_superseded.py <replacement_id> <old_model_id> --reason "替代依据"
python scripts\audit_registered_surrogate_runtime.py --simulate-relocation
```

替代模型必须已经通过独立 COMSOL 验证。该操作不会删除旧模型；闭环审计会把它归入历史替代模型，不再算作活动证据缺口。

正式注册表统一为 `generated/models/surrogate_registry.json`。旧版本创建的 `generated/surrogate_registry.json` 仅作为只读兼容来源；新训练不会再写入旧路径。如果旧注册表包含正式注册表没有或内容冲突的模型，`/api/health` 会返回 `surrogate_runtime.state=registry_split`，需要先核对并合并，不能让旧副本覆盖正式记录。

可先执行安全预检，再合并 legacy 独有且无冲突的条目：

```powershell
python scripts\consolidate_surrogate_registries.py --dry-run
python scripts\consolidate_surrogate_registries.py
python scripts\audit_registered_surrogate_runtime.py --simulate-relocation
```

同 ID 内容不一致时，合并命令会返回非零退出码且不修改正式注册表。网页完成一次独立 COMSOL 验证训练并注册模型后，会自动重新执行带迁移模拟的运行时审计，健康状态无需人工刷新报告。

### 9. P6 外部证据与 Java 双路径

P6 已完成六个代表模板的 Java 导出、编译、COMSOL Java API 重建与求解。运行或复核命令：

```powershell
.\.venv\Scripts\python.exe scripts\run_p6_java_dual_path.py --reuse-export
.\.venv\Scripts\python.exe scripts\prepare_p6_external_evidence.py
.\.venv\Scripts\python.exe scripts\build_p6_status.py
```

状态接口为 `GET /api/p6/status`。本机准备门与外部投稿证据门独立显示；实验模板、人工/外部模型模板或合成行不会被计为已完成证据。详细范围见 `P6_COMPLETION_REPORT.md`。

### 10. P7 多 EDA 案例与可扩展性验证

P7 用冻结的统一证据合同复核母排电热设计、MEMS 热微执行器、电阻 FEM 场路耦合和功率电感器频域响应四个主案例，并把三维电容器静电响应作为扩展案例。审计同时检查原始文件、SHA-256、样本数、输入列、训练/保留集无重叠和各案例验证门限。

```powershell
.\.venv\Scripts\python.exe scripts\run_p7_eda_multicase_benchmark.py
```

状态接口为 `GET /api/p7/status`。当前结果为主案例 4/4、扩展案例 1/1、四类物理任务通过。报告明确区分当前项目新 COMSOL 闭环和历史独立 COMSOL 保留集，不把历史证据表述为本次重新求解。详细范围见 `P7_COMPLETION_REPORT.md`。

### 11. DAC 问题一 物理依赖图开发实验

平台新增目标驱动的物理依赖编译原型。它根据用户要求的输出量反推必要物理接口和耦合，并保留依赖边、证据、冲突和阻断原因。运行开发集比较：

依赖计划已接入建模任务合同和物理选择阶段。合同中的 `decision_support.physics_dependency_graph` 保存完整决策轨迹，界面阶段摘要显示由输出目标补全的接口及阻断原因。

```powershell
.\.venv\Scripts\python.exe scripts\run_dac_problem1_development_benchmark.py
.\.venv\Scripts\python.exe -m unittest tests.test_dac_problem1 -v
```

当前 18 条开发任务上，关键词基线、现有选择器和依赖图方法的物理接口与耦合完全匹配率分别为 61.11%、55.56% 和 100%。该数据集明确标记为 `development_only`，不能用于独立最终泛化声明。研究定义见 `DAC_PROBLEM1_RESEARCH_DEFINITION.md`，五项投稿问题见 `DAC_FIVE_PROBLEM_TRACKER.md`。

## 读取 `.mph` 的现实限制

`.mph` 是 COMSOL 专有模型文件。Python 可以做文件级记录，但不能可靠还原完整模型树。要读取 `.mph` 的参数、组件、物理场和研究，推荐在 COMSOL with MATLAB 中运行：

```matlab
summary = export_mph_summary('your_model.mph', 'your_model_summary.json');
```

脚本位置：

```text
matlab/export_mph_summary.m
```

## Portable Reference Workchains

Saved physics-reference reports can be passed to other local tools without the web UI. A package copies the selected reports into its own `reports/` folder and writes a relative-path `manifest.json`.

```powershell
python -m src.comsol_small_model.cli list-reference-reports --output-dir generated\reference_reports
python -m src.comsol_small_model.cli package-reference-reports generated\reference_reports\reference_example.json --output-dir generated\workchain_packages --title pipe-validation
python -m src.comsol_small_model.cli validate-workchain generated\workchain_packages\workchain_<id>\manifest.json
python -m src.comsol_small_model.cli archive-workchain generated\workchain_packages\workchain_<id>\manifest.json --output-dir generated\workchain_archives
python -m src.comsol_small_model.cli validate-workchain-archive generated\workchain_archives\workchain_<id>.zip
```

Package validation checks file presence, report schemas, and report IDs. It validates traceability only; it does not certify a COMSOL model or engineering result.

这条路线最稳：Python 负责网页、训练、约束和自动化组织；COMSOL/MATLAB 负责真正创建、读取和求解模型。
