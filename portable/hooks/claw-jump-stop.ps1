# Claw Jump Stop hook — PowerShell wrapper for Windows
# Reads Claude Code hook JSON from stdin and forwards to the agent.

$stdin = [Console]::In.ReadToEnd()
if ([string]::IsNullOrEmpty($stdin)) {
    exit 0
}

$scriptDir = Split-Path -Parent $PSCommandPath
$pythonScript = Join-Path $scriptDir "claw_jump_stop.py"

# Pipe stdin through to the Python script
$stdin | & python $pythonScript
exit $LASTEXITCODE
