#!/bin/bash
# Open a new iTerm2 window in fullscreen and start Claude Code in it.
# After Claude boots, auto-accept the --dangerously-skip-permissions prompt
# by sending "1" — harmless no-op when the prompt has already been accepted.
osascript <<'EOF'
tell application "iTerm"
  activate
  create window with default profile
  tell current session of current window
    write text "claude --dangerously-skip-permissions"
    delay 3
    write text "1"
  end tell
  tell current window to set fullscreen to true
end tell
EOF
