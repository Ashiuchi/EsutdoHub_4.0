# Configura o WSL Ubuntu para iniciar automaticamente no login do Windows.
# Execute este script uma vez como Administrador no PowerShell do Windows:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_wsl_autostart.ps1

$taskName = "WSL Ubuntu Autostart"
$distro   = "Ubuntu"

$action = New-ScheduledTaskAction `
    -Execute  "wsl.exe" `
    -Argument "--distribution $distro -- sleep infinity"

$trigger = New-ScheduledTaskTrigger -AtLogon

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances  IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -StartWhenAvailable `
    -Hidden

$principal = New-ScheduledTaskPrincipal `
    -UserId   $env:USERNAME `
    -RunLevel Limited `
    -LogonType Interactive

Register-ScheduledTask `
    -TaskName  $taskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -Principal $principal `
    -Force

Write-Host "Task '$taskName' registrada com sucesso." -ForegroundColor Green
Write-Host "O WSL Ubuntu (e o Ollama via systemd) vao iniciar automaticamente no proximo login." -ForegroundColor Cyan
