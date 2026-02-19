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

if (Test-Path $statusFile) {
    $lastMod = (Get-Item $statusFile).LastWriteTime
    Write-Output "BUILD_STATUS.md last updated: $lastMod"
} else {
    Write-Output "WARNING: BUILD_STATUS.md not found! Create it to preserve session state."
}

Write-Output ""
Write-Output "==================================="
