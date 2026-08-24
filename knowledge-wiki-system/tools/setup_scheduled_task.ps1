# 创建飞书知识库每日同步定时任务
# 用法：右键 → 使用 PowerShell 运行，或在终端输入：
#   powershell -ExecutionPolicy Bypass -File "C:\Users\张逸帆\knowledge-wiki\tools\setup_scheduled_task.ps1"

$TaskName = "飞书知识库同步"
$ScriptPath = "C:\Users\张逸帆\knowledge-wiki\tools\sync_feishu.py"
$PythonPath = "python"

# 要同步的任务动作
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`" --headless" `
    -WorkingDirectory "C:\Users\张逸帆\knowledge-wiki"

# 触发器：每天早上 9:00
$Trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM

# 以当前用户身份运行（登录时运行）
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

# 设置：错过后尽快补跑、允许电池运行
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

# 注册任务
Register-ScheduledTask `
    -TaskName $TaskName `
    -Description "每日同步飞书云文档到本地 knowledge-wiki/raw/feishu/" `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Force

Write-Host "✅ 定时任务已创建：$TaskName"
Write-Host "   时间：每天早上 9:00"
Write-Host "   命令：python `"$ScriptPath`" --headless"
Write-Host ""
Write-Host "管理方式："
Write-Host "   - 查看/修改：运行 taskschd.msc"
Write-Host "   - 手动跑一次：python `"$ScriptPath`" --headless"
Write-Host "   - 删除任务：Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
