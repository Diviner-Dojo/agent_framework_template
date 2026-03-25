# SessionStart hook: Remind Claude to read BUILD_STATUS.md after resume/compaction
# Also runs process health nudges to surface stale work and pending actions.
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
Write-Output "=== PROCESS HEALTH NUDGES ==="
Write-Output ""

# 1. Days since last retro
$retroDir = Join-Path $PWD "docs/sprints"
if (Test-Path $retroDir) {
    $retros = Get-ChildItem -Path $retroDir -Filter "RETRO-*.md" -ErrorAction SilentlyContinue | Sort-Object Name -Descending
    if ($retros.Count -gt 0) {
        $latestRetro = $retros[0].Name
        # Extract date from RETRO-YYYYMMDD.md
        if ($latestRetro -match "RETRO-(\d{4})(\d{2})(\d{2})") {
            $retroDate = [DateTime]::ParseExact("$($Matches[1])-$($Matches[2])-$($Matches[3])", "yyyy-MM-dd", $null)
            $daysSince = ((Get-Date) - $retroDate).Days
            if ($daysSince -gt 14) {
                Write-Output "  WARNING: Last retro was $daysSince days ago ($latestRetro). Consider running /retro."
            } elseif ($daysSince -gt 7) {
                Write-Output "  NOTE: Last retro was $daysSince days ago ($latestRetro)."
            }
        }
    } else {
        Write-Output "  NOTE: No retro files found. Consider running /retro after your first sprint."
    }
}

# 2. Retro action registry check
$actionRegistry = Join-Path $PWD "memory/decisions/retro-action-registry.md"
if (Test-Path $actionRegistry) {
    $content = Get-Content $actionRegistry -Raw -ErrorAction SilentlyContinue
    if ($content) {
        $openCount = ([regex]::Matches($content, "(?i)status:\s*open")).Count + ([regex]::Matches($content, "(?i)status:\s*in-progress")).Count
        if ($openCount -gt 0) {
            Write-Output "  NOTE: $openCount open retro action(s) in registry."
        }
    }
}

# 3. Pending adoption count
$adoptionLog = Join-Path $PWD "memory/lessons/adoption-log.md"
if (Test-Path $adoptionLog) {
    $content = Get-Content $adoptionLog -Raw -ErrorAction SilentlyContinue
    if ($content) {
        $pendingCount = ([regex]::Matches($content, "(?i)status:\s*PENDING")).Count
        if ($pendingCount -gt 10) {
            Write-Output "  WARNING: $pendingCount PENDING patterns in adoption log. Consider running /batch-evaluate."
        } elseif ($pendingCount -gt 0) {
            Write-Output "  NOTE: $pendingCount PENDING pattern(s) in adoption log."
        }
    }
}

# 4. Promotion candidates awaiting review
$dbPath = Join-Path $PWD "metrics/evaluation.db"
if (Test-Path $dbPath) {
    try {
        # Use Python for SQLite query since PowerShell doesn't have native SQLite
        $pendingPromotions = python -c "
import sqlite3, sys
try:
    conn = sqlite3.connect('$($dbPath -replace '\\','/')')
    row = conn.execute('SELECT COUNT(*) FROM promotion_candidates WHERE promoted = 0').fetchone()
    print(row[0] if row else 0)
    conn.close()
except: print(0)
" 2>$null
        if ([int]$pendingPromotions -gt 0) {
            Write-Output "  NOTE: $pendingPromotions promotion candidate(s) awaiting review. Consider running /promote."
        }
    } catch {}
}

# 5. Stale specs check
$specsDir = Join-Path $PWD "docs/sprints"
if (Test-Path $specsDir) {
    $staleSpecs = python -c "
import pathlib, re
specs = list(pathlib.Path('docs/sprints').glob('SPEC-*.md'))
stale = 0
for s in specs:
    text = s.read_text(encoding='utf-8')
    status_m = re.search(r'^status:\s*(.+)$', text, re.MULTILINE)
    type_m = re.search(r'^type:\s*(.+)$', text, re.MULTILINE)
    if not status_m: continue
    status = status_m.group(1).strip().strip('\"')
    spec_type = type_m.group(1).strip().strip('\"') if type_m else 'spec'
    if spec_type == 'vision': continue
    if status in ('approved', 'reviewed'): stale += 1
print(stale)
" 2>$null
    if ([int]$staleSpecs -gt 0) {
        Write-Output "  WARNING: $staleSpecs spec(s) still in approved/reviewed status. May need status update to 'complete'."
    }
}

# 6. Layer 3 health check
$memoryDirs = @("memory/patterns", "memory/decisions", "memory/reflections", "memory/rules")
$totalPromoted = 0
foreach ($dir in $memoryDirs) {
    $fullPath = Join-Path $PWD $dir
    if (Test-Path $fullPath) {
        $files = Get-ChildItem -Path $fullPath -Filter "*.md" -ErrorAction SilentlyContinue
        $totalPromoted += $files.Count
    }
}
if ($totalPromoted -eq 0) {
    Write-Output "  NOTE: Layer 3 (curated memory) is empty. Knowledge pipeline may be stalled."
}

Write-Output ""
Write-Output "========================"
