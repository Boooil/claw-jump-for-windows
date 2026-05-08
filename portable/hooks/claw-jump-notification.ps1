# Claw Jump Notification hook — PowerShell wrapper for Windows

$stdin = [Console]::In.ReadToEnd()
if ([string]::IsNullOrEmpty($stdin)) {
    exit 0
}

$scriptDir = Split-Path -Parent $PSCommandPath
$pythonScript = Join-Path $scriptDir "claw_jump_notification.py"
$stdin | & python $pythonScript
exit $LASTEXITCODE
