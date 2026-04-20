"""Dictate — voice-to-text for Claude Code, integrated into Summon.

Two hotkeys (hold-to-talk):
  Right Ctrl + '  → "Dictate Now": paste into focused window immediately
  Right Ctrl + ;  → "Dictate for Claude": queue transcription, auto-paste
                    next time iTerm2 becomes frontmost

Transcription uses whisper-cli with ggml-large-v3-turbo.bin (local, offline).
Audio feedback via built-in macOS sounds (Pop/Tink/Glass).
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import rumps
import sounddevice as sd
from scipy.io import wavfile

import Quartz
from AppKit import NSWorkspace, NSSound

# ─────────────────────────── Paths & constants ─────────────────────────── #

HOME = Path.home()
SUMMON = HOME / ".claude" / "summon"
MODEL = SUMMON / "models" / "ggml-large-v3-turbo.bin"
WHISPER_BIN = "/opt/homebrew/bin/whisper-cli"
DICTATE_LOG = SUMMON / "dictate.log"
TRANSCRIPTIONS_LOG = SUMMON / "logs" / "transcriptions.jsonl"
STATE_FILE = SUMMON / "dictate_state.json"

TMP_WAV = Path("/tmp/dictate.wav")
TMP_TXT_PREFIX = Path("/tmp/dictate")  # whisper adds .txt

# Audio
SAMPLE_RATE = 16000  # whisper's native rate
CHANNELS = 1
DTYPE = "int16"
MAX_RECORDING_SEC = 120  # safety cap
MIN_RECORDING_SEC = 0.4  # below this, discard (accidental tap)

# Hotkeys — macOS virtual keycodes
KEY_SEMICOLON = 41
KEY_QUOTE = 39
RIGHT_CTRL_MASK = 0x2000  # NX_DEVICERCTLKEYMASK

# Modes
MODE_NOW = "now"        # paste into focused window immediately
MODE_CLAUDE = "claude"  # queue for iTerm

# Target for Claude-mode paste
ITERM_BUNDLE = "com.googlecode.iterm2"

# Queue config
QUEUE_SEPARATOR = "\n"
QUEUE_TTL_SEC = 600  # 10 min — clear stale queue

# Sounds
SOUND_START = "Pop"
SOUND_END = "Tink"
SOUND_PASTE = "Glass"

# Default config (persisted to STATE_FILE)
DEFAULT_CONFIG = {
    "master_enabled": True,       # master toggle for the whole dictate feature
    "dictate_now_enabled": True,
    "dictate_claude_enabled": True,
    "sounds_enabled": True,
    "auto_paste_now": True,       # Dictate Now → auto-paste (vs clipboard-only)
}


# ─────────────────────────── Logging ─────────────────────────── #

def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        DICTATE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(DICTATE_LOG, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def log_transcription(mode: str, text: str, duration_sec: float) -> None:
    try:
        TRANSCRIPTIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(TRANSCRIPTIONS_LOG, "a") as f:
            f.write(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "mode": mode,
                "duration_sec": round(duration_sec, 2),
                "text": text,
            }) + "\n")
    except Exception:
        pass


# ─────────────────────────── Sounds ─────────────────────────── #

_sound_cache: dict[str, NSSound] = {}

def play_sound(name: str, enabled: bool = True) -> None:
    if not enabled:
        return
    try:
        s = _sound_cache.get(name)
        if s is None:
            s = NSSound.soundNamed_(name)
            _sound_cache[name] = s
        if s is not None:
            s.stop()
            s.play()
    except Exception as e:
        log(f"sound error: {e!r}")


# ─────────────────────────── Recorder ─────────────────────────── #

class Recorder:
    """Captures mic input into an in-memory buffer. Thread-safe start/stop."""

    def __init__(self) -> None:
        self._stream: sd.InputStream | None = None
        self._frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._start_ts: float = 0.0

    def start(self) -> bool:
        with self._lock:
            if self._stream is not None:
                return False
            self._frames = []
            try:
                self._stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype=DTYPE,
                    callback=self._callback,
                )
                self._stream.start()
                self._start_ts = time.time()
                log("recorder: start")
                return True
            except Exception as e:
                log(f"recorder start error: {e!r}")
                self._stream = None
                return False

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        try:
            self._frames.append(indata.copy())
        except Exception as e:
            log(f"recorder callback error: {e!r}")

    def stop(self) -> tuple[np.ndarray | None, float]:
        """Stop recording. Returns (audio_int16, duration_sec)."""
        with self._lock:
            if self._stream is None:
                return None, 0.0
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                log(f"recorder stop error: {e!r}")
            finally:
                self._stream = None
            duration = time.time() - self._start_ts
            if not self._frames:
                return None, duration
            audio = np.concatenate(self._frames, axis=0).flatten()
            log(f"recorder: stop ({duration:.2f}s, {len(audio)} samples)")
            return audio, duration


# ─────────────────────────── Transcriber ─────────────────────────── #

def transcribe(audio: np.ndarray) -> str:
    """Run whisper-cli on audio (int16 mono 16kHz). Returns plain text."""
    wavfile.write(str(TMP_WAV), SAMPLE_RATE, audio)
    try:
        subprocess.run(
            [
                WHISPER_BIN,
                "-m", str(MODEL),
                "-f", str(TMP_WAV),
                "-l", "en",
                "-nt",
                "-otxt",
                "-of", str(TMP_TXT_PREFIX),
                "--no-prints",
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as e:
        log(f"whisper failed: {e.stderr.decode(errors='ignore')[:200]}")
        return ""
    except Exception as e:
        log(f"whisper error: {e!r}")
        return ""

    txt_path = TMP_TXT_PREFIX.with_suffix(".txt")
    try:
        text = txt_path.read_text().strip()
    except Exception:
        text = ""
    return text


# ─────────────────────────── Paster ─────────────────────────── #

def copy_to_clipboard(text: str) -> None:
    p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
    p.communicate(text.encode("utf-8"))


def paste_via_cmd_v() -> None:
    """Simulate ⌘V in the focused app."""
    subprocess.run(
        ["osascript", "-e",
         'tell application "System Events" to keystroke "v" using command down'],
        check=False,
    )


# ─────────────────────────── Focus watcher ─────────────────────────── #

def frontmost_bundle() -> str | None:
    try:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return None
        return str(app.bundleIdentifier())
    except Exception:
        return None


# ─────────────────────────── Hotkey tap ─────────────────────────── #

class HotkeyTap:
    """CGEventTap that detects Right-Ctrl + ; / ' as hold-to-talk triggers.

    Runs its own CFRunLoop on a background thread. Callbacks fire on that
    thread — they should be fast and dispatch work elsewhere.
    """

    def __init__(self, on_down, on_up) -> None:
        self.on_down = on_down  # (mode) -> None
        self.on_up = on_up      # (mode) -> None
        self._tap = None
        self._runloop_source = None
        self._thread: threading.Thread | None = None
        self._active_mode: str | None = None  # which mode is currently held

    def start(self) -> bool:
        self._thread = threading.Thread(target=self._run, daemon=True, name="dictate-hotkeys")
        self._thread.start()
        # Give the tap a moment to install; if it failed we'll see in logs.
        time.sleep(0.1)
        return self._tap is not None

    def _run(self) -> None:
        event_mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown) |
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp) |
            Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
        )
        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            event_mask,
            self._callback,
            None,
        )
        if not self._tap:
            log("hotkey tap: CGEventTapCreate returned NULL — check Input Monitoring permission")
            return

        self._runloop_source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(),
            self._runloop_source,
            Quartz.kCFRunLoopCommonModes,
        )
        Quartz.CGEventTapEnable(self._tap, True)
        log("hotkey tap: installed")
        Quartz.CFRunLoopRun()

    def _callback(self, proxy, event_type, event, refcon):  # noqa: ARG002
        try:
            # If the tap is disabled by the system (e.g. timeout), re-enable it.
            if event_type in (Quartz.kCGEventTapDisabledByTimeout,
                              Quartz.kCGEventTapDisabledByUserInput):
                Quartz.CGEventTapEnable(self._tap, True)
                return event

            flags = Quartz.CGEventGetFlags(event)
            right_ctrl_down = bool(flags & RIGHT_CTRL_MASK)

            if event_type == Quartz.kCGEventFlagsChanged:
                # If right-ctrl got released while we were recording, stop.
                if not right_ctrl_down and self._active_mode is not None:
                    mode = self._active_mode
                    self._active_mode = None
                    self.on_up(mode)
                return event

            if event_type in (Quartz.kCGEventKeyDown, Quartz.kCGEventKeyUp):
                keycode = Quartz.CGEventGetIntegerValueField(
                    event, Quartz.kCGKeyboardEventKeycode
                )
                if keycode not in (KEY_SEMICOLON, KEY_QUOTE):
                    return event

                mode = MODE_CLAUDE if keycode == KEY_SEMICOLON else MODE_NOW

                if event_type == Quartz.kCGEventKeyDown:
                    if right_ctrl_down and self._active_mode is None:
                        self._active_mode = mode
                        self.on_down(mode)
                        return None  # consume
                    return event  # not our combo — pass through

                # keyUp
                if self._active_mode == mode:
                    self._active_mode = None
                    self.on_up(mode)
                    return None  # consume
                return event
        except Exception as e:
            log(f"hotkey callback error: {e!r}")
        return event


# ─────────────────────────── Controller ─────────────────────────── #

@dataclass
class DictateState:
    recording_mode: str | None = None  # MODE_NOW / MODE_CLAUDE / None
    transcribing: bool = False
    queue: list[str] = field(default_factory=list)
    queue_ts: float = 0.0  # when most-recent item was added


def load_config() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text())
        merged = {**DEFAULT_CONFIG, **data}
        return merged
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(cfg, indent=2))
    except Exception as e:
        log(f"save_config error: {e!r}")


class DictateController:
    """Owns the full dictation pipeline and exposes rumps MenuItems for Summon
    to drop into its menu. One instance per running app."""

    def __init__(self) -> None:
        self.cfg = load_config()
        self.state = DictateState()
        self.recorder = Recorder()
        self._worker_lock = threading.Lock()
        self._hotkeys: HotkeyTap | None = None

        # Menu items — Summon will splice these into its menu
        self._m_now = rumps.MenuItem("Dictate Now  (Right ⌃+')", callback=self._toggle_now)
        self._m_claude = rumps.MenuItem("Dictate for Claude  (Right ⌃+;)", callback=self._toggle_claude)
        self._m_sounds = rumps.MenuItem("Audio feedback", callback=self._toggle_sounds)
        self._m_auto_paste = rumps.MenuItem("Auto-paste (Dictate Now)",
                                            callback=self._toggle_auto_paste)
        self._m_status = rumps.MenuItem("Status: idle", callback=None)
        self._m_queue_info = rumps.MenuItem("Queue: empty", callback=None)
        self._m_clear_queue = rumps.MenuItem("Clear queue", callback=self._clear_queue)
        self._m_paste_queue = rumps.MenuItem("Paste queue into iTerm now",
                                             callback=self._paste_queue_now)
        self._m_open_log = rumps.MenuItem("Open transcription log",
                                          callback=self._open_log)

        self._refresh_menu_state()

    # ── Public API for Summon ─────────────────────────────────────── #

    def menu_items(self) -> list:
        """Return a list suitable for embedding as a rumps submenu."""
        return [
            self._m_status,
            None,
            self._m_now,
            self._m_claude,
            None,
            self._m_queue_info,
            self._m_paste_queue,
            self._m_clear_queue,
            None,
            self._m_sounds,
            self._m_auto_paste,
            self._m_open_log,
        ]

    def start(self) -> bool:
        """Install the global hotkey tap."""
        if not MODEL.exists():
            log(f"model missing at {MODEL}")
            return False
        if not Path(WHISPER_BIN).exists():
            log(f"whisper-cli missing at {WHISPER_BIN}")
            return False
        self._hotkeys = HotkeyTap(on_down=self._on_hotkey_down, on_up=self._on_hotkey_up)
        ok = self._hotkeys.start()
        log(f"dictate start: hotkeys={'ok' if ok else 'failed'}")
        return ok

    def tick(self) -> None:
        """Called by Summon's main-thread timer. Handles:
          - queue TTL expiration
          - iTerm focus → paste queue
          - refresh menu labels
        """
        now = time.time()
        # Queue expiration
        if self.state.queue and (now - self.state.queue_ts) > QUEUE_TTL_SEC:
            log(f"queue expired after {QUEUE_TTL_SEC}s, clearing {len(self.state.queue)} item(s)")
            self.state.queue.clear()

        # iTerm focus triggers paste
        if self.state.queue and frontmost_bundle() == ITERM_BUNDLE:
            self._paste_queue()

        self._refresh_menu_state()

    # ── Hotkey callbacks (run on event-tap thread) ──────────────── #

    def _on_hotkey_down(self, mode: str) -> None:
        if not self.cfg.get("master_enabled", True):
            return
        if mode == MODE_NOW and not self.cfg.get("dictate_now_enabled", True):
            return
        if mode == MODE_CLAUDE and not self.cfg.get("dictate_claude_enabled", True):
            return
        if self.state.recording_mode is not None:
            return  # already recording
        if self.state.transcribing:
            return  # busy
        play_sound(SOUND_START, self.cfg.get("sounds_enabled", True))
        if self.recorder.start():
            self.state.recording_mode = mode
            log(f"hotkey down: mode={mode}")
        else:
            log("hotkey down: recorder failed to start")

    def _on_hotkey_up(self, mode: str) -> None:
        if self.state.recording_mode != mode:
            return
        self.state.recording_mode = None
        audio, duration = self.recorder.stop()
        play_sound(SOUND_END, self.cfg.get("sounds_enabled", True))
        if audio is None or duration < MIN_RECORDING_SEC:
            log(f"hotkey up: dropped short recording ({duration:.2f}s)")
            return
        if duration > MAX_RECORDING_SEC:
            log(f"hotkey up: capping at {MAX_RECORDING_SEC}s")
            audio = audio[: MAX_RECORDING_SEC * SAMPLE_RATE]
            duration = MAX_RECORDING_SEC
        self.state.transcribing = True
        threading.Thread(
            target=self._transcribe_and_dispatch,
            args=(audio, mode, duration),
            daemon=True,
            name="dictate-worker",
        ).start()

    # ── Worker: transcribe + route ──────────────────────────────── #

    def _transcribe_and_dispatch(self, audio: np.ndarray, mode: str, duration: float) -> None:
        try:
            text = transcribe(audio)
            if not text:
                log(f"empty transcription for {mode} clip ({duration:.2f}s)")
                return
            log_transcription(mode, text, duration)

            if mode == MODE_NOW:
                copy_to_clipboard(text)
                if self.cfg.get("auto_paste_now", True):
                    # Small delay so clipboard write settles before paste
                    time.sleep(0.08)
                    paste_via_cmd_v()
                    play_sound(SOUND_PASTE, self.cfg.get("sounds_enabled", True))
            else:  # MODE_CLAUDE
                self.state.queue.append(text)
                self.state.queue_ts = time.time()
                copy_to_clipboard(QUEUE_SEPARATOR.join(self.state.queue))
                log(f"queued ({len(self.state.queue)} item(s)): {text[:80]!r}")
        finally:
            self.state.transcribing = False

    # ── Queue paste ─────────────────────────────────────────────── #

    def _paste_queue(self) -> None:
        if not self.state.queue:
            return
        text = QUEUE_SEPARATOR.join(self.state.queue)
        copy_to_clipboard(text)
        time.sleep(0.08)
        paste_via_cmd_v()
        play_sound(SOUND_PASTE, self.cfg.get("sounds_enabled", True))
        log(f"pasted queue ({len(self.state.queue)} item(s)) into iTerm")
        self.state.queue.clear()

    # ── Menu callbacks ──────────────────────────────────────────── #

    def _toggle_now(self, sender: rumps.MenuItem) -> None:
        self.cfg["dictate_now_enabled"] = not self.cfg.get("dictate_now_enabled", True)
        save_config(self.cfg)
        self._refresh_menu_state()

    def _toggle_claude(self, sender: rumps.MenuItem) -> None:
        self.cfg["dictate_claude_enabled"] = not self.cfg.get("dictate_claude_enabled", True)
        save_config(self.cfg)
        self._refresh_menu_state()

    def _toggle_sounds(self, sender: rumps.MenuItem) -> None:
        self.cfg["sounds_enabled"] = not self.cfg.get("sounds_enabled", True)
        save_config(self.cfg)
        self._refresh_menu_state()

    def _toggle_auto_paste(self, sender: rumps.MenuItem) -> None:
        self.cfg["auto_paste_now"] = not self.cfg.get("auto_paste_now", True)
        save_config(self.cfg)
        self._refresh_menu_state()

    def _clear_queue(self, _sender) -> None:
        n = len(self.state.queue)
        self.state.queue.clear()
        log(f"queue cleared ({n} item(s))")
        self._refresh_menu_state()

    def _paste_queue_now(self, _sender) -> None:
        if not self.state.queue:
            rumps.notification("Dictate", "Queue empty", "Nothing to paste.")
            return
        # User invoked manually — just paste into whatever is focused.
        self._paste_queue()

    def _open_log(self, _sender) -> None:
        if TRANSCRIPTIONS_LOG.exists():
            subprocess.run(["open", str(TRANSCRIPTIONS_LOG)], check=False)
        else:
            rumps.notification("Dictate", "No transcriptions yet", "")

    # ── Menu label refresh ──────────────────────────────────────── #

    def _refresh_menu_state(self) -> None:
        self._m_now.state = 1 if self.cfg.get("dictate_now_enabled", True) else 0
        self._m_claude.state = 1 if self.cfg.get("dictate_claude_enabled", True) else 0
        self._m_sounds.state = 1 if self.cfg.get("sounds_enabled", True) else 0
        self._m_auto_paste.state = 1 if self.cfg.get("auto_paste_now", True) else 0

        if self.state.recording_mode == MODE_NOW:
            self._m_status.title = "● Recording (Dictate Now)…"
        elif self.state.recording_mode == MODE_CLAUDE:
            self._m_status.title = "● Recording (for Claude)…"
        elif self.state.transcribing:
            self._m_status.title = "⋯ Transcribing…"
        else:
            self._m_status.title = "Status: idle"

        n = len(self.state.queue)
        if n == 0:
            self._m_queue_info.title = "Queue: empty"
        else:
            self._m_queue_info.title = f"Queue: {n} item(s) — will paste on iTerm focus"

    # ── Public status accessor for Summon title ────────────────── #

    def title_suffix(self) -> str:
        """Returns a short emoji suffix Summon can append to its title."""
        if self.state.recording_mode is not None:
            return "🔴"
        if self.state.transcribing:
            return "⋯"
        if self.state.queue:
            return f"📋{len(self.state.queue)}"
        return ""

    def is_master_enabled(self) -> bool:
        return bool(self.cfg.get("master_enabled", True))

    def set_master_enabled(self, enabled: bool) -> None:
        self.cfg["master_enabled"] = bool(enabled)
        save_config(self.cfg)
        self._refresh_menu_state()
