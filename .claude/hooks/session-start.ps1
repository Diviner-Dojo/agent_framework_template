# SessionStart hook: Remind Claude to read BUILD_STATUS.md after resume/compaction
# This outputs a message that appears in Claude's context

$statusFile = Join-Path $PWD "BUILD_STATUS.md"

Write-Output "=== SESSION RESUMED ==="
Write-Output ""

if (Test-Path $statusFile) {
    Write-Output "BUILD_STATUS.md exists. Read it to restore context about:"
    Write-Output "  - Current task and progress"
    Write-Output "  - Open discussion IDs"
    Write-Output "  - Files modified recently"
    Write-Output "  - Resume instructions"
    Write-Output ""
    Write-Output "Action: Read the file BUILD_STATUS.md before doing anything else."
} else {
    Write-Output "No BUILD_STATUS.md found. This may be a fresh session."
    Write-Output "Check CLAUDE.md for project overview and conventions."
}

Write-Output ""
Write-Output "========================"
