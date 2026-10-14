# Windows 发布与迁移验收

## 1. 环境要求

- Windows 10 或 Windows 11。
- 64 位 CPython 3.12。
- MATLAB R2023b Update 6；若使用其他版本，必须重新完成 LiveLink 兼容性求解。
- COMSOL Multiphysics 6.4 与所需物理模块。
- MATLAB LiveLink for COMSOL。

## 2. 重建 Python 环境

在项目目录执行：

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock-windows-py312.txt
```

不要复制旧电脑的虚拟环境目录。配置 `configs/execution_node.json` 中的 MATLAB、COMSOL、mphserver 和 LiveLink 路径。

## 3. 迁移前检查

```bat
.venv\Scripts\python.exe scripts\run_p2_migration_acceptance.py --run-tests
```

报告写入 `generated/p2/migration_acceptance.json`。所有 required 检查必须通过。

## 4. 一键启动

双击 `start_windows.bat`。启动器依次检查或启动 mphserver、单实例执行 Worker 和网页服务，并在健康检查通过后打开 `http://127.0.0.1:8880/`。

网页应显示：

1. 离线/API 模式切换。
2. 自动建模十阶段任务向导。
3. COMSOL 端口、Worker 和任务状态。
4. 二维结果图或可旋转三维预览。
5. 已保存任务恢复、失败阶段重提和任务包下载。

## 5. 目标电脑最小求解验收

1. 在网页点击“连接 COMSOL”，确认 `localhost:2036` 已连接。
2. 使用 `configs/one_dimensional_heat_conduction.json` 创建快速任务。
3. 审批执行后确认生成 MPH、CSV、PNG、执行日志和物理验证报告。
4. 确认最高温度位于 293.15–373.15 K。

历史 MPH 只能证明源电脑的执行结果。目标电脑必须重新完成本节的实时求解，才能通过迁移验收。

## 6. Linux 案例源

`/home/lab/zhangmx/案例下载/案例下载/` 必须通过 `configs/case_sources.json` 配置为以下一种方式：Windows 镜像目录、WSL 发行版，或 SSH 主机与本地缓存。未配置映射时，Windows 页面只能报告不可访问，不能直接读取 Linux 路径。
