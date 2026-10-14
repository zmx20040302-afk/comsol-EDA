param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $PSScriptRoot "start_windows_execution_node.ps1"
$pythonArgument = if ($Python) { " -Python `"$Python`"" } else { "" }
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"$pythonArgument"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "COMSOLModelCodex" -Action $action -Trigger $trigger -Description "Start COMSOL Model Codex and its local execution worker after Windows logon." -Force
Write-Output "Scheduled task COMSOLModelCodex installed. It starts after Windows logon."
