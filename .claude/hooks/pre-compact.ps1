# PreCompact hook: Remind Claude to update BUILD_STATUS.md before compaction
# This outputs a message that appears in Claude's context

$statusFile = Join-Path $PWD "BUILD_STATUS.md"

Write-Output "=== CONTEXT COMPACTION IMMINENT ==="
Write-Output ""
Write-Output "IMPORTANT: Update BUILD_STATUS.md NOW with:"
Write-Output "  - Current task in progress"
Write-Output "  - Files modified since last update"
Write-Output "  - Open discussion IDs and their status"
Write-Output "  - Resume instructions for after compaction"
Write-Output ""
Write-Output "If this is a LONG session (a soft/hard wrap-up may have been missed),"
Write-Output "run the 'wrapping-up-sessions' skill / '/handoff' to write a clean handoff"
Write-Output "artifact BEFORE this compaction (ADR-0018). Compaction is the lossy backstop."
Write-Output ""

if (Test-Path $statusFile) {
    $lastMod = (Get-Item $statusFile).LastWriteTime
    Write-Output "BUILD_STATUS.md last updated: $lastMod"
} else {
    Write-Output "WARNING: BUILD_STATUS.md not found! Create it to preserve session state."
}

Write-Output ""
Write-Output "Also: run 'bash ~/.claude/sync-all-memories.sh' to back up any new memories to GitHub."
Write-Output ""
Write-Output "==================================="

# Auto-sync shared memory to GitHub (non-blocking)
$syncScript = Join-Path $env:USERPROFILE ".claude\sync-all-memories.sh"
if (Test-Path $syncScript) {
    Start-Process -NoNewWindow -FilePath "bash" -ArgumentList $syncScript -ErrorAction SilentlyContinue
}
