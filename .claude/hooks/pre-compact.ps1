# PreCompact hook: Remind Claude to update BUILD_STATUS.md before compaction
# This outputs a message that appears in Claude's context

$statusFile = Join-Path $PWD "BUILD_STATUS.md"

Write-Output "=== CONTEXT COMPACTION IMMINENT ==="
Write-Output ""
Write-Output "IMPORTANT: Update BUILD_STATUS.md NOW with INCREMENTAL MERGING:"
Write-Output "  1. Move current content under '## Previous Session (YYYY-MM-DD HH:MM)'"
Write-Output "  2. Write fresh status above it (current task, modified files, open discussions, resume instructions)"
Write-Output "  3. Keep at most 3 previous session sections — remove the oldest if needed"
Write-Output "  This preserves context across compaction rounds."
Write-Output ""

if (Test-Path $statusFile) {
    $lastMod = (Get-Item $statusFile).LastWriteTime
    Write-Output "BUILD_STATUS.md last updated: $lastMod"
} else {
    Write-Output "WARNING: BUILD_STATUS.md not found! Create it to preserve session state."
}

Write-Output ""
Write-Output "==================================="
