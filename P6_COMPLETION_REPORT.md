# P6 外部证据与双执行路径阶段报告

更新时间：2026-10-11

## 1. 阶段定义

P6 用于关闭 P0–P5 审计中仍依赖外部条件的证据缺口，包括六模板 Java 双执行路径、实物温度实验、固定任务人工与外部模型对照，以及目标 Windows 电脑迁移验收。本阶段把本机工程准备和外部投稿证据分为两个独立门，禁止使用模板行、仿真复制值或合成数据冒充外部测量。

## 2. 已完成的本机工作

### 2.1 六模板 Java 双路径

六个已经通过 MATLAB LiveLink 的代表模板均从其已验证 MPH 导出模板专用 Java 源码，使用 COMSOL 6.4 自带 Java 编译器编译，并由 `comsolbatch` 调用 COMSOL Java API 重建、运行第一个研究并保存新的 MPH。

| 模板 | Java 导出 | 编译 | 重建与求解 | 新 MPH 字节 | 执行时间 s |
|---|---:|---:|---:|---:|---:|
| 固体传热 | 通过 | 通过 | 通过 | 1,563,697 | 16.70 |
| 电流 | 通过 | 通过 | 通过 | 742,100 | 12.02 |
| 电热耦合 | 通过 | 通过 | 通过 | 1,795,649 | 16.00 |
| 固体力学 | 通过 | 通过 | 通过 | 2,030,011 | 14.83 |
| 流热耦合 | 通过 | 通过 | 通过 | 2,626,958 | 19.70 |
| 压力声学 | 通过 | 通过 | 通过 | 721,209 | 11.66 |

Java 双路径门为 6/6 通过。每个模板均重建 1 个组件、1 个研究和至少 1 个求解结果，并记录 Java 源码与新 MPH 的 SHA-256。

### 2.2 外部证据采集入口

- 温度实验继续使用已有的测量不确定度、COMSOL 与代理三方比较协议，最低要求 5 个独立真实测量工况。
- 新增固定 60 任务的三方法配对记录模板，覆盖人工 COMSOL、直接外部模型和本项目分阶段平台，共 180 行。
- 对照评估器只接受 `measured` 或 `valid` 记录，检查固定任务集合、方法覆盖、重复任务、布尔字段、运行标识、人工修改量、交互次数、完成时间和 false-safe。
- 当前电脑迁移预检已经重新运行，Python 3.12、依赖、MATLAB/COMSOL 路径、LiveLink、六模板 MATLAB 证据、Java 双路径、固定基准、网页入口和离线测试全部通过。
- 网页新增 `GET /api/p6/status`，分别显示本机准备状态和外部投稿证据状态。

## 3. 当前门状态

| 证据门 | 状态 | 原因 |
|---|---|---|
| Java 双路径 | 通过 | 6/6 导出、编译、重建和求解通过 |
| 当前电脑预检 | 通过 | 所有必需检查通过 |
| 证据采集资产 | 通过 | 配置、Schema、模板和评估器齐全 |
| 实物温度实验 | 等待 | 0/5 个真实测量工况 |
| 固定任务外部对照 | 等待 | 0/180 条真实观察记录 |
| 目标电脑验收 | 等待 | 尚未在另一台 Windows 电脑运行 |

因此，P6 **本机准备门通过**，但**外部投稿证据门尚未通过**。这不是软件执行失败，而是需要实验设备、人工参与、外部模型冻结运行和第二台电脑产生的新证据。

本轮全量自动化回归共运行 169 项，失败 0、错误 0、跳过 0；P5 与 P6 聚焦测试 13/13 通过。论文更新后由 Microsoft Word 导出为 21 页 PDF，并完成逐页视觉检查，未发现裁切、重叠、乱码或空白正文页。

## 4. 主要产物

- Java 双路径报告：`generated/p6/java_dual_path/java_dual_path_report.json`
- 六模板 Java 源码：`generated/p6/java_dual_path/*/*_backup.java`
- P1 更新后成熟度：`generated/p1/template_maturity.json`
- 固定任务对照配置：`configs/p6_external_evidence.json`
- 180 行对照模板：`examples/p6_fixed_task_baseline_template.csv`
- 对照评估器：`src/comsol_small_model/p6_baseline_evaluation.py`
- P6 状态：`generated/p6/p6_status.json`
- 当前电脑迁移预检：`generated/p2/migration_acceptance.json`

## 5. 关闭 P6 外部投稿门的实际步骤

1. 按温度实验模板录入至少 5 个独立测量工况及 95% 扩展不确定度，并运行三方验证。
2. 在冻结的 60 条任务上分别采集人工 COMSOL、直接外部模型和分阶段平台记录，共 180 条；不要修改任务文本或事后删除失败行。
3. 在另一台兼容 Windows 电脑执行 `run_p2_migration_acceptance.py --run-tests --host-role destination --output generated/p6/destination_migration_acceptance.json`，并完成一个最小实时模板求解。
4. 重新运行 P6 状态构建器。只有六个证据门全部通过时，`publication_external_gate_passed` 才会变为 `true`。
