"""PreToolUse validator: file locking, protected files, secrets, and a Bash command guard.

Reads JSON tool input from stdin. Outputs hook response JSON to stdout.
Exit code 0 always (hook errors should not block work).

File Locking:
  - Atomic lock acquisition via directory creation (race-condition safe)
  - Locks auto-expire after 120 seconds
  - Session-based: locks tied to the session that created them

Secret Detection:
  - Scans content for 12 secret patterns (API keys, AWS keys, JWT, Slack, Bearer, Anthropic,
    OpenAI, GCP, etc.)
  - Skips test files to reduce false positives
  - Uses "ask" permission to flag without hard-blocking

Protected Files (Write/Edit):
  - Blocks edits to .git/, .env, evaluation.db, .claude/settings.json
  - Blocks Write/Edit to any ``discussions/**/events.jsonl`` (Layer 1 is append-only and is
    written only by ``scripts/`` — never by hand)

Bash Command Guard (``check_bash_command``):
  - Refuses shell commands whose *text* shows a write/truncate/move/delete/chmod aimed at a
    protected path, plus ``sqlite3`` DML/DDL against ``metrics/evaluation.db``.

  SCOPE — WHAT THIS GUARD CLAIMS TO BE, AND WHAT IT DOES NOT.
  This is **disclosed defence-in-depth: it raises the cost of a careless act. It is NOT a
  boundary, and no document may describe it as one.**

  That wording is not modesty; it is the conclusion of three review rounds. Each round found a
  new way to route around the same guard — shell grouping ``(...)``, ``&&`` / ``;`` chaining,
  ``bash -lc``, a mis-parsed ``robocopy`` destination, opaque SQL spellings — and each fix was
  correct, and the next round found more. The pattern is the finding: **predicting what a shell
  command will do by reading its text is unwinnable.** A shell can spell any act an unbounded
  number of ways, and a guard that keeps announcing the class is closed becomes exactly the
  "prose overstates code" defect this file's own education row exists to remove.

  So this file has STOPPED GROWING THE VERB TABLES. The fixes below are parser-level and
  general (a leading reserved word shadowed the real command word; a combined ``-lc`` cluster
  was not unwrapped). New *verbs* are not being added, because completeness there is not
  reachable and claiming it is the failure mode.

  WHERE THE REAL GUARANTEE LIVES. Deterministic detection of Layer 1 tampering is
  ``scripts/verify_layer1_integrity.py``, wired into ``scripts/quality_gate.py`` as
  ``check_layer1_integrity``. It records a sha256 of every sealed ``discussions/**`` record in
  an append-only manifest and re-compares the bytes, so it reports a change **regardless of how
  the change was made** — shell, editor, Python, git, a background process, a subagent nobody
  watched. It cannot be out-spelled, because it never tries to predict a command. It is a
  DETECTIVE control (it tells you afterwards) where this one is PREVENTIVE (it refuses
  beforehand), and it requires no ``.claude/settings.json`` wiring to work — which is precisely
  why it is the stronger of the two. If you have to trust exactly one of these, trust that one.

  STATE THAT CLAIM AT ITS ACTUAL WIDTH. It watches **what is in the manifest**, and red means
  **the bytes moved** — a digest mismatch, a file gone from disk, conflicting manifest lines, or
  a committed git blob the working copy is not. It does NOT go red merely because a record
  stopped being *classified* as sealed: sealed-ness comes from ``metrics/evaluation.db``
  (gitignored — ``.gitignore:13`` matches ``*.db``) and the read-only bit (git does not carry
  it), so folding that into the verdict marked 236 of this repo's 278 byte-identical records
  CHANGED on any fresh clone. Losing the seal is now a separate, never-fatal signal. This
  matters *here* because the KNOWN-OPEN list below leaves the un-sealing primitives
  (``attrib -r``, ``Set-ItemProperty -Name IsReadOnly``) unmatched on the grounds that the
  detective control catches un-sealing. It does not catch un-sealing as a failure. It catches
  **the byte change the un-sealing enables**, which is the thing that matters — but the two are
  not the same sentence, and the narrower one is the true one.

  WHAT IT IS NOT — read this before trusting it.
  This is **command-text matching, not a sandbox**. It reads the literal string the agent asked
  to run and refuses obviously destructive *shapes*. Concretely it CANNOT stop:
    * obfuscation or indirection — ``P=discussions; rm -rf "$P"``, a base64-decoded path, a glob
      that only expands to a protected path at runtime (``rm -rf disc*``), or a path assembled
      from environment variables. ``powershell -EncodedCommand`` IS base64-decoded and re-checked,
      but the decoded text then gets only this same text matching, so a payload that obfuscates
      *inside* the encoding is not caught by decoding it;
    * **a relative path whose meaning comes from the shell's working directory.** This is the
      guard's most important blind spot after obfuscation, and it is *live on this machine*: both
      the ``Bash`` and ``PowerShell`` tools document that "working directory persists between
      calls". So ``cd discussions/2026-08-07`` in one tool call and ``rm -rf DISC-1`` in the
      **next** call is invisible — the second command's text names nothing protected, and a
      PreToolUse hook sees one command at a time with no memory of the shell's state. Within a
      *single* command string ``cd X && rm -rf Y`` IS resolved (see ``_join_cwd``); across
      separate calls it is not, and it cannot be, from command text alone;
    * a write performed by a *program it launches* rather than by the command line itself —
      ``bash cleanup.sh``, ``python tidy.py``, ``make clean``, a git hook, an editor, a server;
    * **SQL it cannot read.** ``sqlite3 db "DELETE FROM …"`` is inspected, but
      ``sqlite3 db < wipe.sql`` and ``sqlite3 db ".read wipe.sql"`` supply the statements from a
      file the hook never opens. Those shapes are ASKed (an opaque script against Layer 2 is a
      human's call) — but "ask" here means *we could not read it*, not *we judged it safe*;
    * ``git clean -fd`` / ``git checkout -- .`` / ``rm -rf .`` / ``rm -rf *`` style commands that
      name no path but destroy untracked, modified or working-directory files anyway;
    * **a destructive verb that is not on the list below.** The verb tables
      (``DESTRUCTIVE_ALL_ARGS`` / ``DESTRUCTIVE_DEST_ONLY`` / ``DESTRUCTIVE_GIT_SUBCOMMANDS``) are
      a *closed enumeration*, so this is the guard's widest hole after obfuscation. POSIX **and**
      PowerShell/cmd verbs are enumerated (this repo's declared primary shell is PowerShell and a
      separate ``PowerShell`` tool exists alongside ``Bash``), but enumeration is not coverage.
      Known-unmatched shapes on Windows include .NET calls
      (``[System.IO.File]::Delete('…')``, ``[IO.File]::WriteAllText(…)``), ``Invoke-Expression``
      / ``iex`` on a built-up string, ``Start-Process``, and cmdlet aliases nobody listed. Adding
      a verb here is cheap; *knowing which verb to add* is the part that does not scale;
    * anything at all once a shell is already running (it is a *pre*-tool hook, not a syscall
      filter).
  It will also produce **false positives, and ``deny`` has no in-session override**. Two classes
  are known, and the second was found by measurement rather than imagination:
    * **Path lookalikes.** Matching is by path *component* (see ``_classify_path``), so
      ``my-discussions-notes/`` is correctly ignored but a hypothetical ``docs/discussions/`` or a
      scratch copy at ``/tmp/backup/metrics/evaluation.db`` would be refused even though neither is
      this repo's Layer 1 or Layer 2.
    * **Inline python whose write does not target the protected path.** Until the ``_py_call_ops``
      rewrite, the inline-python branch denied on the mere CO-OCCURRENCE of a write verb anywhere
      and a protected path anywhere — it never checked that the write *targeted* the path. Six
      read-only shapes were measured as ``deny``: ``shutil.copy('metrics/evaluation.db',
      '/tmp/scratch.db')`` (the copy-the-DB-to-scratch idiom this repo's own task briefs mandate);
      a read-only ``sqlite3.connect('file:metrics/evaluation.db?mode=ro', uri=True)`` that wrote
      its REPORT to ``/tmp`` via ``open(...,'w').write(...)`` or ``csv.writer``;
      ``sys.stdout.write(open('discussions/…/events.jsonl').read())``, denied for writing to
      STDOUT; and a file-count under ``discussions/`` written to ``/tmp``, in both ``-c`` and
      heredoc spellings. Every one of the six has a shell twin that was ALLOWED
      (``cp metrics/evaluation.db /tmp/backup.db``), so the two spellings of one act disagreed —
      the "blocks ordinary work → gets switched off → same as no guard" failure mode, in a branch
      with no override. Writes are now attributed to the operand they actually target.
      WHAT REMAINS after that fix: the python op tables are a closed enumeration in exactly the
      way the shell verb tables are (``os.open``+``os.write``, ``zipfile.ZipFile(p,'w')``,
      ``import shutil as sh`` and ``from shutil import rmtree`` are unmatched — bare names are
      excluded on purpose, since a table containing ``replace``/``copy`` would deny ordinary
      ``str.replace``); and a target that is not a literal after ONE assignment hop is
      *unresolved*, which returns ``ask`` — "we could not attribute this write", never "safe".
  When a false positive happens the agent cannot force it through; the deny reason names
  the exact token that matched so a human can see the misfire and run the command themselves.
  Net: this raises the cost of an accident and of casual bypass. It does not make destruction
  impossible, and nothing here should be described as if it did.

  WRAPPERS ARE UNWRAPPED. ``bash -c`` / ``sh -c`` / ``cmd /c`` / ``powershell -Command`` /
  ``pwsh -c`` / ``powershell -EncodedCommand`` payloads are extracted and re-checked recursively
  (depth-capped). This is not a nicety: **this machine's primary shell tool is PowerShell**, so
  ``powershell -Command '<payload>'`` was the single most natural way to run a command here and,
  until this was added, it routed around the entire guard by one word.

  GROUPING AND CONTROL FLOW ARE UNWRAPPED TOO. A leading ``(``, ``{``, ``do``, ``then``,
  ``try``, ``foreach``, ``ForEach-Object`` or ``%`` used to shadow the real command word, so
  ``for f in 1; do rm -rf discussions/…; done`` and
  ``1 | ForEach-Object { Remove-Item -Recurse -Force discussions/… }`` were ALLOWED with the
  protected path spelled out in full. See ``NON_COMMAND_LEAD_WORDS`` for the fix and for why
  *that* set is closeable (shell reserved words are fixed by the grammars) while the
  destructive-verb tables are not.

  KNOWN-OPEN AND DELIBERATELY NOT FIXED. These are real, they are reachable, and they are left
  open **on purpose**: each fix would be one more entry in a closed enumeration, and shipping it
  would re-inflate exactly the claim the SCOPE note above retracts. Disclosing them is worth
  more than a table that looks complete:
    * ``perl -i`` is unmatched while ``sed -i`` is matched — one act, two spellings, two
      verdicts. Adding ``perl`` invites ``ruby -i``, ``php -i``, and the next one.
    * ``chmod``'s Windows twins (``attrib -r``, ``Set-ItemProperty -Name IsReadOnly``) are
      unmatched — including the PowerShell primitive for UN-sealing a sealed ``events.jsonl``.
      Note what makes this survivable: un-sealing is caught after the fact by the Layer 1
      integrity check, which reports a sealed record that stopped being sealed.
    * ``Path.replace`` is unmatched while its siblings ``Path.rename`` and ``os.replace`` are
      matched. This is the one python-table exclusion made on purpose, and it is named here
      because a deliberate exclusion is the one most owed a sentence.
    * ``eval``, background ``&`` placement, here-strings, PowerShell splatting, and aliases
      defined in a profile are all untested.
  The honest summary is the SCOPE note: this raises the cost of an accident. Anyone who wants
  through, gets through.

  ACTIVATION: this guard only runs if ``.claude/settings.json`` wires this validator onto a
  PreToolUse matcher covering **both** shell tools — ``"matcher": "Bash|PowerShell"``. Matching
  only ``Bash`` leaves the ``PowerShell`` tool unrouted, which on this repo's primary shell is the
  larger half of the hole. That file is developer-applied. Until it is wired, every function below
  is dead code and the bypass it describes remains open.
"""

import base64
import binascii
import json
import os
import re
import sys
import time
from pathlib import Path


def deny(reason: str) -> None:
    """Output a deny decision and exit."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def ask(reason: str) -> None:
    """Output an ask decision and exit."""
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


# --- Secret patterns ---
SECRET_PATTERNS = [
    (
        "generic secret",
        re.compile(
            r"(?i)(api[_-]?key|secret|password|token|credential)\s*[=:]\s*[\"']\s*[a-zA-Z0-9+/]{20,}"
        ),
    ),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    (
        "JWT token",
        re.compile(r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"),
    ),
    ("GitHub personal access token", re.compile(r"ghp_[a-zA-Z0-9]{36}")),
    (
        "private key",
        re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "exported secret",
        re.compile(
            r"(?i)export\s+(API_KEY|SECRET|PASSWORD|TOKEN|CREDENTIAL|AWS_|PRIVATE_KEY)=[\"']\s*[a-zA-Z0-9+/]{20,}"
        ),
    ),
    ("Slack token", re.compile(r"xox[bpsa]-[a-zA-Z0-9-]{10,}")),
    (
        "Bearer token",
        re.compile(r"(?i)(?:bearer|authorization)\s*[=:]\s*(?:bearer\s+)?[a-zA-Z0-9_.+/=-]{20,}"),
    ),
    ("Anthropic API key", re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}")),
    ("OpenAI API key", re.compile(r"sk-proj-[a-zA-Z0-9_-]{20,}")),
    ("GCP API key", re.compile(r"AIzaSy[a-zA-Z0-9_-]{33}")),
    ("GCP OAuth token", re.compile(r"ya29\.[a-zA-Z0-9_-]{50,}")),
]

# --- Protected file patterns ---
PROTECTED_PATTERNS = [".git/", ".env", "metrics/evaluation.db", ".claude/settings.json"]

# --- Append-only Layer 1 logs (Write/Edit AND Bash) ---
# ``discussions/`` as a whole is deliberately NOT added to PROTECTED_PATTERNS: transcripts and
# artifacts under a discussion are legitimately authored with Write/Edit (hand-relayed reviews do
# exactly that). What is never legitimate is authoring or rewriting ``events.jsonl`` — it is the
# machine-written append-only event log, produced solely by scripts/ (create_discussion.py
# touches it, log_event.py appends, close_discussion.py seals it read-only).
APPEND_ONLY_SUFFIX = "events.jsonl"
# The one file under discussions/ that framework commands legitimately write from a shell.
DISCUSSION_STATE_FILE = "state.json"


def is_append_only_log(file_path: str) -> bool:
    """True if the path is a Layer 1 append-only event log (``discussions/**/events.jsonl``)."""
    normalized = file_path.replace("\\", "/").lower()
    return "discussions/" in normalized and normalized.endswith(APPEND_ONLY_SUFFIX)


# ---------------------------------------------------------------------------
# Bash command guard
# ---------------------------------------------------------------------------
# DENY vs ASK — the call, and why.
#
# ``deny`` is absolute: the tool call never runs and there is no override in-session. ``ask``
# stops the call and hands the decision to a human. ``ask`` is the weaker, recoverable choice —
# EXCEPT in a headless/auto-approving session, where there may be no human to answer; we have not
# verified how ``ask`` resolves under ``--permission-mode bypassPermissions``, and this framework
# runs such sessions (scripts/session_supervisor.py). Treat ``ask`` as "probably stops it".
#
# So: ``deny`` is reserved for paths where the loss is irreversible or where the write would
# expand the agent's own permissions, AND where a measurement showed no legitimate shell use:
#   - ``discussions/``      Layer 1, immutable/append-only (Principle #4, ADR-0027 suchness).
#   - ``.git/``             direct surgery on repository internals.
#   - ``metrics/evaluation.db``  Layer 2. File-level destruction (rm/mv/truncate/redirect) and
#                           row/schema-destroying SQL (DELETE/DROP/ALTER) deny — measured: no
#                           documented workflow issues those. Non-destructive DML (UPDATE,
#                           INSERT) only ASKS, because `/promote` legitimately UPDATEs this DB
#                           from an inline `python -c`. Denying it outright would break a
#                           shipped command, and a guard that breaks shipped commands gets
#                           switched off — which is the same as having no guard.
#   - ``.claude/settings.json``  the permission surface — Principle #7, developer-applied only.
#   - ``.claude/hooks/``    the execution surface reachable from that permission surface.
# ``ask`` is used for ``.env``, where a developer overwrite is a plausible legitimate act, and for
# SQL this guard cannot read (``sqlite3 db < script.sql``) — "ask" there means *unreadable*, not
# *judged safe*.
#
# APPENDING. An earlier draft carved out ``>>`` into ``discussions/`` on the reasoning that
# "Layer 1 is append-only, not write-never". That carve-out has been REMOVED, for three measured
# reasons:
#   1. Nothing uses it. ``grep -rnE '>>\s*[^ ]*discussions/' .claude/ scripts/ CLAUDE.md docs/``
#      returns 0 hits, so the carve-out protected no workflow — it was asserted, not measured,
#      and it was the only design decision in this guard with no measurement behind it.
#   2. It was internally inconsistent. ``echo x >> …/events.jsonl`` was allowed while the exactly
#      equivalent ``echo x | tee -a …/events.jsonl`` was denied (``tee`` is an all-args verb) and
#      the PowerShell equivalent ``Add-Content`` was allowed only because nobody had listed it.
#      All three now agree: refused. ``add-content``/``ac`` were added to the verb table for this.
#   3. It inverted the two halves of this very validator. The Write/Edit half denies
#      ``discussions/**/events.jsonl`` unconditionally — that one file is the whole reason the
#      Write/Edit half exists — so the shell half was strictly *weaker* than the file half on the
#      single file both were written to protect. Shell appends now deny too.
# The sanctioned appender is unaffected: ``scripts/log_event.py`` is a program invocation, not a
# shell redirect, and never matched.
#
# RESIDUAL ASYMMETRY, stated rather than smoothed over: the two halves are still not identical.
# Write/Edit denies only ``discussions/**/events.jsonl``; the shell half denies everything under
# ``discussions/`` except ``state.json``. That is deliberate — a shell command names directories
# (``rm -rf discussions/2026-08-07``), so file-level precision is not available to it — but it
# does mean ``Write`` to ``discussions/…/transcript.md`` is allowed while ``>>`` to the same file
# is refused. Nobody should describe these two halves as "the same rule".

BASH_DENY_DIRS = ("discussions", ".git", ".claude/hooks")
BASH_DENY_FILES = ("metrics/evaluation.db", ".claude/settings.json")

# WHY BOTH SHELL DIALECTS ARE ENUMERATED.
# An earlier draft of this guard knew POSIX verbs only. Measured against it, every one of
# ``Remove-Item -Recurse -Force discussions\...``, ``Clear-Content …/events.jsonl``,
# ``Set-Content …/events.jsonl -Value ''``, ``'x' | Out-File metrics/evaluation.db``,
# ``Copy-Item /tmp/f.db metrics/evaluation.db``, ``Move-Item discussions/… C:/tmp/gone``,
# ``del …\events.jsonl`` and ``rd /s /q discussions`` returned ALLOW — 0 of 20 probed
# PowerShell/cmd shapes were caught. This repo's declared primary shell is PowerShell and the
# agent has a ``PowerShell`` tool distinct from ``Bash``, so a POSIX-only table is not a partial
# guard on this platform; it is an unlocked back door standing beside a locked front one.

# Commands where EVERY path argument is a destruction target.
DESTRUCTIVE_ALL_ARGS = {
    # --- POSIX ---
    "rm",
    "unlink",
    "shred",
    "truncate",
    "chmod",
    "chown",
    "mv",
    "move",
    "tee",
    "dd",
    # --- PowerShell cmdlets + their aliases, and cmd.exe builtins (DESTROY class) ---
    "remove-item",
    "ri",
    "rd",
    "rmdir",
    "del",
    "erase",
    "move-item",
    "mi",
    "rename-item",
    "rni",
    "ren",
    "rename",
    # --- PowerShell writers (WRITE class): they create or overwrite the named file ---
    "set-content",
    "sc",
    "out-file",
    "clear-content",
    "clc",
    # ``Add-Content`` is the PowerShell ``>>``. It is listed for the same reason ``tee`` is: see
    # the APPENDING note above — all three appenders now agree instead of two of three leaking.
    "add-content",
    "ac",
}
# Commands where only the LAST path argument is written (source args are only read).
DESTRUCTIVE_DEST_ONLY = {
    "cp",
    "copy",
    "install",
    "rsync",
    "copy-item",
    "cpi",
    "xcopy",
    "robocopy",
}
# ``robocopy SOURCE DEST [file …]`` and ``xcopy SOURCE DEST`` name the destination SECOND, not
# last. The generic "last argument is the target" rule therefore read the FILE FILTER as the
# destination: MEASURED, ``robocopy C:/tmp discussions/2026-08-07 *.jsonl`` returned ALLOW while
# the two-argument ``xcopy C:/tmp/x discussions/2026-08-07`` denied — the same act, two verdicts,
# from a verb that was ON the table. That is worse than an unlisted verb, because the education
# row counts these among the words it claims to cover.
_DEST_IS_SECOND_ARG = {"robocopy", "xcopy"}
# Two operation classes, because ``discussions/`` treats them differently — see _classify_path.
#   DESTROY: the path stops existing, or its bytes/permissions are replaced wholesale.
#   WRITE:   a file is created or overwritten at that path.
# ``Set-Content``/``Out-File``/``Clear-Content`` are WRITE, matching how ``>`` truncation is
# already classified: the sole behavioural difference between the two classes is the
# ``discussions/**/state.json`` carve-out, and treating a PowerShell writer differently from the
# ``>`` that does the identical thing would be an inconsistency with no safety benefit.
DESTROY_VERBS = {
    "rm",
    "unlink",
    "shred",
    "truncate",
    "chmod",
    "chown",
    "mv",
    "move",
    "dd",
    "remove-item",
    "ri",
    "rd",
    "rmdir",
    "del",
    "erase",
    "move-item",
    "mi",
    "rename-item",
    "rni",
    "ren",
    "rename",
}
# ``git`` subcommands that delete or overwrite working-tree files.
DESTRUCTIVE_GIT_SUBCOMMANDS = {"rm", "clean", "checkout", "restore", "reset"}

# Statements are separated by ``;`` ``&&`` ``||`` ``&`` / newline; stages within one statement by
# ``|``. The distinction matters: in ``find discussions … | xargs rm`` the destroyed path is named
# in an *upstream* stage of the same pipeline, not in the ``rm`` stage's own arguments.
_STATEMENT_SPLIT = re.compile(r"\|\||&&|[;\n&]")
_PIPE_SPLIT = re.compile(r"\|")
_TOKEN_RE = re.compile(r"\"[^\"]*\"|'[^']*'|\S+")
# A redirection: ``>`` or ``>>`` followed by a target. ``(?![&>])`` skips ``2>&1`` and ``>>>``.
_REDIRECT_RE = re.compile(r"(>{1,2})\s*(?![&>])(\"[^\"]*\"|'[^']*'|[^\s;|&<>]+)")

_SQLITE_CLI_RE = re.compile(r"(?<![\w./\\-])sqlite3(?:\.exe)?(?![\w.-])", re.IGNORECASE)
# SQL that destroys rows or schema. MEASURED: nothing in .claude/commands, .claude/skills or
# scripts/ issues any of these against evaluation.db —
#   grep -rniE '(delete from|drop table|alter table)' .claude/commands/ .claude/skills/  -> 0 hits
# ADR-0032 independently records `grep -rn 'DELETE FROM findings' scripts/` -> EXIT=1, no match.
# CITED BY CONTENT, NOT BY LINE NUMBER, ON PURPOSE: an earlier draft of this comment said
# "ADR-0032:497"; that claim is at line 589 today. A line number in a living document is a
# citation that rots silently, which is the exact defect class this guard's own review flagged.
# Re-locate with: grep -n "DELETE FROM findings" docs/adr/ADR-0032-*.md
# so denying them costs no documented workflow. This is the shape of today's incident.
_SQL_DESTRUCTIVE_RE = re.compile(
    r"(?i)\b(?:delete\s+from|drop\s+(?:table|index|view|trigger|database)|alter\s+table"
    r"|truncate\s+table|replace\s+into)\b"
)
# SQL that writes without destroying. MEASURED: `/promote` legitimately runs UPDATE against
# evaluation.db from an inline `python -c` block —
#   grep -rhoiE '\b(UPDATE [a-z_]+)\b' .claude/commands/ .claude/skills/   -> 40 hits, all UPDATE
# Denying this class would break a documented framework command, so it is "ask", not "deny".
# That is a correction to an earlier draft of this guard which denied all DML; the earlier
# justification had only surveyed `sqlite3`-CLI usage and missed the inline-python callers.
_SQL_WRITE_RE = re.compile(
    r"(?i)\b(?:update|insert\s+into|vacuum|attach|reindex"
    r"|create\s+(?:table|index|view|trigger|virtual))\b"
)
# Inline python: both ``python -c "..."`` and the heredoc form ``python - <<'PY' ... PY``.
# The heredoc form is not exotic — it is how an agent typically does bulk file surgery.
_PY_INLINE_RE = re.compile(
    r"(?<![\w./\\-])(?:python|python3|py)(?:\.exe)?\s+(?:\S+\s+)*?(?:-c(?![\w-])|<<)",
    re.IGNORECASE | re.DOTALL,
)
# --- Wrapper shells: a whole command hidden inside another command's argument ---
# EVERY one of these takes the REST of the line as its payload, so the capture is ``.+`` rather
# than a single token: ``cmd /c rd /s /q discussions`` and ``powershell -Command Clear-Content x``
# are both legal unquoted. Capturing one token would have re-checked ``rd`` alone and allowed it.
# Each family gets its own pattern instead of one alternation, because the flag spellings collide:
# ``bash -e -c '…'`` must not read ``-e`` as PowerShell's ``-EncodedCommand``.
#
# PowerShell accepts unambiguous parameter-name prefixes, so ``-Command`` may be typed ``-c``,
# ``-com`` or ``-command``, and ``-EncodedCommand`` as ``-e``, ``-enc`` or ``-encodedcommand``.
# Those six spellings are matched; a prefix nobody spells (``-comm``) is an enumeration gap of
# the same family the docstring already names.
#
# COMBINED SHORT FLAGS. POSIX shells accept ``-c`` fused into a single-dash cluster, and people
# type it: MEASURED, ``bash -lc '<payload>'``, ``bash -ec …`` and ``bash -euxc …`` all returned
# ALLOW against the pre-fix pattern, which required a standalone ``-c``. The cluster is matched by
# requiring ``c`` to be the LAST letter of a SINGLE-dash option (``-(?!-)\w*c``), which is where
# the payload actually follows. ``(?!-)`` keeps long options out: ``bash --norc -c '…'`` ends in
# ``c`` too, and matching ``--norc`` would have captured ``-c '…'`` as the payload and re-checked
# the wrong string.
_POSIX_DASH_C_RE = re.compile(
    r"(?<![\w./\\-])(?:bash|sh|zsh|dash)(?:\.exe)?(?:\s+-[\w-]+)*?\s+-(?!-)\w*c(?![\w-])\s+(.+)",
    re.IGNORECASE | re.DOTALL,
)
_CMD_SLASH_C_RE = re.compile(
    r"(?<![\w./\\-])cmd(?:\.exe)?(?:\s+/[\w:]+)*?\s+/[ck](?![\w:])\s+(.+)",
    re.IGNORECASE | re.DOTALL,
)
# ``(?:\s+-flag(?:\s+value)?)*?`` skips ``-NoProfile``, ``-ExecutionPolicy Bypass`` etc.
_PS_PRE_FLAGS = r"(?:\s+-[\w:.-]+(?:\s+(?![-\"'])[^\s]+)?)*?"
_PS_COMMAND_RE = re.compile(
    r"(?<![\w./\\-])(?:powershell|pwsh)(?:\.exe)?" + _PS_PRE_FLAGS + r"\s+-c(?:om(?:mand)?)?"
    r"(?![\w:.-])\s+(.+)",
    re.IGNORECASE | re.DOTALL,
)
_PS_ENCODED_RE = re.compile(
    r"(?<![\w./\\-])(?:powershell|pwsh)(?:\.exe)?"
    + _PS_PRE_FLAGS
    + r"\s+-e(?:nc(?:odedcommand)?)?"
    r"(?![\w:.-])\s+[\"']?([A-Za-z0-9+/=]+)",
    re.IGNORECASE,
)
# ``sqlite3 db < script.sql`` / ``.read script.sql``: the SQL lives in a file this hook never
# opens, so the DELETE/UPDATE split below cannot be applied. Detected so it can be ASKed rather
# than silently allowed — see the CANNOT list. The ``<`` pattern requires the operand to look like
# a path (contain ``.`` or ``/``) so that ``"SELECT * FROM t WHERE n < 5"`` is not mistaken for a
# redirection; ``<<`` heredocs are excluded by the surrounding lookarounds.
_SQL_INPUT_REDIRECT_RE = re.compile(r"(?<![<>])<(?!<)\s*[\"']?[\w~-]*[./\\][\w./\\-]*")
_SQL_DOT_READ_RE = re.compile(r"(?<![\w.])\.(?:read|import)(?![\w])", re.IGNORECASE)
# Directory-changing commands. Tracked so ``cd X && rm -rf Y`` resolves Y against X — see
# _join_cwd, and see the CANNOT list for why the ACROSS-CALLS version is unfixable here.
CD_COMMANDS = {"cd", "chdir", "pushd", "set-location", "sl"}
# Words that prefix a real command without being one (``sudo rm``, ``... | xargs rm``).
WRAPPER_COMMANDS = {"sudo", "env", "nohup", "time", "xargs", "command", "nice", "stdbuf", "doas"}

# --- Grouping and control flow: the parser bug, not an enumeration gap ---
# MEASURED against the pre-fix code, all of these returned ALLOW with the protected path spelled
# out in full — no obfuscation, no indirection:
#   ``( rm -rf discussions/2026-08-07 )``            ``{ rm -rf discussions/2026-08-07; }``
#   ``for f in 1; do rm -rf discussions/…; done``    ``if true; then rm -rf discussions/…; fi``
#   ``while true; do … done``  ``until false; do … done``
#   ``1 | ForEach-Object { Remove-Item -Recurse -Force discussions/… }``
#   ``foreach ($i in 1) { … }``  ``try { … } catch { }``  ``1 | % { Clear-Content … }``
#   ``if ($true) { Clear-Content …/events.jsonl }``  ``(cd discussions && rm -rf 2026-08-07)``
# The cause was one line: the command-word scan took the FIRST non-flag token of a segment, so a
# leading ``do`` / ``then`` / ``try`` / ``ForEach-Object`` / ``(`` shadowed the real command word.
# Every verb was on the table; the parser never reached it.
#
# WHY THIS SET IS CLOSEABLE AND THE VERB TABLES ARE NOT. These are shell RESERVED WORDS and
# grouping punctuation — fixed by the two grammars (POSIX sh defines its reserved words; so does
# PowerShell's parser), not by what anyone thinks of. The set of *destructive commands*, by
# contrast, is unbounded, which is why this file stops adding to it. Skipping a token here can
# only make the scan look FURTHER for a command, so it can add detections and never remove one.
# MEASURED: this set is disjoint from every destructive-verb table (pinned by a test), so no real
# verb is shadowed by it.
SHELL_GROUPING_CHARS = "(){}"
NON_COMMAND_LEAD_WORDS = {
    # POSIX sh reserved words
    "if",
    "then",
    "elif",
    "else",
    "fi",
    "for",
    "while",
    "until",
    "do",
    "done",
    "case",
    "esac",
    "in",
    "select",
    "function",
    "!",
    "[[",
    "]]",
    "[",
    # PowerShell keywords
    "foreach",
    "try",
    "catch",
    "finally",
    "switch",
    "begin",
    "process",
    "end",
    "param",
    "filter",
    "trap",
    "data",
    "dynamicparam",
    "return",
    # PowerShell block-taking pipeline cmdlets and their aliases: the destructive call lives
    # inside the script block, so the cmdlet name is a wrapper exactly like ``xargs``.
    "foreach-object",
    "where-object",
    "%",
    "?",
}
# ---------------------------------------------------------------------------
# Inline python: WHICH OPERAND is the target, not merely which verb appears
# ---------------------------------------------------------------------------
# THE DEFECT THIS REPLACED. The first draft asked two INDEPENDENT questions — "does this inline
# python contain a write/destroy verb anywhere?" and "does the command text mention a protected
# path anywhere?" — and denied on the conjunction. It never checked that the write *targeted* the
# protected path. That is the "blocks ordinary work → gets switched off → same as no guard"
# failure mode this guard's own education row defines, and ``deny`` has no in-session override.
#
# MEASURED against the pre-fix code, six read-only shapes ALL returned deny:
#   1. ``python -c "import shutil; shutil.copy('metrics/evaluation.db','/tmp/scratch.db')"``
#      — the copy-the-DB-to-a-scratch-path idiom this repo's own task briefs mandate so that
#      analysis never touches Layer 2;
#   2. ``sqlite3.connect('file:metrics/evaluation.db?mode=ro', uri=True)`` … ``open('/tmp/o.json',
#      'w').write(json.dumps(rows))`` — the mandated READ-ONLY URI connection, denied for where it
#      wrote its report;
#   3. the same shape ending in ``csv.writer(open('/tmp/o.csv','w')).writerows(rows)``;
#   4. ``python -c "import sys; sys.stdout.write(open('discussions/a/events.jsonl').read())"``
#      — denied for writing to STDOUT;
#   5. ``open('/tmp/out.txt','w').write(str(len(list(pathlib.Path('discussions').rglob('*')))))``;
#   6. the heredoc spelling of 5.
# Every one of those has a shell twin that was ALLOWED (``cp metrics/evaluation.db /tmp/backup.db``
# → allow, pinned by a test), so the two spellings of one act disagreed.
#
# THE RULE NOW: find each write/destroy CALL SITE, extract the operand that call actually writes
# to (its receiver for ``Path(...).write_text()``, its last argument for ``shutil.copy``, its first
# for ``open(..., 'w')``), and classify only that operand. A protected path elsewhere in the
# program — in a read-only ``connect()``, in a ``rglob()`` scan, in the content being written — is
# no longer a hit.
#
# RESIDUAL LIMITS, stated rather than smoothed over (see the docstring's false-positive paragraph):
#   * these tables are a closed enumeration exactly like the shell verb tables — ``os.open`` +
#     ``os.write``, ``zipfile.ZipFile(p,'w')``, ``import shutil as sh``, and
#     ``from shutil import rmtree`` are not matched (bare names are deliberately excluded: a
#     method table containing ``replace``/``copy`` would deny ordinary ``str.replace`` calls);
#   * an operand that is not a literal is resolved ONE hop through an assignment
#     (``p = Path('discussions')/…`` then ``p.write_text(…)``, which is how ``/review`` writes
#     ``state.json``). Two hops, a loop variable, or a computed name is *unresolved*, and an
#     unresolved target in a program that also mentions a protected path returns **ask** — meaning
#     "we could not attribute this write", never "we judged it safe". That is the same word, with
#     the same meaning, as the opaque-SQL branch.
_PY_STRING_RE = re.compile(r"'([^'\n]*)'|\"([^\"\n]*)\"")
_PY_CALL_SITE_RE = re.compile(r"(?<!\w)((?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*)\s*\(")
_PY_NAME_RE = re.compile(r"[A-Za-z_]\w*")
# A quoted ``open`` mode. Only positions AFTER the first argument are tested, so ``open('a')``
# (a file literally named ``a``) is not misread as append mode.
_PY_MODE_RE = re.compile(r"^[rwxabt+U]{1,4}$")
# Callables whose FIRST argument is a path and whose mode decides whether it is a write.
_PY_OPEN_NAMES = {"open", "io.open", "codecs.open"}
# Dotted callables whose target is one or more ARGUMENTS.
#   "all"   — every argument is a target (``os.rename`` names both ends).
#   "last"  — only the final argument is written; earlier ones are read (``shutil.copy``).
#   "first" — only the first argument is a path; the rest is a mode/length.
_PY_ARG_OPS: dict[str, tuple[str, str]] = {
    "os.remove": ("destroy", "all"),
    "os.unlink": ("destroy", "all"),
    "os.rmdir": ("destroy", "all"),
    "os.removedirs": ("destroy", "all"),
    "os.truncate": ("destroy", "first"),
    "os.chmod": ("destroy", "first"),
    "os.rename": ("destroy", "all"),
    "os.renames": ("destroy", "all"),
    "os.replace": ("destroy", "all"),
    "shutil.rmtree": ("destroy", "all"),
    "shutil.move": ("destroy", "all"),
    "shutil.copy": ("write", "last"),
    "shutil.copyfile": ("write", "last"),
    "shutil.copy2": ("write", "last"),
    "shutil.copytree": ("write", "last"),
}
# Method calls whose target is the RECEIVER (``Path('x').write_text('')`` — the path is what the
# method is called ON, and the argument is CONTENT, so the argument must NOT be classified: that
# is the same "-Value carries data, not a path" rule the PowerShell parser already applies).
#   "receiver+args" is used only where the argument is genuinely a second path (``Path.rename``).
# ``write``/``writelines`` are deliberately ABSENT: a writable file object can only come from an
# ``open`` in the same program, which IS matched, so listing them adds no information and was the
# single largest false-positive source (it fired on ``sys.stdout.write``).
_PY_METHOD_OPS: dict[str, tuple[str, str]] = {
    "unlink": ("destroy", "receiver"),
    "rmdir": ("destroy", "receiver"),
    "truncate": ("destroy", "receiver"),
    "chmod": ("destroy", "receiver"),
    "rename": ("destroy", "receiver+args"),
    "write_text": ("write", "receiver"),
    "write_bytes": ("write", "receiver"),
}


def _py_string_literals(fragment: str) -> list[str]:
    """Every single- or double-quoted string literal in a fragment of python source, in order."""
    out: list[str] = []
    for match in _PY_STRING_RE.finditer(fragment):
        out.append(match.group(1) if match.group(1) is not None else match.group(2))
    return out


def _balanced_parens(text: str, index: int) -> str:
    """Inner text of the parenthesis group opening at ``index``. Quote-aware."""
    depth = 0
    quote = ""
    position = index
    while position < len(text):
        char = text[position]
        if quote:
            if char == "\\":
                position += 2
                continue
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[index + 1 : position]
        position += 1
    return text[index + 1 :]


def _split_top_level_args(inner: str) -> list[str]:
    """Split a call's argument text on top-level commas, ignoring commas inside quotes/brackets."""
    args: list[str] = []
    depth = 0
    quote = ""
    start = 0
    for position, char in enumerate(inner):
        if quote:
            if char == quote:
                quote = ""
            continue
        if char in "\"'":
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            args.append(inner[start:position])
            start = position + 1
    tail = inner[start:]
    if tail.strip() or args:
        args.append(tail)
    return args


def _receiver_expression(text: str, dot: int) -> str:
    """The expression a method call at ``text[dot] == '.'`` is invoked on.

    Walks LEFT over a balanced trailer chain: ``pathlib.Path('discussions/a/e.jsonl')`` for
    ``….unlink()``, ``(Path('discussions') / 'x')`` for ``….write_text()``, or the bare name
    ``state_path`` (which the caller then resolves one hop through its assignment).
    """
    closers = {")": "(", "]": "[", "}": "{"}
    position = dot - 1
    while position >= 0 and text[position].isspace():
        position -= 1
    end = position + 1
    while position >= 0:
        char = text[position]
        if char in closers:
            opener, depth = closers[char], 0
            while position >= 0:
                if text[position] == char:
                    depth += 1
                elif text[position] == opener:
                    depth -= 1
                    if depth == 0:
                        position -= 1
                        break
                position -= 1
            continue
        if char.isalnum() or char in "_.":
            position -= 1
            continue
        break
    return text[position + 1 : end]


def _py_assignment_rhs(program: str, name: str) -> str:
    """The right-hand side of the first ``name = …`` in the program, or ``""``.

    ONE hop only, and deliberately so — this exists to resolve the shape ``/review`` actually
    uses (``state_path = pathlib.Path('discussions') / … / 'state.json'`` then
    ``state_path.write_text(…)``), not to become a dataflow analyser inside a PreToolUse hook.
    """
    match = re.search(rf"(?<![\w.]){re.escape(name)}\s*=(?!=)\s*([^\n;]+)", program)
    return match.group(1) if match else ""


def _py_candidate_paths(window: str, program: str) -> list[str]:
    """Path candidates for one target operand, or ``[]`` when the operand is not a literal.

    Multiple literals in ONE operand are joined with ``/`` rather than classified separately,
    because that is what they mean: ``Path('discussions') / '2026-08-07' / 'D' / 'state.json'``
    and ``os.path.join('discussions', '2026-08-07')`` are single paths spelled in pieces.
    Classifying the pieces separately would see a bare ``'discussions'`` and deny the
    ``state.json`` write ``/review`` depends on — the carve-out only reads on the joined form.
    """
    literals = _py_string_literals(window)
    if not literals:
        name = window.strip()
        if _PY_NAME_RE.fullmatch(name):
            literals = _py_string_literals(_py_assignment_rhs(program, name))
    if not literals:
        return []
    return ["/".join(literals)] if len(literals) > 1 else literals


def _py_has_write_mode(args: list[str], first: int) -> bool:
    """True if an ``open``-shaped call's mode argument creates, truncates or appends.

    ``first`` is the index the mode may start at, and it differs by spelling: ``open(path, 'w')``
    puts the mode SECOND, while ``Path(path).open('w')`` puts it FIRST because the path moved to
    the receiver. Reading the wrong slot silently allows one of the two spellings — measured: it
    let ``Path('discussions/a/events.jsonl').open('w').write('')`` through.
    """
    for arg in args[first:]:
        for literal in _py_string_literals(arg):
            if _PY_MODE_RE.fullmatch(literal) and any(flag in literal for flag in "wax"):
                return True
    return False


def _py_call_ops(program: str) -> list[tuple[str, list[str]]]:
    """Every write/destroy call site in an inline python program, as ``(op, target_operands)``.

    A method call is NOT detected by "is the preceding character a dot": the call-site pattern
    matches a whole dotted chain, so ``p.write_text(…)`` arrives as the single name
    ``p.write_text`` with a newline before it. Testing the preceding character therefore missed
    every bare-name receiver — measured: it allowed the ``/review``-shaped
    ``p = Path('discussions')/'a'/'events.jsonl'`` … ``p.write_text('')``. The dot INSIDE the
    matched name is located instead, so both spellings resolve to the same receiver.
    """
    found: list[tuple[str, list[str]]] = []
    for match in _PY_CALL_SITE_RE.finditer(program):
        name = match.group(1)
        short = name.rsplit(".", 1)[-1]
        args = _split_top_level_args(_balanced_parens(program, match.end() - 1))
        # ``chained`` = the match began immediately after a dot, i.e. the receiver is an
        # expression that already closed (``Path(p).open('w')``). Without it, that call arrives as
        # the bare name ``open`` and is mistaken for the BUILTIN ``open`` — whose mode sits one
        # argument later — so the write mode is looked for in an empty slot and the call is
        # allowed. Measured: that let ``Path('discussions/a/events.jsonl').open('w')`` through.
        chained = match.start() > 0 and program[match.start() - 1] == "."
        if "." in name:
            dot = match.start() + len(name) - len(short) - 1
        elif chained:
            dot = match.start() - 1
        else:
            dot = -1

        if name in _PY_ARG_OPS and not chained:
            op, which = _PY_ARG_OPS[name]
            targets = args[-1:] if which == "last" else args[:1] if which == "first" else args
            found.append((op, targets))
        elif name in _PY_OPEN_NAMES and not chained:
            if _py_has_write_mode(args, 1):
                found.append(("write", args[:1]))
        elif dot >= 0 and short == "open":
            if _py_has_write_mode(args, 0):
                found.append(("write", [_receiver_expression(program, dot)]))
        elif dot >= 0 and short in _PY_METHOD_OPS:
            op, which = _PY_METHOD_OPS[short]
            receiver = _receiver_expression(program, dot)
            found.append((op, [receiver] + args if which == "receiver+args" else [receiver]))
    return found


def _mentions_protected(lowered: str) -> bool:
    """True if the command text names a protected path anywhere at all (attribution aside)."""
    for directory in BASH_DENY_DIRS:
        if (
            directory + "/" in lowered
            or f"'{directory}'" in lowered
            or f'"{directory}"' in lowered
        ):
            return True
    return any(filename in lowered for filename in BASH_DENY_FILES)


def _strip_token(token: str) -> str:
    """Normalize one shell token: drop quotes, backslashes to slashes, lowercase."""
    t = token.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        t = t[1:-1]
    return t.replace("\\", "/").strip().lower()


def _components(token: str) -> list[str]:
    """Path components of a normalized token, with ``.`` and empty segments dropped."""
    return [c for c in _strip_token(token).split("/") if c and c != "."]


def _has_component_run(components: list[str], target: str) -> bool:
    """True if ``target``'s components appear as a CONTIGUOUS run inside ``components``.

    Matching whole components rather than substrings is what keeps ``my-discussions-notes/`` and
    ``/tmp/scratch-metrics/evaluation.db`` out of the deny set: plain ``in`` containment matched
    both, and ``deny`` has no override, so each was an unrecoverable false positive on an
    unrelated path. Measured: this repo contains exactly one directory named ``discussions``
    (``find . -type d -name discussions -not -path './.claude/worktrees/*'`` → ``./discussions``),
    so the tightening costs no real coverage here.
    """
    target_parts = [c for c in target.split("/") if c]
    span = len(target_parts)
    return any(components[i : i + span] == target_parts for i in range(len(components) - span + 1))


def _join_cwd(prefix: str, arg: str) -> str:
    """Join a ``cd`` operand onto the tracked working directory, resolving ``..``.

    Only meaningful WITHIN one command string. See the module docstring's CANNOT list for why the
    across-tool-calls case (the shell's real, persisting cwd) is out of reach of any hook that
    sees one command at a time.
    """
    arg = _strip_token(arg)
    if not arg:
        return prefix
    absolute = arg.startswith("/") or bool(re.match(r"^[a-z]:(/|$)", arg))
    parts = [] if absolute else [p for p in prefix.split("/") if p]
    for piece in arg.split("/"):
        if piece in ("", "."):
            continue
        if piece == "..":
            if parts:
                parts.pop()
        else:
            parts.append(piece)
    return "/".join(parts)


def _classify_path(token: str, op: str = "destroy") -> tuple[str, str] | None:
    """Classify a single token as a protected path, given the operation about to hit it.

    Matching is by whole path COMPONENT (see ``_has_component_run``), not substring.

    The ``state.json`` carve-out is drawn exactly where the evidence is. ``/review``,
    ``/deliberate`` and ``/analyze-project`` each legitimately write
    ``discussions/<date>/<id>/state.json`` from an inline ``python -c`` block — measured, and an
    earlier draft of this guard denied all three, which would have broken ``/review`` on day one.
    That is the *only* shell write under ``discussions/`` found anywhere in this repo's commands,
    skills, hooks or docs, so it is the only one carved out. Everything else under
    ``discussions/`` — ``events.jsonl``, ``transcript.md``, ``artifacts/`` — is refused for both
    operation classes: those are captured reasoning, and rewriting them in place is precisely the
    suchness violation Layer 1 exists to prevent (ADR-0027). Appends are refused too; the
    ``>>`` carve-out that used to sit here was removed — see the APPENDING note above.

    Args:
        token: One shell token, possibly quoted or Windows-separated.
        op: ``"destroy"`` (removal/rename/chmod/truncate) or ``"write"`` (create/overwrite).

    Returns:
        ``(decision, label)`` with decision ``"deny"`` or ``"ask"``, or ``None`` if unprotected.
    """
    parts = _components(token)
    if not parts:
        return None
    for directory in BASH_DENY_DIRS:
        if _has_component_run(parts, directory):
            if directory == "discussions" and op == "write" and parts[-1] == DISCUSSION_STATE_FILE:
                return None
            return ("deny", directory + "/")
    for filename in BASH_DENY_FILES:
        if _has_component_run(parts, filename):
            return ("deny", filename)
    if parts[-1] == ".env":
        return ("ask", ".env")
    return None


def _tokens(segment: str) -> list[str]:
    """Split a command segment into tokens, dropping redirection operators."""
    raw = _TOKEN_RE.findall(_REDIRECT_RE.sub(" ", segment))
    return [t for t in raw if t not in (">", ">>")]


def _strip_grouping(token: str) -> str:
    """Drop shell grouping punctuation from a token's edges.

    ``_TOKEN_RE`` splits on whitespace only, so ``(rm`` and ``2026-08-07)`` arrive as single
    tokens with the bracket fused on. Stripping the edges is what lets ``(rm -rf discussions)``
    resolve to the command ``rm`` and the operand ``discussions`` — before this, the fused
    bracket made the command word unrecognizable AND broke the whole-component path match.
    Quoted tokens are left alone so a literal ``"(x)"`` argument is not silently rewritten.
    """
    stripped = token.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in "\"'":
        return stripped
    return stripped.strip(SHELL_GROUPING_CHARS).strip()


# PowerShell passes paths BY NAME at least as often as positionally, and passes non-path data by
# name too. A flat "drop every ``-`` token" split gets both cases wrong in opposite directions:
#   - ``Copy-Item -Destination metrics/evaluation.db -Path /tmp/f.db`` — the write target is not
#     the last positional token, so a last-arg rule reads the SOURCE and allows the overwrite;
#   - ``Set-Content notes.md -Value 'see discussions/2026-08-07'`` — the *content* looks like a
#     path argument, so a keep-every-non-flag-token rule denies an entirely ordinary write.
# So parameter names are interpreted, not discarded.
#   value params: the following token is DATA — skip it (false-positive control).
#   target params: the following token is the WRITE DESTINATION — record it as such.
# Any other ``-flag`` is dropped and its follower is treated positionally, which is what the POSIX
# verbs need (``truncate -s 0 FILE``, ``chmod -R 666 DIR``, ``sed -i.bak SCRIPT FILE``).
_PS_VALUE_PARAMS = {
    "-value",
    "-inputobject",
    "-encoding",
    "-filter",
    "-include",
    "-exclude",
    "-delimiter",
    "-width",
    "-stream",
    "-itemtype",
}
_PS_TARGET_PARAMS = {"-destination", "-dest", "-filepath", "-newname", "-target", "-outfile"}
# ``-Path``/``-LiteralPath`` need no entry: the flag is dropped and its operand falls through to
# the positional list, which is exactly right — for ``Remove-Item -Path X`` that operand IS the
# destruction target, and for ``Copy-Item -Path X`` a source operand is harmless in a list whose
# last-or-named element is what gets checked.


def _parse_segment(segment: str) -> tuple[str, list[str], list[str]]:
    """Split one pipeline stage into ``(command, positional_args, destination_args)``.

    Wrapper words (``sudo``, ``xargs``…) are stripped so the *real* command word is returned.
    ``destination_args`` holds operands introduced by an explicit destination parameter
    (``-Destination``, ``-FilePath``); those also appear in ``positional_args``, because for an
    all-args verb every operand is a target anyway.
    """
    tokens = _tokens(segment)
    index = 0
    command = ""
    saw_keyword = False
    paren_depth = 0
    while index < len(tokens):
        raw_token = tokens[index]
        index += 1
        # Inside a keyword's parenthesised header (``foreach ($i in 1)``, ``if ($true)``) —
        # consume to the matching close. See the header note below for why this is scoped to
        # keywords instead of to every ``(``.
        if paren_depth > 0:
            paren_depth = max(0, paren_depth + raw_token.count("(") - raw_token.count(")"))
            continue
        token = _strip_grouping(raw_token)
        # Bare grouping punctuation (``(``, ``{``, ``}``) strips to nothing.
        if not token:
            continue
        if token.startswith("-"):
            continue
        word = _strip_token(token).rsplit("/", 1)[-1]
        if word in WRAPPER_COMMANDS:
            continue
        # A reserved word or a block-taking cmdlet PRECEDES the real command; keep scanning.
        # See NON_COMMAND_LEAD_WORDS for why this set is closeable and the verb tables are not.
        if word in NON_COMMAND_LEAD_WORDS:
            saw_keyword = True
            continue
        # A ``(`` AFTER a keyword opens that keyword's header, whose contents are a condition,
        # not a command: ``foreach ($i in 1) { Remove-Item … }`` otherwise resolves its command
        # word to ``$i`` (and then to ``1``) and never reaches ``Remove-Item``.
        # Scoped to "after a keyword" on purpose — a LEADING ``(`` is a subshell whose first word
        # IS the command, and ``(cd discussions && rm -rf 2026-08-07)`` depends on reading that
        # ``cd`` to resolve the later relative path.
        if saw_keyword and raw_token.startswith("("):
            paren_depth = max(0, raw_token.count("(") - raw_token.count(")"))
            continue
        command = word
        break
    if not command:
        return ("", [], [])

    positional: list[str] = []
    destination: list[str] = []
    pending: str | None = None
    for raw_token in tokens[index:]:
        # Same edge-strip as the command scan: without it ``rm -rf 2026-08-07)`` yields the
        # operand ``2026-08-07)``, whose last path component never equals a protected one.
        token = _strip_grouping(raw_token)
        if not token:
            continue
        if pending == "skip":
            pending = None
            continue
        if pending == "target":
            pending = None
            positional.append(token)
            destination.append(token)
            continue
        if token.startswith("-"):
            flag = _strip_token(token)
            if flag in _PS_VALUE_PARAMS:
                pending = "skip"
            elif flag in _PS_TARGET_PARAMS:
                pending = "target"
            continue
        positional.append(token)
    return (command, positional, destination)


def _operative_command(segment: str) -> str:
    """The command word a segment actually runs, or ``""``."""
    return _parse_segment(segment)[0]


def _new_item_targets(tokens: list[str], args: list[str]) -> list[str]:
    """Targets for ``New-Item``, which is TWO commands wearing one name.

    ``New-Item -ItemType Directory -Force x`` is the PowerShell ``mkdir -p`` — ordinary work, and
    unmatched here exactly as POSIX ``mkdir`` is unmatched. But ``New-Item -Force x`` on an
    EXISTING FILE **overwrites it with an empty file**: that is a truncation primitive of exactly
    the incident class this guard was written for (``: > …/events.jsonl``), and its POSIX analogue
    is not ``mkdir`` but ``> file``, which this guard already matches. The earlier draft cited only
    the directory half of the case and allowed both halves on the strength of it.
    """
    item_type = ""
    for index, token in enumerate(tokens):
        if _strip_token(token) == "-itemtype" and index + 1 < len(tokens):
            item_type = _strip_token(tokens[index + 1])
            break
    if item_type.startswith("dir"):
        return []
    return args


def _target_tokens(segment: str) -> list[str]:
    """Return the tokens a segment would WRITE to, based on its command word."""
    tokens = _tokens(segment)
    command, args, destination = _parse_segment(segment)
    if not command:
        return []

    if command in ("new-item", "ni"):
        return _new_item_targets(tokens, args)
    if command in DESTRUCTIVE_ALL_ARGS:
        # ``dd of=FILE`` names its target with a key=value argument.
        return [a.split("=", 1)[1] if a.lower().startswith("of=") else a for a in args]
    if command in DESTRUCTIVE_DEST_ONLY:
        # A named ``-Destination`` wins over position; PowerShell allows either order.
        if command in _DEST_IS_SECOND_ARG:
            return destination or args[1:2]
        return destination or args[-1:]
    if command == "sed":
        in_place = any(t == "-i" or t.startswith("-i") or t == "--in-place" for t in tokens)
        # The first arg of sed is the script (``s/a/b/``), not a path.
        return args[1:] if in_place else []
    if command == "git" and args and _strip_token(args[0]) in DESTRUCTIVE_GIT_SUBCOMMANDS:
        return args[1:]
    if command == "find" and ("-delete" in tokens or "-exec" in tokens):
        return args
    return []


def _resolved_token_text(command: str) -> str:
    """Space-joined cwd-resolved forms of every token, for the whole-command mention checks.

    Section 1's SQL and inline-python checks read the RAW command text, so
    ``cd metrics && sqlite3 evaluation.db "DELETE FROM findings"`` never spells
    ``metrics/evaluation.db`` anywhere and slipped past them even after section 2's token walk
    learned to resolve ``cd``. Appending the resolved forms lets the text-level checks see what
    the token-level walk already sees. Same limit as everywhere else: within ONE command string.
    """
    resolved: list[str] = []
    cwd = ""
    for statement in _STATEMENT_SPLIT.split(command):
        if not statement.strip():
            continue
        stages = [s for s in _PIPE_SPLIT.split(statement) if s.strip()]
        if cwd:
            resolved.extend(_join_cwd(cwd, token) for stage in stages for token in _tokens(stage))
        head_command, head_args, _ = _parse_segment(stages[0]) if stages else ("", [], [])
        if head_command in CD_COMMANDS and head_args:
            cwd = _join_cwd(cwd, head_args[0])
    return " ".join(resolved)


def _unwrap_payload(payload: str) -> str:
    """Strip the quoting a wrapper shell puts around an inner command.

    ``powershell -Command "sqlite3 db \\"DELETE FROM t\\""`` arrives with the inner quotes
    backslash-escaped; leaving them escaped would hide the SQL from the checks that read raw text.
    """
    inner = payload.strip()
    if len(inner) >= 2 and inner[0] == inner[-1] and inner[0] in "\"'":
        inner = inner[1:-1]
    return inner.replace('\\"', '"').replace("\\'", "'")


def _decode_encoded_command(blob: str) -> str | None:
    """Base64-decode a ``powershell -EncodedCommand`` payload, or ``None`` if unreadable.

    PowerShell encodes as UTF-16LE; UTF-8 is tried as a fallback because agents hand-roll it. The
    decision to DECODE rather than blanket-deny is deliberate: an encoded command that touches
    nothing protected is ordinary work, and a guard that refuses a whole flag on sight is the kind
    that gets switched off. What decoding does NOT buy is depth — the decoded text then gets the
    same text matching as everything else, so obfuscation *inside* the payload survives it. When
    decoding fails the caller records ASK, meaning "unread", not "safe".
    """
    raw = blob.strip().strip("\"'")
    if not raw:
        return None
    try:
        data = base64.b64decode(raw + "=" * (-len(raw) % 4), validate=True)
    except (binascii.Error, ValueError):
        return None
    for encoding in ("utf-16-le", "utf-8"):
        try:
            text = data.decode(encoding)
        except (UnicodeDecodeError, ValueError):
            continue
        if text and not any(ch < " " and ch not in "\t\r\n" for ch in text):
            return text
    return None


def _escalate(current: str | None, candidate: str) -> str:
    """Deny outranks ask outranks nothing."""
    if current == "deny" or candidate == "deny":
        return "deny"
    return "ask"


def check_bash_command(command: str, _depth: int = 0) -> tuple[str, str] | None:
    """Heuristically classify a shell command that would modify a protected path.

    Returns ``(decision, reason)`` with decision ``"deny"`` or ``"ask"``, or ``None`` to allow.
    See the module docstring for the explicit list of what this cannot catch — it matches command
    text and is defeated by obfuscation, indirection, and any write done inside a launched program.

    Args:
        command: The literal shell command string from the Bash tool input.

    Returns:
        A ``(decision, reason)`` pair, or ``None`` if nothing protected was recognized.
    """
    if not command or not command.strip():
        return None

    decision: str | None = None
    hits: list[str] = []

    def record(verdict: str, detail: str) -> None:
        nonlocal decision
        decision = _escalate(decision, verdict)
        if detail not in hits:
            hits.append(detail)

    # --- 0. Unwrap a wrapper shell's payload and re-check it ---
    # ``powershell -Command`` is FIRST in importance, not last: this machine's primary shell tool
    # is PowerShell, so before this existed the guard was routed around by the most natural way to
    # run anything here. The nested verdict is adopted as-is (deny stays deny).
    if _depth < 3:
        for pattern, label in (
            (_POSIX_DASH_C_RE, "sh -c"),
            (_CMD_SLASH_C_RE, "cmd /c"),
            (_PS_COMMAND_RE, "powershell -Command"),
        ):
            for payload in pattern.findall(command):
                nested = check_bash_command(_unwrap_payload(payload), _depth + 1)
                if nested:
                    record(nested[0], f"nested {label} payload")
        for blob in _PS_ENCODED_RE.findall(command):
            decoded = _decode_encoded_command(blob)
            if decoded is None:
                # We could not read it. Saying "ask" here means UNREADABLE, not SAFE.
                record("ask", "powershell -EncodedCommand payload that could not be decoded")
                continue
            nested = check_bash_command(decoded, _depth + 1)
            if nested:
                record(nested[0], "nested powershell -EncodedCommand payload")

    # --- 1. Whole-command checks (run on the raw text so quoting/pipes cannot hide them) ---
    # The cwd-resolved token forms are appended so these text-level checks are ``cd``-aware too.
    lowered = (command + " " + _resolved_token_text(command)).replace("\\", "/").lower()
    inline_python = bool(_PY_INLINE_RE.search(command))

    # 1a. SQL issued against a protected database, either via the sqlite3 CLI or inline python.
    #     DESTRUCTIVE (DELETE/DROP/ALTER) denies; non-destructive DML (UPDATE/INSERT) asks,
    #     because /promote legitimately UPDATEs evaluation.db — see _SQL_WRITE_RE.
    sqlite_cli = bool(_SQLITE_CLI_RE.search(command))
    if sqlite_cli or inline_python:
        sql_verdict = None
        if _SQL_DESTRUCTIVE_RE.search(command):
            sql_verdict = "deny"
        elif _SQL_WRITE_RE.search(command):
            sql_verdict = "ask"
        if sql_verdict:
            for filename in BASH_DENY_FILES:
                if filename.endswith(".db") and filename in lowered:
                    record(sql_verdict, f"SQL write statement against {filename}")

    # 1c. SQL supplied from a FILE (``sqlite3 db < wipe.sql``, ``.read wipe.sql``). The statements
    #     are not in the command text, so 1a's deny/ask split cannot be applied at all — the
    #     script may be a report or may be the incident. MEASURED: zero uses of either shape in
    #     .claude/{commands,skills,rules,agents}, scripts/ or CLAUDE.md, so asking costs no
    #     documented workflow. This is an ASK because the content is UNKNOWN, not because it was
    #     judged benign; the docstring's CANNOT list says so in the same words.
    if sqlite_cli and (_SQL_INPUT_REDIRECT_RE.search(command) or _SQL_DOT_READ_RE.search(command)):
        for filename in BASH_DENY_FILES:
            if filename.endswith(".db") and filename in lowered:
                record("ask", f"SQL script supplied from a file against {filename} (text unread)")

    # 1b. Inline python performing a FILE write/delete on a protected path. The program is a
    #     single quoted token (or a heredoc body), so scan the raw text rather than tokens.
    #     ATTRIBUTION, not co-occurrence: each write/destroy call site is located and only the
    #     operand it actually writes to is classified — see the _py_call_ops block above for the
    #     six read-only shapes the previous co-occurrence rule denied. An operand that is not a
    #     literal (after one assignment hop) is UNRESOLVED; an unresolved target in a program that
    #     also names a protected path is "ask" — "we could not attribute this write", not "safe".
    if inline_python:
        unresolved: list[str] = []
        for op, windows in _py_call_ops(command):
            attributed = False
            for window in windows:
                for candidate in _py_candidate_paths(window, command):
                    attributed = True
                    # _classify_path carries the state.json carve-out (/review, /deliberate,
                    # /analyze-project) and applies it to the WRITE class only.
                    found = _classify_path(candidate, op=op)
                    if found:
                        record(found[0], f"inline python {op} targeting {found[1]} [{candidate}]")
            if not attributed and op not in unresolved:
                unresolved.append(op)
        if unresolved and _mentions_protected(lowered):
            for op in unresolved:
                record("ask", f"inline python {op} whose target could not be read from the text")

    # --- 2. Per-statement checks: redirections and destructive command words ---
    # Statements are walked IN ORDER so that a ``cd`` earlier in the same command string moves the
    # working directory used to resolve later relative paths. ``cd discussions/2026-08-07 &&
    # rm -rf DISC-1`` names nothing protected in the ``rm`` stage's own text; only the join does.
    # Both the bare token and the cd-resolved token are classified, so this only ever ADDS hits.
    cwd = ""
    for statement in _STATEMENT_SPLIT.split(command):
        if not statement.strip():
            continue
        stages = [s for s in _PIPE_SPLIT.split(statement) if s.strip()]
        # Every path named anywhere in this pipeline — a destructive stage that takes its
        # arguments from stdin (``… | xargs rm``) destroys whatever an upstream stage produced.
        pipeline_tokens = [t for stage in stages for t in _tokens(stage)]

        def check(target: str, op: str, describe: str, _cwd: str = "") -> None:
            """Classify a target both as written and as resolved against the tracked cwd."""
            found = _classify_path(target, op=op)
            if found:
                record(found[0], f"{describe} {found[1]} [{_strip_token(target)}]")
                return
            if not _cwd:
                return
            joined = _join_cwd(_cwd, target)
            found = _classify_path(joined, op=op)
            if found:
                record(found[0], f"{describe} {found[1]} [{joined} — resolved after 'cd {_cwd}']")

        for stage in stages:
            for operator, target in _REDIRECT_RE.findall(stage):
                # A redirection creates/overwrites a file: WRITE class. ``>>`` is NOT carved out
                # for discussions/ — see the APPENDING note at the top of this section.
                check(target, "write", f"shell redirection '{operator}' into", cwd)

            command_word = _operative_command(stage)
            op = "destroy" if command_word in DESTROY_VERBS else "write"
            if command_word == "git" or (command_word == "find" and "-delete" in _tokens(stage)):
                op = "destroy"
            targets = _target_tokens(stage)
            if not targets and len(stages) > 1 and command_word in DESTRUCTIVE_ALL_ARGS:
                targets = pipeline_tokens
            for target in targets:
                check(target, op, f"'{command_word}' targeting", cwd)

        # Apply the cd AFTER this statement's own targets are checked: in ``cd a && cd b``, the
        # operand of the second cd is relative to the first.
        head_command, head_args, _ = _parse_segment(stages[0]) if stages else ("", [], [])
        if head_command in CD_COMMANDS and head_args:
            cwd = _join_cwd(cwd, head_args[0])

    if decision is None:
        return None

    verb = "Refusing" if decision == "deny" else "Confirm before running"
    override = (
        "There is NO in-session override for a deny. "
        if decision == "deny"
        else "This is 'ask' because the intent could not be judged from the text, not because it "
        "was judged safe. "
    )
    reason = (
        f"{verb} this command: it looks like it would modify a protected path "
        f"({'; '.join(hits)}). "
        "Layer 1 (discussions/) is append-only, metrics/evaluation.db is derived state, and "
        ".git/ .claude/settings.json .claude/hooks/ are the repository and permission surfaces. "
        f"{override}"
        "If the change is genuinely needed, report it and let the developer make it. "
        "NOTE: this check reads command text only — it is a guard rail, not a sandbox, and it "
        "can misfire; the matched token is shown in brackets above, so say so (quoting it) if you "
        "believe this is a false positive."
    )
    return (decision, reason)


# --- Test file patterns (skip secret detection) ---
TEST_FILE_PATTERNS = re.compile(
    r"(test_.*\.py|.*_test\.py|.*/tests/.*\.py|.*\.test\.[tj]sx?|.*\.spec\.[tj]sx?)$"
)


def is_protected(file_path: str) -> bool:
    """Check if file is protected from modification."""
    normalized = file_path.replace("\\", "/")
    if normalized.endswith("/.env") or normalized.endswith(".env"):
        return True
    for pattern in PROTECTED_PATTERNS:
        if pattern in normalized:
            return True
    return False


def detect_secret(content: str) -> str | None:
    """Return the type of secret found in content, or None."""
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(content):
            return name
    return None


def is_test_file(file_path: str) -> bool:
    """Check if file is a test file (skip secret detection)."""
    return bool(TEST_FILE_PATTERNS.search(file_path.replace("\\", "/")))


def lock_file_path(lock_dir: Path, rel_path: str) -> Path:
    """Generate a safe lock file path from a relative file path."""
    safe_name = rel_path.replace("/", "_").replace("\\", "_")
    return lock_dir / f"{safe_name}.lock"


def try_acquire_lock(lock_dir: Path, rel_path: str, session_id: str) -> str | None:
    """Try to acquire a file lock. Returns error message or None on success."""
    lock_file = lock_file_path(lock_dir, rel_path)

    # Check for existing lock from another session
    if lock_file.exists():
        try:
            lock_data = json.loads(lock_file.read_text())
            lock_session = lock_data.get("session_id", "")
            lock_time = lock_data.get("timestamp", 0)
            time_diff = int(time.time()) - lock_time

            # Lock expires after 120 seconds
            if time_diff < 120 and lock_session != session_id and lock_session:
                return (
                    f"File '{rel_path}' is being edited by another agent. "
                    "Wait for completion or coordinate."
                )
        except (json.JSONDecodeError, OSError):
            pass  # Stale/corrupt lock, overwrite it

    # Acquire lock atomically using directory creation
    acquiring_dir = lock_file.parent / f"{lock_file.name}.acquiring"
    try:
        acquiring_dir.mkdir(exist_ok=False)
    except FileExistsError:
        return (
            "Failed to acquire file lock — another agent may be editing this file. Wait and retry."
        )

    try:
        lock_data = {
            "session_id": session_id,
            "timestamp": int(time.time()),
            "file": rel_path,
        }
        lock_file.write_text(json.dumps(lock_data))
    finally:
        try:
            acquiring_dir.rmdir()
        except OSError:
            pass

    return None


def main() -> None:
    """Main entry point for PreToolUse validation."""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", tool_input.get("path", ""))
    session_id = data.get("session_id", "")
    tool_name = data.get("tool_name", "")

    # --- Shell command guard ---
    # Only fires when .claude/settings.json wires this validator onto a matcher covering both
    # shell tools ("Bash|PowerShell"). It is INERT until the developer applies that wiring
    # (see the module docstring). Both tools are named explicitly rather than relying on the
    # has-a-command/has-no-file_path fallback, so the routing does not depend on payload shape.
    if tool_name in ("Bash", "PowerShell") or (not file_path and tool_input.get("command")):
        verdict = check_bash_command(tool_input.get("command", ""))
        if verdict:
            decision, reason = verdict
            if decision == "deny":
                deny(reason)
            ask(reason)
        return

    if not file_path:
        return

    # --- Append-only Layer 1 logs ---
    if is_append_only_log(file_path):
        deny(
            "Cannot write discussions/**/events.jsonl by hand — Layer 1 is an append-only "
            "machine-written log (Principle #4). Use scripts/log_event.py to append an event."
        )

    # --- Protected Files ---
    if is_protected(file_path):
        deny("Cannot modify protected file. Use appropriate commands or escalate.")

    # --- File Locking ---
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    lock_dir = Path(project_dir) / ".claude" / "hooks" / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)

    # Compute relative path
    normalized_file = file_path.replace("\\", "/")
    normalized_project = project_dir.replace("\\", "/")
    if normalized_file.startswith(normalized_project):
        rel_path = normalized_file[len(normalized_project) :].lstrip("/")
    else:
        rel_path = normalized_file

    lock_error = try_acquire_lock(lock_dir, rel_path, session_id)
    if lock_error:
        deny(lock_error)

    # --- Secret Detection ---
    if is_test_file(file_path):
        return

    if tool_name in ("Write", "Edit"):
        content = tool_input.get("content", tool_input.get("new_string", ""))
        if content:
            secret_type = detect_secret(content)
            if secret_type:
                ask(
                    f"Potential {secret_type} detected in content being "
                    "written. Please verify this is not sensitive data."
                )


if __name__ == "__main__":
    main()
