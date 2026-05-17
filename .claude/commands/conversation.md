---
description: "Join or initiate a cross-project conversation. Projects exchange messages through shared-memory, waiting for each other's responses automatically. Developer only intervenes when a project needs approval for changes in its own codebase."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
argument-hint: "<start topic> | <join> | <status>"
---

# Cross-Project Conversation

You are acting as this project's representative in a cross-project dialogue. Messages
are exchanged through ~/.claude/shared-memory/conversations/. Each project writes
messages and waits for responses without developer intervention, unless you need
approval for a change in YOUR OWN codebase.

## Understanding the Arguments

The developer will invoke this command in one of three ways:

- `/conversation start <topic>` — Initiate a new conversation. You write the first message.
- `/conversation join` — Check for active conversations that include this project and join the latest one.
- `/conversation status` — Show all active conversations and their state.

## Directory Structure

```
~/.claude/shared-memory/conversations/
  CONV-YYYYMMDD-HHMMSS-<slug>/
    manifest.json
    001-<project-name>.md
    002-<other-project>.md
    ...
```

## Manifest Format

```json
{
  "conversation_id": "CONV-YYYYMMDD-HHMMSS-<slug>",
  "topic": "Human-readable topic description",
  "status": "active",
  "initiated_by": "agentic-journal",
  "participants": ["agentic-journal", "verification-portal", "agent-framework-template"],
  "created_at": "2026-04-11T18:00:00Z",
  "current_turn": "verification-portal",
  "turn_number": 2,
  "timeout_minutes": 5,
  "messages": [
    {"file": "001-agentic-journal.md", "author": "agentic-journal", "timestamp": "..."},
    {"file": "002-verification-portal.md", "author": "verification-portal", "timestamp": "..."}
  ]
}
```

## Project Name Detection

Determine this project's conversation name from the working directory:
- Look at the git remote URL or the directory name
- Map to a short readable name: `agentic-journal`, `verification-portal`, `agent-framework-template`, etc.
- Use this consistently in manifest.json and message filenames

## Starting a Conversation

When the developer says `/conversation start <topic>`:

1. Create the conversation directory:
```bash
CONV_DIR="$HOME/.claude/shared-memory/conversations"
mkdir -p "$CONV_DIR"
TIMESTAMP=$(date -u +%Y%m%d-%H%M%S)
SLUG=$(echo "<topic>" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-' | head -c 40)
CONV_ID="CONV-${TIMESTAMP}-${SLUG}"
mkdir -p "$CONV_DIR/$CONV_ID"
```

2. Ask the developer which projects should participate (or accept a list in the command).

3. Write `manifest.json` with status `active`, this project as `initiated_by`, the
   participant list, and `current_turn` set to the first participant OTHER than this
   project (since you're about to write the opening message).

4. Write the first message as `001-<this-project>.md`:
```markdown
---
author: <this-project>
timestamp: <ISO 8601>
turn: 1
topic: <topic>
---

<Your opening message — describe the topic, what you need from the other projects,
and what response you're looking for. Be specific.>
```

5. Update manifest.json with the message entry and set `current_turn` to the next
   expected responder.

6. Tell the developer: "Conversation started. Tell the other projects to run
   `/conversation join` to participate. I will wait for responses."

7. **Enter the wait loop** (see below).

## Joining a Conversation

When the developer says `/conversation join`:

1. Scan `~/.claude/shared-memory/conversations/` for active conversations:
```bash
find "$HOME/.claude/shared-memory/conversations" -name "manifest.json" -exec grep -l '"status": "active"' {} \;
```

2. For each active conversation, read `manifest.json` and check if this project is
   in the `participants` list.

3. If multiple active conversations exist, show them and ask the developer which to join.

4. If it's this project's turn (`current_turn` matches this project name):
   - Read ALL previous messages in order
   - Write your response
   - Update the manifest
   - Enter the wait loop

5. If it's NOT this project's turn:
   - Read all messages so far to build context
   - Enter the wait loop (waiting for your turn)

## Writing a Message

When it's your turn to respond:

1. Read ALL previous messages in the conversation (in order) to understand the full context.

2. Think about the topic from THIS project's perspective. Consider:
   - How does this topic affect THIS project specifically?
   - What project-specific context is relevant?
   - What concerns or questions does this project have?
   - What would you propose or agree to?

3. Write your response as `NNN-<this-project>.md` where NNN is the next message number:
```markdown
---
author: <this-project>
timestamp: <ISO 8601>
turn: <number>
topic: <topic>
in_response_to: <previous message filename>
---

<Your response. Be specific and actionable. If you need the developer to approve
something in your own codebase, say so clearly with:>

**DEVELOPER ACTION NEEDED**: <description of what needs approval in this project>

<If the conversation topic is resolved from your perspective, say:>

**STATUS**: resolved — <brief summary of outcome>

<If you need more information, say:>

**WAITING FOR**: <what you need from which project>
```

4. Update `manifest.json`:
   - Add the message to the `messages` array
   - Increment `turn_number`
   - Set `current_turn` to the next participant who needs to respond
   - If ALL participants have marked STATUS as resolved, set conversation `status` to `closed`

## Determining Next Turn

After writing a message, determine who goes next:

- If you asked a specific project a question → that project is next
- If you addressed all participants → the next participant in the list (round-robin)
- If the conversation is a back-and-forth between two projects → the other one
- If you marked STATUS as resolved → check if all participants have resolved. If yes,
  close the conversation. If no, the next unresolved participant goes.

## The Wait Loop

After writing your message (or after joining when it's not your turn), enter a polling
loop:

```bash
# Poll for new messages every 10 seconds
CONV_PATH="<path to conversation directory>"
LAST_COUNT=<current number of message files>
TIMEOUT=300  # 5 minutes
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
  CURRENT_COUNT=$(ls "$CONV_PATH"/*.md 2>/dev/null | wc -l)
  if [ "$CURRENT_COUNT" -gt "$LAST_COUNT" ]; then
    echo "NEW_MESSAGE_DETECTED"
    break
  fi
  sleep 10
  ELAPSED=$((ELAPSED + 10))
done

if [ $ELAPSED -ge $TIMEOUT ]; then
  echo "TIMEOUT"
fi
```

When a new message is detected:
1. Read the new message file(s)
2. Check `manifest.json` — is it your turn?
3. If yes → read the message, formulate a response, write it, return to wait loop
4. If no → return to wait loop (another participant may need to go first)

When timeout occurs:
1. Tell the developer: "No response received in 5 minutes. The other project may not
   have joined yet. Run `/conversation status` to check, or ask the other project to
   run `/conversation join`."

## Conversation Status

When the developer says `/conversation status`:

1. List all conversations in `~/.claude/shared-memory/conversations/`
2. For each, show: conversation ID, topic, status, participants, whose turn it is,
   message count, last message timestamp
3. Highlight any that are waiting for THIS project to respond

## Closing a Conversation

A conversation closes when:
- All participants have marked their STATUS as resolved
- The initiating project explicitly closes it
- The developer says `/conversation close`

When closing:
1. Set `status` to `closed` in manifest.json
2. Add a `closed_at` timestamp
3. Write a summary message as the final entry (optional — if the conversation
   produced decisions worth recording)

## Rules

- **NEVER write a message when it's not your turn.** Check manifest.json first.
- **NEVER modify another project's messages.** Only write new files and update manifest.json.
- **ALWAYS read ALL previous messages** before responding. Context is everything.
- **Ask the developer before making changes to your own codebase** based on the
  conversation. The conversation is a dialogue — actual code changes need developer approval.
- **Keep messages concise and actionable.** This is a working conversation, not a deliberation.
  No specialist panels, no YAML findings blocks. Just clear, direct communication between projects.
- **If you're confused about the topic**, say so in your message rather than guessing.
  The other project can clarify.
- **Timeout is 5 minutes by default.** If no response arrives, report to the developer
  rather than looping forever.
