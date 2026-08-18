# SessionStart hook: Remind Claude to read BUILD_STATUS.md after resume/compaction
# and surface process health indicators to prevent discipline drift.
# See: RETRO-20260318, DISC-20260319-004414-process-maturity-discipline-drift-prevention
#
# INTERPRETER: settings.json invokes this with `powershell` = Windows PowerShell 5.1
# (measured 2026-08-08: 5.1.26100.8875), NOT pwsh 7. Join-Path takes exactly TWO
# arguments in 5.1 -- the 3+-argument form is a pwsh-7-only feature and throws
# "A positional parameter cannot be found". Nest Join-Path calls instead. Before this
# was fixed, every PROCESS HEALTH check below except one failed under the configured
# interpreter (measured: 198 stderr lines, 39 naming Join-Path, one surviving output
# line -- and that line, "Layer 3 empty", was false, produced by the failure itself).

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
# Surfaces drift indicators so the agent (and developer) see them when this hook runs --
# which SessionStart events run it is set by the matcher in .claude/settings.json, so this
# is not "every session". These are informational, not blocking.

Write-Output ""
Write-Output "=== PROCESS HEALTH ==="

# 1. Days since last retro
$retroDir = Join-Path (Join-Path $PWD "docs") "sprints"
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
$registryFile = Join-Path (Join-Path (Join-Path $PWD "memory") "decisions") "retro-action-registry.md"
if (Test-Path $registryFile) {
    $openCount = (Select-String -Path $registryFile -Pattern '\| OPEN \|' -SimpleMatch).Count
    if ($openCount -gt 0) {
        Write-Output "  [i] Retro action registry: $openCount OPEN action items. Check memory/decisions/retro-action-registry.md."
    }
}

# 3. PENDING adoption count (from adoption-log.md)
$adoptionLog = Join-Path (Join-Path (Join-Path $PWD "memory") "lessons") "adoption-log.md"
if (Test-Path $adoptionLog) {
    $pendingCount = (Select-String -Path $adoptionLog -Pattern '^\| .* \| PENDING \|' ).Count
    if ($pendingCount -gt 10) {
        Write-Output "  [!] $pendingCount PENDING adoption patterns. Run /batch-evaluate to clear backlog."
    } elseif ($pendingCount -gt 0) {
        Write-Output "  [i] $pendingCount PENDING adoption patterns in adoption log."
    }
}

# 4. Promotion candidates awaiting review
$dbPath = Join-Path (Join-Path $PWD "metrics") "evaluation.db"
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
$specsDir = Join-Path (Join-Path $PWD "docs") "sprints"
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
    $dirPath = Join-Path (Join-Path $PWD "memory") $dir
    if (Test-Path $dirPath) {
        $totalPromoted += (Get-ChildItem -Path $dirPath -File).Count
    }
}
if ($totalPromoted -eq 0) {
    Write-Output "  [!] Layer 3 empty (0 promoted patterns/decisions/reflections/rules). Knowledge pipeline stalled."
}

# 7. Shared memory / heritage availability
$sharedMemory = Join-Path (Join-Path $env:USERPROFILE ".claude") "shared-memory"
$heritage = Join-Path (Join-Path $sharedMemory "heritage") "HERITAGE.md"
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

# 9. Education gate backlog (Principle #5 deferrals that were never closed)
# READ-ONLY. docs/education/CONTRACTS.md declares gates.yaml has exactly ONE writer
# (the ingest path via gate_registry.py's atomic save_registry); this hook must never
# become a second one, so it shells out to the `backlog` READ subcommand and prints
# what it returns. INFORMATIONAL ONLY: nothing here fails, blocks, or gates a build --
# turning Principle #5 into a build condition is a governance change that needs its own
# /plan and a Steward gate (docs/education/governance-mechanisms.md Row 6).
# OWED-DEBT: docs/education/governance-mechanisms.md Row 6 -- its sentences "Nothing WARNS
# either.", "Nothing notices." and "Visibility that depends on somebody choosing to look
# is ... the only one operating here." predate this check and are now false on the events
# the matcher selects. That file is outside this change's scope. The debt is not recorded
# only in this comment: tests/test_education_backlog_surfacing.py has a test that fails if
# the doc is corrected while this note remains, or if this note is deleted while the doc is
# still false.
# SCOPE OF THIS NUDGE: it appears only when this hook runs, and which SessionStart events
# run it is set by the matcher in .claude/settings.json. Measured 2026-08-09 that matcher
# was `resume|compact`, so the backlog surfaced on resume/compaction but NOT on a fresh
# session. Read settings.json rather than trusting that date.
# Shelling out to python buys the documented strict validator + the tested age logic
# instead of a second, unvalidated YAML parser written in PowerShell against a format
# CONTRACTS.md declares strict. Cost, four independent Measure-Command median runs on this
# machine (2026-08-08 and 2026-08-09, the last one after the nudge grew to four lines):
# subcommand medians 67-85 ms against hook-total medians 479-770 ms, i.e. 11-16% of the
# hook. Latest 7-run sample: subcommand median 73.7 ms, hook median 636.0 ms => 11.6%.
# Individual runs are far noisier than their medians (that sample's raw spread: subcommand
# 66-280 ms, hook 453-926 ms, warm vs cold file cache), so treat the share as "roughly a
# tenth to a sixth", not a fixed number.
$gatesFile = Join-Path (Join-Path (Join-Path $PWD "docs") "education") "gates.yaml"
$gateCli = Join-Path (Join-Path (Join-Path $PWD "scripts") "education") "gate_registry.py"
if ((Test-Path $gatesFile) -and (Test-Path $gateCli)) {
    try {
        $backlogLines = & python $gateCli --registry $gatesFile backlog 2>$null
        if ($LASTEXITCODE -eq 0 -and $backlogLines) {
            $backlogLines | ForEach-Object { Write-Output $_ }
        }
    } catch {
        # python may not be on PATH — skip silently (same idiom as the sqlite3 check above)
    }
}

Write-Output ""
Write-Output "========================"
