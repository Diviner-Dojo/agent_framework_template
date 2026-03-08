# User Notification Hook

Configure a system notification when Claude Code completes a long-running task. This hook fires on the `Notification` event, which Claude Code emits when it wants to notify the user.

## Setup

Add the appropriate hook to your `.claude/settings.json` under the `hooks` key.

### Windows (PowerShell + BurntToast)

Install the BurntToast module first:
```powershell
Install-Module -Name BurntToast -Scope CurrentUser
```

Hook configuration:
```json
{
  "hooks": {
    "Notification": [
      {
        "type": "command",
        "command": "powershell -Command \"New-BurntToastNotification -Text 'Claude Code', '$CLAUDE_NOTIFICATION_MESSAGE'\""
      }
    ]
  }
}
```

### macOS (osascript)

No dependencies needed — uses built-in AppleScript.

Hook configuration:
```json
{
  "hooks": {
    "Notification": [
      {
        "type": "command",
        "command": "osascript -e 'display notification \"'$CLAUDE_NOTIFICATION_MESSAGE'\" with title \"Claude Code\"'"
      }
    ]
  }
}
```

### Linux (notify-send)

Install `libnotify` if not present:
```bash
# Debian/Ubuntu
sudo apt install libnotify-bin

# Fedora
sudo dnf install libnotify

# Arch
sudo pacman -S libnotify
```

Hook configuration:
```json
{
  "hooks": {
    "Notification": [
      {
        "type": "command",
        "command": "notify-send 'Claude Code' \"$CLAUDE_NOTIFICATION_MESSAGE\""
      }
    ]
  }
}
```

## Environment Variables

The notification hook receives:
- `CLAUDE_NOTIFICATION_MESSAGE` — The notification message text

## Scope

This hook is configured per-user (not per-project). Add it to your user-level `.claude/settings.json`, not the project-level one.

## Testing

After configuration, trigger a notification by running a long task in Claude Code. The notification should appear when the task completes.
