#!/usr/bin/env bash
# Dictate MVP — records N seconds, transcribes with whisper-cli, copies to clipboard.
# Usage: ./test_mvp.sh [seconds]  (default 5)

set -euo pipefail

DURATION="${1:-5}"
DICTATE_DIR="$HOME/.claude/dictate"
MODEL="$DICTATE_DIR/models/ggml-large-v3-turbo.bin"
WAV="/tmp/dictate_mvp.wav"
TXT="/tmp/dictate_mvp.txt"

if [[ ! -f "$MODEL" ]]; then
  echo "Model missing: $MODEL" >&2
  exit 1
fi

echo "Recording ${DURATION}s... speak now."
# Beep so you know recording started
afplay /System/Library/Sounds/Pop.aiff &

# 16kHz mono PCM — what whisper expects
sox -d -r 16000 -c 1 -b 16 "$WAV" trim 0 "$DURATION" 2>/dev/null

afplay /System/Library/Sounds/Tink.aiff &
echo "Transcribing..."

# -nt: no timestamps, -of -: write text to stdout via file prefix
whisper-cli \
  -m "$MODEL" \
  -f "$WAV" \
  -l en \
  -nt \
  -otxt \
  -of "${TXT%.txt}" 2>/dev/null

TRANSCRIPT="$(cat "$TXT" | sed 's/^ *//;s/ *$//')"
echo ""
echo "=== TRANSCRIPT ==="
echo "$TRANSCRIPT"
echo "=================="

printf '%s' "$TRANSCRIPT" | pbcopy
afplay /System/Library/Sounds/Glass.aiff &
echo "(copied to clipboard)"
