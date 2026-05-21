# SessionStart hook: Remind Claude to read BUILD_STATUS.md after resume/compaction
# and surface process health indicators to prevent discipline drift.
# See: RETRO-20260318, DISC-20260319-004414-process-maturity-discipline-drift-prevention

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

# --- Process Health Nudge ---
# Surfaces drift indicators so the agent (and developer) see them at session start.
# These are informational, not blocking.

Write-Output ""
Write-Output "=== PROCESS HEALTH ==="

# 1. Days since last retro
$retroDir = Join-Path $PWD "docs" "sprints"
if (Test-Path $retroDir) {
    $latestRetro = Get-ChildItem -Path $retroDir -Filter "RETRO-*.md" |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if ($latestRetro) {
        # Extract date from filename RETRO-YYYYMMDD.md
        $retroDate = $latestRetro.Name -replace '^RETRO-(\d{4})(\d{2})(\d{2}).*$', '$1-$2-$3'
        try {
            $retroDateTime = [DateTime]::ParseExact($retroDate, "yyyy-MM-dd", $null)
            $daysSince = ([DateTime]::Now - $retroDateTime).Days
            if ($daysSince -gt 14) {
                Write-Output "  [!] RETRO OVERDUE: Last retro was $daysSince days ago ($($latestRetro.Name)). Run /retro."
            } elseif ($daysSince -gt 7) {
                Write-Output "  [i] Last retro: $daysSince days ago ($($latestRetro.Name)). Consider running /retro soon."
            } else {
                Write-Output "  [ok] Last retro: $daysSince days ago ($($latestRetro.Name))."
            }
        } catch {
            Write-Output "  [?] Could not parse retro date from $($latestRetro.Name)."
        }
    } else {
        Write-Output "  [!] No retro files found. Run /retro."
    }
}

# 2. Retro action registry check
$registryFile = Join-Path $PWD "memory" "decisions" "retro-action-registry.md"
if (Test-Path $registryFile) {
    $openCount = (Select-String -Path $registryFile -Pattern '\| OPEN \|' -SimpleMatch).Count
    if ($openCount -gt 0) {
        Write-Output "  [i] Retro action registry: $openCount OPEN action items. Check memory/decisions/retro-action-registry.md."
    }
}

# 3. PENDING adoption count (from adoption-log.md)
$adoptionLog = Join-Path $PWD "memory" "lessons" "adoption-log.md"
if (Test-Path $adoptionLog) {
    $pendingCount = (Select-String -Path $adoptionLog -Pattern '^\| .* \| PENDING \|' ).Count
    if ($pendingCount -gt 10) {
        Write-Output "  [!] $pendingCount PENDING adoption patterns. Run /batch-evaluate to clear backlog."
    } elseif ($pendingCount -gt 0) {
        Write-Output "  [i] $pendingCount PENDING adoption patterns in adoption log."
    }
}

# 4. Promotion candidates awaiting review
$dbPath = Join-Path $PWD "metrics" "evaluation.db"
if (Test-Path $dbPath) {
    try {
        $query = "SELECT COUNT(*) FROM promotion_candidates WHERE status = 'pending'"
        $result = & sqlite3 $dbPath $query 2>$null
        if ($result -and [int]$result -gt 0) {
            Write-Output "  [i] $result promotion candidate(s) awaiting review. Run /promote."
        }
    } catch {
        # sqlite3 may not be on PATH — skip silently
    }
}

# 5. Stale specs check
$specsDir = Join-Path $PWD "docs" "sprints"
if (Test-Path $specsDir) {
    $staleCount = 0
    Get-ChildItem -Path $specsDir -Filter "SPEC-*.md" | ForEach-Object {
        $content = Get-Content $_.FullName -Raw
        if ($content -match '(?m)^status:\s*(approved|reviewed)' -and $content -notmatch '(?m)^type:\s*vision') {
            $staleCount++
        }
    }
    if ($staleCount -gt 0) {
        Write-Output "  [i] $staleCount specs still marked approved/reviewed. Verify if implemented."
    }
}

# 5b. Unclosed complete specs (status: complete but missing closure fields)
if (Test-Path $specsDir) {
    $unclosedCount = 0
    Get-ChildItem -Path $specsDir -Filter "SPEC-*.md" | ForEach-Object {
        $content = Get-Content $_.FullName -Raw
        if ($content -match '(?m)^status:\s*complete') {
            $isVision = $content -match '(?m)^type:\s*vision'
            $hasDate = $content -match '(?m)^completed_at:\s*\S+'
            $hasCommit = $content -match '(?m)^completed_commit:\s*\S+'
            if (-not $hasDate -or (-not $hasCommit -and -not $isVision)) {
                $unclosedCount++
            }
        }
    }
    if ($unclosedCount -gt 0) {
        Write-Output "  [!] $unclosedCount complete spec(s) missing closure fields. Run: python scripts/close_spec.py --list"
    }
}

# 6. Layer 3 health (quick check — count files in memory/ subdirs)
$memoryDirs = @("patterns", "decisions", "reflections", "rules")
$totalPromoted = 0
foreach ($dir in $memoryDirs) {
    $dirPath = Join-Path $PWD "memory" $dir
    if (Test-Path $dirPath) {
        $totalPromoted += (Get-ChildItem -Path $dirPath -File).Count
    }
}
if ($totalPromoted -eq 0) {
    Write-Output "  [!] Layer 3 empty (0 promoted patterns/decisions/reflections/rules). Knowledge pipeline stalled."
}

# 7. Shared memory / heritage availability
$sharedMemory = Join-Path $env:USERPROFILE ".claude" "shared-memory"
$heritage = Join-Path $sharedMemory "heritage" "HERITAGE.md"
$warnings = Join-Path $sharedMemory "universal-warnings.md"
if (Test-Path $heritage) {
    $heritageCount = (Get-ChildItem -Path (Join-Path $sharedMemory "heritage") -Recurse -Filter "*.md" | Where-Object { $_.Name -ne "HERITAGE.md" }).Count
    Write-Output "  [i] Heritage collection: $heritageCount formative discussions available at ~/.claude/shared-memory/heritage/"
}
if (Test-Path $warnings) {
    Write-Output "  [i] Universal warnings (15 lessons) at ~/.claude/shared-memory/universal-warnings.md"
}

# 8. Framework changelog — new innovations from sibling projects
$changelog = Join-Path $sharedMemory "FRAMEWORK_CHANGELOG.md"
if (Test-Path $changelog) {
    $changelogLines = Get-Content $changelog | Where-Object { $_ -match '^\- \*\*' }
    $entryCount = $changelogLines.Count
    if ($entryCount -gt 0) {
        Write-Output "  [i] Framework changelog: $entryCount innovations tracked. Check ~/.claude/shared-memory/FRAMEWORK_CHANGELOG.md for updates."
    }
}

Write-Output ""
Write-Output "========================"
