"""Generate an interactive HTML visualization of the git repository structure.

Renders a layperson-friendly infographic showing:
- Your personal repo vs the public repo as two distinct zones
- How far apart they are (divergence)
- Your branches as work-in-progress lanes
- Uncommitted work, stashes, and cleanup opportunities
- Remote branches collapsed by default with plain-English explanations

Usage:
    python scripts/git_visualize.py            # generate and open
    python scripts/git_visualize.py --no-open  # generate only
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path


def run_git(*args: str) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


@dataclass
class BranchInfo:
    name: str
    sha: str = ""
    upstream: str = ""
    track: str = ""
    merged_into_main: bool = False
    is_current: bool = False
    last_commit_date: str = ""
    last_commit_msg: str = ""
    ahead: int = 0
    behind: int = 0


@dataclass
class RepoState:
    current_branch: str = ""
    local_branches: list[BranchInfo] = field(default_factory=list)
    origin_branches: list[BranchInfo] = field(default_factory=list)
    upstream_branches: list[BranchInfo] = field(default_factory=list)
    origin_url: str = ""
    upstream_url: str = ""
    main_vs_upstream: tuple[int, int] = (0, 0)  # ahead, behind
    main_vs_origin: tuple[int, int] = (0, 0)
    uncommitted_files: list[dict] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)
    stashes: list[str] = field(default_factory=list)
    recent_commits: list[dict] = field(default_factory=list)


def gather_state() -> RepoState:
    """Collect all relevant git state into a single object."""
    state = RepoState()

    # Current branch
    state.current_branch = run_git("branch", "--show-current")

    # Remote URLs
    for remote in run_git("remote").splitlines():
        url = run_git("remote", "get-url", remote.strip())
        if remote.strip() == "origin":
            state.origin_url = url
        elif remote.strip() == "upstream":
            state.upstream_url = url

    # Divergence: local main vs upstream/main
    lr = run_git("rev-list", "--left-right", "--count", "main...upstream/main")
    if lr:
        parts = lr.split()
        state.main_vs_upstream = (int(parts[0]), int(parts[1]))

    # Divergence: local main vs origin/main
    lr = run_git("rev-list", "--left-right", "--count", "main...origin/main")
    if lr:
        parts = lr.split()
        state.main_vs_origin = (int(parts[0]), int(parts[1]))

    # Merged branches
    merged_raw = run_git("branch", "--merged", "main")
    merged = {b.strip().lstrip("* ") for b in merged_raw.splitlines()}

    # Local branches
    raw = run_git(
        "for-each-ref",
        "--format=%(refname:short)|%(objectname:short)|%(upstream:short)|%(upstream:track)",
        "--sort=-committerdate",
        "refs/heads/",
    )
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        name = parts[0]
        sha = parts[1] if len(parts) > 1 else ""
        upstream = parts[2] if len(parts) > 2 else ""
        track = parts[3] if len(parts) > 3 else ""

        # Get last commit info for this branch
        log_line = run_git("log", "-1", "--format=%ai|%s", name)
        log_parts = log_line.split("|", 1) if log_line else ["", ""]

        # Get ahead/behind vs main
        ahead, behind = 0, 0
        if name != "main":
            ab = run_git("rev-list", "--left-right", "--count", f"main...{name}")
            if ab:
                ab_parts = ab.split()
                behind, ahead = int(ab_parts[0]), int(ab_parts[1])

        state.local_branches.append(
            BranchInfo(
                name=name,
                sha=sha,
                upstream=upstream,
                track=track,
                merged_into_main=name in merged and name != "main",
                is_current=name == state.current_branch,
                last_commit_date=log_parts[0][:10] if log_parts[0] else "",
                last_commit_msg=log_parts[1] if len(log_parts) > 1 else "",
                ahead=ahead,
                behind=behind,
            )
        )

    # Remote branches (origin)
    raw = run_git(
        "for-each-ref",
        "--format=%(refname:short)|%(objectname:short)|%(committerdate:short)|%(subject)",
        "--sort=-committerdate",
        "refs/remotes/origin/",
    )
    for line in raw.splitlines():
        if not line.strip() or "HEAD" in line:
            continue
        parts = line.split("|")
        name = parts[0].replace("origin/", "")
        # Skip if there's a local branch with the same name
        local_names = {b.name for b in state.local_branches}
        state.origin_branches.append(
            BranchInfo(
                name=name,
                sha=parts[1] if len(parts) > 1 else "",
                last_commit_date=parts[2] if len(parts) > 2 else "",
                last_commit_msg=parts[3] if len(parts) > 3 else "",
                merged_into_main=name in merged,
            )
        )

    # Remote branches (upstream)
    raw = run_git(
        "for-each-ref",
        "--format=%(refname:short)|%(objectname:short)|%(committerdate:short)|%(subject)",
        "--sort=-committerdate",
        "refs/remotes/upstream/",
    )
    for line in raw.splitlines():
        if not line.strip() or "HEAD" in line:
            continue
        parts = line.split("|")
        name = parts[0].replace("upstream/", "")
        state.upstream_branches.append(
            BranchInfo(
                name=name,
                sha=parts[1] if len(parts) > 1 else "",
                last_commit_date=parts[2] if len(parts) > 2 else "",
                last_commit_msg=parts[3] if len(parts) > 3 else "",
            )
        )

    # Working directory status
    status_raw = run_git("status", "--porcelain")
    for line in status_raw.splitlines():
        if not line.strip():
            continue
        code = line[:2]
        filepath = line[3:]
        if code.startswith("?"):
            state.untracked_files.append(filepath)
        else:
            state.uncommitted_files.append({"status": code.strip(), "file": filepath})

    # Stashes
    stash_raw = run_git("stash", "list", "--format=%s")
    state.stashes = [s for s in stash_raw.splitlines() if s.strip()]

    # Recent commits on current branch
    log_raw = run_git("log", "-8", "--format=%h|%s|%ai|%an", state.current_branch)
    for line in log_raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        state.recent_commits.append(
            {
                "sha": parts[0],
                "message": parts[1] if len(parts) > 1 else "",
                "date": parts[2][:10] if len(parts) > 2 else "",
                "author": parts[3] if len(parts) > 3 else "",
            }
        )

    return state


def extract_org_name(url: str) -> str:
    """Pull the org/user name from a git URL."""
    # Handle https://github.com/Org/Repo.git and git@github.com:Org/Repo.git
    if "github.com" in url:
        parts = url.replace(":", "/").replace(".git", "").split("/")
        for i, p in enumerate(parts):
            if "github.com" in p and i + 1 < len(parts):
                return parts[i + 1]
    return url


def generate_html(state: RepoState) -> str:
    """Generate the layperson-friendly infographic HTML."""
    origin_org = extract_org_name(state.origin_url)
    upstream_org = extract_org_name(state.upstream_url)

    # Serialize state for JS
    js_state = {
        "currentBranch": state.current_branch,
        "localBranches": [
            {
                "name": b.name,
                "sha": b.sha,
                "merged": b.merged_into_main,
                "current": b.is_current,
                "date": b.last_commit_date,
                "message": b.last_commit_msg,
                "ahead": b.ahead,
                "behind": b.behind,
                "upstream": b.upstream,
                "track": b.track,
            }
            for b in state.local_branches
        ],
        "originBranches": [
            {
                "name": b.name,
                "sha": b.sha,
                "date": b.last_commit_date,
                "message": b.last_commit_msg,
                "merged": b.merged_into_main,
            }
            for b in state.origin_branches
        ],
        "upstreamBranches": [
            {
                "name": b.name,
                "sha": b.sha,
                "date": b.last_commit_date,
                "message": b.last_commit_msg,
            }
            for b in state.upstream_branches
        ],
        "mainVsUpstream": {
            "ahead": state.main_vs_upstream[0],
            "behind": state.main_vs_upstream[1],
        },
        "mainVsOrigin": {"ahead": state.main_vs_origin[0], "behind": state.main_vs_origin[1]},
        "uncommitted": [f for f in state.uncommitted_files],
        "untracked": state.untracked_files,
        "stashes": state.stashes,
        "recentCommits": state.recent_commits,
        "originOrg": origin_org,
        "upstreamOrg": upstream_org,
    }

    html = (
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>My Repository Map</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: #0d1117; color: #c9d1d9;
    min-height: 100vh; padding: 24px;
    overflow-x: auto;
  }

  /* Header */
  .header {
    text-align: center; margin-bottom: 32px;
  }
  .header h1 { font-size: 28px; color: #fff; margin-bottom: 4px; }
  .header .subtitle { color: #8b949e; font-size: 14px; }

  /* Main landscape layout */
  .landscape {
    display: flex; align-items: flex-start; gap: 0;
    min-height: 500px; position: relative;
    justify-content: center;
  }

  /* Repo zone */
  .repo-zone {
    border-radius: 16px; padding: 24px;
    min-width: 380px; max-width: 480px;
    position: relative;
  }
  .repo-zone h2 {
    font-size: 18px; margin-bottom: 4px;
    display: flex; align-items: center; gap: 8px;
  }
  .repo-zone .zone-subtitle {
    font-size: 12px; color: #8b949e; margin-bottom: 16px;
    line-height: 1.5;
  }

  .zone-upstream {
    background: #1a1230; border: 2px solid #6e40c9;
  }
  .zone-upstream h2 { color: #a371f7; }

  .zone-personal {
    background: #0d1f2d; border: 2px solid #1f6feb;
  }
  .zone-personal h2 { color: #58a6ff; }

  .zone-local {
    background: #0d2118; border: 2px solid #238636;
  }
  .zone-local h2 { color: #3fb950; }

  /* The connector arrow between zones */
  .connector {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; min-width: 120px; padding: 0 8px;
    position: relative;
  }
  .connector-line {
    width: 100%; height: 4px; position: relative;
    display: flex; align-items: center; justify-content: center;
  }
  .connector-line .line {
    flex: 1; height: 4px; border-radius: 2px;
  }
  .connector-line .arrow {
    font-size: 20px; margin: 0 -4px; position: relative; z-index: 1;
  }
  .connector-label {
    font-size: 12px; text-align: center; margin-top: 8px;
    padding: 6px 12px; border-radius: 8px;
    font-weight: 600; line-height: 1.4;
  }
  .sync-ok { background: #238636; color: #fff; }
  .sync-behind { background: #da3633; color: #fff; }
  .sync-ahead { background: #1f6feb; color: #fff; }
  .sync-diverged { background: #d29922; color: #fff; }

  /* Branch cards */
  .branch-card {
    background: rgba(255,255,255,0.06); border-radius: 10px;
    padding: 12px 14px; margin: 8px 0;
    border-left: 4px solid #444;
    transition: background 0.2s;
    cursor: default;
  }
  .branch-card:hover { background: rgba(255,255,255,0.1); }
  .branch-card.current { border-left-color: #f0c000; background: rgba(240,192,0,0.08); }
  .branch-card.merged { border-left-color: #555; opacity: 0.6; }
  .branch-card.active-work { border-left-color: #58a6ff; }
  .branch-card.is-main { border-left-color: #3fb950; }

  .branch-header {
    display: flex; align-items: center; gap: 8px; margin-bottom: 4px;
  }
  .branch-icon { font-size: 16px; }
  .branch-name { font-weight: 600; font-size: 14px; color: #e6edf3; }
  .branch-badge {
    font-size: 10px; padding: 2px 8px; border-radius: 10px;
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
  }
  .badge-you-are-here { background: #f0c000; color: #000; }
  .badge-merged { background: #555; color: #aaa; }
  .badge-main { background: #238636; color: #fff; }
  .badge-ahead { background: #1f6feb; color: #fff; }

  .branch-detail {
    font-size: 12px; color: #8b949e; margin-top: 4px; line-height: 1.5;
  }
  .branch-action {
    font-size: 11px; margin-top: 6px; padding: 4px 8px;
    border-radius: 6px; display: inline-block;
  }
  .action-cleanup { background: rgba(218,54,51,0.15); color: #f85149; }
  .action-active { background: rgba(31,111,235,0.15); color: #58a6ff; }
  .action-ok { background: rgba(35,134,54,0.15); color: #3fb950; }

  /* Collapsible section */
  .collapsible-header {
    cursor: pointer; user-select: none;
    display: flex; align-items: center; gap: 8px;
    padding: 8px 0; font-size: 13px; color: #8b949e;
    border: none; background: none; width: 100%;
    text-align: left;
  }
  .collapsible-header:hover { color: #c9d1d9; }
  .collapsible-header .chevron {
    transition: transform 0.2s; font-size: 10px;
  }
  .collapsible-header.open .chevron { transform: rotate(90deg); }
  .collapsible-body {
    max-height: 0; overflow: hidden; transition: max-height 0.3s ease;
  }
  .collapsible-body.open { max-height: 2000px; }

  /* Working area (bottom strip) */
  .working-area {
    margin-top: 32px; display: flex; gap: 20px;
    justify-content: center; flex-wrap: wrap;
  }
  .working-card {
    background: #161b22; border: 1px solid #30363d; border-radius: 12px;
    padding: 16px 20px; min-width: 280px; max-width: 400px;
  }
  .working-card h3 {
    font-size: 14px; margin-bottom: 10px;
    display: flex; align-items: center; gap: 8px;
  }
  .working-card .file-list {
    font-size: 12px; color: #8b949e; line-height: 1.8;
  }
  .working-card .file-list .status {
    display: inline-block; width: 18px; text-align: center;
    font-weight: bold; margin-right: 4px; border-radius: 3px;
    font-size: 10px; padding: 1px 3px;
  }
  .status-m { color: #d29922; }
  .status-new { color: #3fb950; }
  .status-d { color: #f85149; }

  .count-badge {
    background: #30363d; color: #8b949e;
    font-size: 11px; padding: 2px 8px; border-radius: 10px;
  }

  /* Tooltip */
  .tooltip-box {
    position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
    background: #161b22; border: 1px solid #30363d; border-radius: 12px;
    padding: 12px 20px; font-size: 13px; color: #8b949e;
    display: flex; gap: 20px; align-items: center;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4); z-index: 100;
  }
  .tooltip-box .key { color: #58a6ff; font-weight: 600; }

  /* Explainer boxes */
  .explainer {
    background: rgba(255,255,255,0.03); border: 1px dashed #30363d;
    border-radius: 8px; padding: 10px 14px; margin: 10px 0;
    font-size: 12px; color: #8b949e; line-height: 1.6;
  }
  .explainer strong { color: #c9d1d9; }

  /* Timeline */
  .timeline {
    margin-top: 12px;
  }
  .timeline-item {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 6px 0; font-size: 12px;
    border-left: 2px solid #21262d; margin-left: 6px; padding-left: 14px;
  }
  .timeline-item:first-child { border-left-color: #f0c000; }
  .timeline-sha {
    color: #58a6ff; font-family: monospace; font-size: 11px;
    flex-shrink: 0;
  }
  .timeline-msg { color: #c9d1d9; }
  .timeline-date { color: #484f58; font-size: 11px; flex-shrink: 0; }

  /* Health summary */
  .health-bar {
    display: flex; gap: 16px; justify-content: center;
    margin-bottom: 24px; flex-wrap: wrap;
  }
  .health-item {
    display: flex; align-items: center; gap: 6px;
    font-size: 13px; padding: 6px 14px;
    background: #161b22; border-radius: 20px; border: 1px solid #30363d;
  }
  .health-dot {
    width: 8px; height: 8px; border-radius: 50%;
  }
  .dot-green { background: #3fb950; }
  .dot-yellow { background: #d29922; }
  .dot-red { background: #f85149; }
  .dot-blue { background: #58a6ff; }
</style>
</head>
<body>

<div class="header">
  <h1>My Repository Map</h1>
  <div class="subtitle">A bird's-eye view of where your code lives and how it flows</div>
</div>

<!-- Health summary bar -->
<div class="health-bar" id="health-bar"></div>

<!-- Main landscape: left (upstream) -> center (origin) -> right (local) -->
<div class="landscape" id="landscape"></div>

<!-- Bottom: working directory state -->
<div class="working-area" id="working-area"></div>

<!-- Tooltip bar -->
<div class="tooltip-box">
  <span><span class="key">Branches</span> = separate workstreams (like drafts of a document)</span>
  <span><span class="key">Merged</span> = work that's been folded back into the main copy</span>
  <span><span class="key">Uncommitted</span> = edits you haven't saved to git yet</span>
</div>

<script>
const S = """
        + json.dumps(js_state)
        + """;

// ── Helpers ──
function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
}

function makeBranchCard(b, context) {
  const card = el('div', 'branch-card');
  if (b.current) card.classList.add('current');
  else if (b.merged) card.classList.add('merged');
  else if (b.name === 'main') card.classList.add('is-main');
  else if (b.ahead > 0) card.classList.add('active-work');

  let badges = '';
  if (b.current) badges += '<span class="branch-badge badge-you-are-here">\\u2b50 YOU ARE HERE</span> ';
  if (b.name === 'main') badges += '<span class="branch-badge badge-main">MAIN</span> ';
  if (b.merged) badges += '<span class="branch-badge badge-merged">MERGED</span> ';
  if (b.ahead > 0 && !b.current) badges += '<span class="branch-badge badge-ahead">+' + b.ahead + ' commits</span> ';

  let icon = '\\ud83c\\udf3f'; // branch icon
  if (b.name === 'main') icon = '\\ud83c\\udfe0';
  if (b.current) icon = '\\ud83d\\udccd';
  if (b.merged) icon = '\\u2705';

  card.innerHTML = '<div class="branch-header">'
    + '<span class="branch-icon">' + icon + '</span>'
    + '<span class="branch-name">' + b.name + '</span>'
    + badges + '</div>';

  // Plain-english detail
  let detail = '';
  if (b.name === 'main') {
    detail = 'Your main branch &mdash; the "official" version of your code.';
  } else if (b.current) {
    detail = 'This is where you\\'re working right now.';
    if (b.ahead > 0) detail += ' You have <strong>' + b.ahead + ' commit(s)</strong> not yet in main.';
  } else if (b.merged) {
    detail = 'This work has already been folded into main. It served its purpose.';
  } else if (b.ahead > 0) {
    detail = b.ahead + ' commit(s) ahead of main &mdash; work in progress.';
  }
  if (b.date) detail += '<br><span style="color:#484f58">Last touched: ' + b.date + '</span>';
  if (b.message) detail += '<br><span style="color:#6e7681">"' + b.message + '"</span>';

  if (detail) card.appendChild(el('div', 'branch-detail', detail));

  // Action suggestion
  if (b.merged && b.name !== 'main') {
    card.appendChild(el('div', 'branch-action action-cleanup',
      '\\ud83e\\uddf9 Safe to delete &mdash; this work is already in main'));
  } else if (b.current && b.ahead > 0) {
    card.appendChild(el('div', 'branch-action action-active',
      '\\ud83d\\ude80 Active work &mdash; merge into main when ready'));
  } else if (b.name === 'main') {
    card.appendChild(el('div', 'branch-action action-ok',
      '\\u2714 This is your home base'));
  }

  return card;
}

function makeCollapsible(title, count, contentFn) {
  const wrapper = el('div', '');
  const header = el('button', 'collapsible-header',
    '<span class="chevron">\\u25b6</span> ' + title
    + ' <span class="count-badge">' + count + '</span>');
  const body = el('div', 'collapsible-body');
  contentFn(body);
  header.onclick = () => {
    header.classList.toggle('open');
    body.classList.toggle('open');
  };
  wrapper.appendChild(header);
  wrapper.appendChild(body);
  return wrapper;
}

// ── Build the health bar ──
function buildHealthBar() {
  const bar = document.getElementById('health-bar');
  const items = [];

  // Sync status
  const behind = S.mainVsUpstream.behind;
  if (behind === 0) {
    items.push({dot: 'dot-green', text: 'In sync with public repo'});
  } else {
    items.push({dot: 'dot-red', text: behind + ' update(s) behind public repo'});
  }

  // Active branches
  const activeBranches = S.localBranches.filter(b => !b.merged && b.name !== 'main');
  items.push({dot: 'dot-blue', text: activeBranches.length + ' active branch(es)'});

  // Cleanup opportunities
  const cleanable = S.localBranches.filter(b => b.merged);
  if (cleanable.length > 0) {
    items.push({dot: 'dot-yellow', text: cleanable.length + ' branch(es) ready to clean up'});
  }

  // Uncommitted work
  const dirtyCount = S.uncommitted.length + S.untracked.length;
  if (dirtyCount > 0) {
    items.push({dot: 'dot-yellow', text: dirtyCount + ' unsaved change(s)'});
  }

  // Stashes
  if (S.stashes.length > 0) {
    items.push({dot: 'dot-yellow', text: S.stashes.length + ' stash(es) tucked away'});
  }

  items.forEach(item => {
    const div = el('div', 'health-item',
      '<div class="health-dot ' + item.dot + '"></div>' + item.text);
    bar.appendChild(div);
  });
}

// ── Build the landscape ──
function buildLandscape() {
  const landscape = document.getElementById('landscape');

  // ── LEFT: Upstream (public repo) ──
  const upstreamZone = el('div', 'repo-zone zone-upstream');
  upstreamZone.innerHTML = '<h2>\\ud83c\\udf0d Public Repo</h2>'
    + '<div class="zone-subtitle">'
    + '<strong>' + S.upstreamOrg + '</strong> on GitHub<br>'
    + 'The original project. Think of this as the <strong>published book</strong> &mdash; '
    + 'the official version that everyone sees.'
    + '</div>';

  // Upstream main
  const upMain = el('div', 'branch-card is-main');
  upMain.innerHTML = '<div class="branch-header">'
    + '<span class="branch-icon">\\ud83c\\udfe0</span>'
    + '<span class="branch-name">main</span>'
    + '<span class="branch-badge badge-main">OFFICIAL</span></div>'
    + '<div class="branch-detail">The published version of the framework.</div>';
  upstreamZone.appendChild(upMain);

  // Upstream remote branches (collapsed)
  if (S.upstreamBranches.length > 0) {
    const otherUpstream = S.upstreamBranches.filter(b => b.name !== 'main');
    if (otherUpstream.length > 0) {
      upstreamZone.appendChild(makeCollapsible(
        'Other branches on the public repo',
        otherUpstream.length,
        (body) => {
          body.appendChild(el('div', 'explainer',
            '<strong>What are these?</strong> These are branches that exist on the public repo. '
            + 'They\\'re like drafts and experiments happening in the published project. '
            + 'You didn\\'t create them and you don\\'t need to manage them. '
            + 'They\\'re visible to you because your computer is connected to that repo, '
            + 'like being able to see the table of contents of a book in a shared library.'));
          otherUpstream.forEach(b => {
            const card = el('div', 'branch-card');
            card.innerHTML = '<div class="branch-header">'
              + '<span class="branch-icon">\\ud83c\\udf3f</span>'
              + '<span class="branch-name">' + b.name + '</span></div>'
              + '<div class="branch-detail">'
              + (b.date ? 'Last activity: ' + b.date + '<br>' : '')
              + (b.message ? '"' + b.message + '"' : '') + '</div>';
            body.appendChild(card);
          });
        }
      ));
    }
  }

  landscape.appendChild(upstreamZone);

  // ── CONNECTOR: upstream <-> origin ──
  const conn1 = el('div', 'connector');
  const line1 = el('div', 'connector-line');
  const behind = S.mainVsUpstream.behind;
  const ahead = S.mainVsUpstream.ahead;

  let syncClass, syncText;
  if (behind === 0 && ahead === 0) {
    syncClass = 'sync-ok'; syncText = '\\u2705 Perfectly in sync';
  } else if (behind > 0 && ahead === 0) {
    syncClass = 'sync-behind'; syncText = '\\u2b07 ' + behind + ' update(s) behind';
  } else if (ahead > 0 && behind === 0) {
    syncClass = 'sync-ahead'; syncText = '\\u2b06 ' + ahead + ' commit(s) ahead';
  } else {
    syncClass = 'sync-diverged'; syncText = '\\u21c4 Diverged: ' + ahead + ' ahead, ' + behind + ' behind';
  }

  line1.innerHTML = '<span class="arrow" style="color:#6e40c9">\\u25c0</span>'
    + '<div class="line" style="background: linear-gradient(to right, #6e40c9, #1f6feb)"></div>'
    + '<span class="arrow" style="color:#1f6feb">\\u25b6</span>';
  conn1.appendChild(line1);
  conn1.appendChild(el('div', 'connector-label ' + syncClass, syncText));
  conn1.appendChild(el('div', 'explainer',
    'This connection shows whether<br>your copy matches the original.<br>'
    + '<strong>"Behind"</strong> = the public repo<br>has new stuff you haven\\'t grabbed yet.'));
  landscape.appendChild(conn1);

  // ── CENTER: Origin (your GitHub fork) ──
  const originZone = el('div', 'repo-zone zone-personal');
  originZone.innerHTML = '<h2>\\ud83d\\udd12 Your GitHub Copy</h2>'
    + '<div class="zone-subtitle">'
    + '<strong>' + S.originOrg + '</strong> on GitHub<br>'
    + 'Your personal fork. Think of this as <strong>your own copy of the book</strong> &mdash; '
    + 'you can scribble in the margins, write new chapters, and push changes back to the original when ready.'
    + '</div>';

  // Origin branches that match local (show as "published" versions)
  const originOnly = S.originBranches.filter(ob =>
    !S.localBranches.some(lb => lb.name === ob.name)
    && ob.name !== 'main' && ob.name !== 'HEAD'
  );

  // Show main on origin
  const originMain = el('div', 'branch-card is-main');
  const originSync = S.mainVsOrigin;
  let originMainDetail = 'The main branch on your GitHub copy.';
  if (originSync.ahead === 0 && originSync.behind === 0) {
    originMainDetail += ' <strong style="color:#3fb950">Matches your local main.</strong>';
  } else if (originSync.behind > 0) {
    originMainDetail += ' <strong style="color:#d29922">' + originSync.behind + ' behind your local.</strong>';
  }
  originMain.innerHTML = '<div class="branch-header">'
    + '<span class="branch-icon">\\ud83c\\udfe0</span>'
    + '<span class="branch-name">main</span>'
    + '<span class="branch-badge badge-main">MAIN</span></div>'
    + '<div class="branch-detail">' + originMainDetail + '</div>';
  originZone.appendChild(originMain);

  // Origin-only branches (collapsed)
  if (originOnly.length > 0) {
    originZone.appendChild(makeCollapsible(
      'Other branches on your GitHub',
      originOnly.length,
      (body) => {
        body.appendChild(el('div', 'explainer',
          '<strong>What are these?</strong> These are branches that exist on your GitHub copy '
          + 'but you don\\'t have checked out locally. Some may be leftover from old pull requests. '
          + 'They\\'re like bookmarks in your copy of the book &mdash; not hurting anything, '
          + 'but you can remove them if you want a tidy shelf.'));
        originOnly.forEach(b => {
          const card = el('div', 'branch-card' + (b.merged ? ' merged' : ''));
          card.innerHTML = '<div class="branch-header">'
            + '<span class="branch-icon">' + (b.merged ? '\\u2705' : '\\ud83c\\udf3f') + '</span>'
            + '<span class="branch-name">' + b.name + '</span>'
            + (b.merged ? '<span class="branch-badge badge-merged">MERGED</span>' : '')
            + '</div>'
            + '<div class="branch-detail">'
            + (b.date ? 'Last activity: ' + b.date + '<br>' : '')
            + (b.message ? '"' + b.message + '"' : '') + '</div>';
          body.appendChild(card);
        });
      }
    ));
  }

  landscape.appendChild(originZone);

  // ── CONNECTOR: origin <-> local ──
  const conn2 = el('div', 'connector');
  const line2 = el('div', 'connector-line');
  line2.innerHTML = '<span class="arrow" style="color:#1f6feb">\\u25c0</span>'
    + '<div class="line" style="background: linear-gradient(to right, #1f6feb, #238636)"></div>'
    + '<span class="arrow" style="color:#238636">\\u25b6</span>';
  conn2.appendChild(line2);
  conn2.appendChild(el('div', 'connector-label sync-ok', '\\ud83d\\udcbb Your Computer'));
  conn2.appendChild(el('div', 'explainer',
    '<strong>Push</strong> = send your local<br>work up to GitHub.<br>'
    + '<strong>Pull</strong> = grab the latest<br>from GitHub to your computer.'));
  landscape.appendChild(conn2);

  // ── RIGHT: Local (your computer) ──
  const localZone = el('div', 'repo-zone zone-local');
  localZone.innerHTML = '<h2>\\ud83d\\udcbb Your Computer</h2>'
    + '<div class="zone-subtitle">'
    + 'This is where you actually do the work. '
    + 'Think of this as <strong>your writing desk</strong> &mdash; '
    + 'the book is open, and you\\'re making edits.'
    + '</div>';

  // Local branches
  // Sort: current first, then main, then active, then merged
  const sorted = [...S.localBranches].sort((a, b) => {
    if (a.current) return -1; if (b.current) return 1;
    if (a.name === 'main') return -1; if (b.name === 'main') return 1;
    if (a.merged !== b.merged) return a.merged ? 1 : -1;
    return 0;
  });

  sorted.forEach(b => {
    localZone.appendChild(makeBranchCard(b, 'local'));
  });

  // Recent commits timeline
  if (S.recentCommits.length > 0) {
    localZone.appendChild(el('h3', '', '<br>Recent Activity'));
    const timeline = el('div', 'timeline');
    S.recentCommits.forEach((c, i) => {
      const item = el('div', 'timeline-item',
        '<span class="timeline-sha">' + c.sha + '</span>'
        + '<span class="timeline-msg">' + c.message + '</span>'
        + '<span class="timeline-date">' + c.date + '</span>');
      timeline.appendChild(item);
    });
    localZone.appendChild(timeline);
  }

  landscape.appendChild(localZone);
}

// ── Build working area (bottom cards) ──
function buildWorkingArea() {
  const area = document.getElementById('working-area');

  // Uncommitted changes
  if (S.uncommitted.length > 0 || S.untracked.length > 0) {
    const card = el('div', 'working-card');
    card.innerHTML = '<h3>\\u270f\\ufe0f Unsaved Changes '
      + '<span class="count-badge">' + (S.uncommitted.length + S.untracked.length) + '</span></h3>'
      + '<div class="explainer">These files have been modified but not yet committed. '
      + 'Think of them as <strong>edits on your desk that haven\\'t been filed yet</strong>. '
      + 'Until you commit them, they\\'re not part of the permanent record.</div>';

    const list = el('div', 'file-list');
    S.uncommitted.forEach(f => {
      list.appendChild(el('div', '',
        '<span class="status status-m">' + f.status + '</span> ' + f.file));
    });
    S.untracked.forEach(f => {
      list.appendChild(el('div', '',
        '<span class="status status-new">NEW</span> ' + f));
    });
    card.appendChild(list);
    area.appendChild(card);
  }

  // Stashes
  if (S.stashes.length > 0) {
    const card = el('div', 'working-card');
    card.innerHTML = '<h3>\\ud83d\\udce6 Stashed Work '
      + '<span class="count-badge">' + S.stashes.length + '</span></h3>'
      + '<div class="explainer">Stashes are like <strong>setting aside a half-finished task</strong> '
      + 'so you can work on something else. The work is saved but hidden. '
      + 'These are often forgotten &mdash; check if you still need them.</div>';

    const list = el('div', 'file-list');
    S.stashes.forEach(s => {
      list.appendChild(el('div', '', '\\ud83d\\udce6 ' + s));
    });
    card.appendChild(list);
    area.appendChild(card);
  }

  // If everything is clean
  if (S.uncommitted.length === 0 && S.untracked.length === 0 && S.stashes.length === 0) {
    const card = el('div', 'working-card');
    card.innerHTML = '<h3>\\u2728 Clean Desk</h3>'
      + '<div class="branch-detail">No unsaved changes, no stashes. Everything is committed and tidy.</div>';
    area.appendChild(card);
  }
}

// ── Run ──
buildHealthBar();
buildLandscape();
buildWorkingArea();
</script>
</body>
</html>"""
    )
    return html


def main() -> None:
    no_open = "--no-open" in sys.argv
    state = gather_state()
    html = generate_html(state)

    out_path = Path(tempfile.gettempdir()) / "git_repo_map.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Git map generated: {out_path}")

    if not no_open:
        webbrowser.open(str(out_path))
        print("Opened in browser.")


if __name__ == "__main__":
    main()
