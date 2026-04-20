"""Summon — macOS menu-bar companion for Claude Code.

Two integrated features:

  1. Double-clap launcher: a background thread listens on the default input
     device and opens a new iTerm2 Claude Code session on double-clap.
  2. Dictate (see dictate.py): Right-Ctrl + ' / ; hold-to-talk, pastes
     transcription into focused window or queues for Claude.

Menu bar icon cycles through a 4-frame radar pulse while enabled.
"""
from __future__ import annotations

import json
import subprocess
import time
from collections import deque
from pathlib import Path

import numpy as np
import rumps
import sounddevice as sd

from dictate import DictateController

HOME = Path.home()
SUMMON = HOME / ".claude" / "summon"
ICONS = SUMMON / "icons"
LAUNCHER = SUMMON / "launch_claude.sh"
STATE = SUMMON / "state.json"
LOG = SUMMON / "summon.log"

# Audio detection
SAMPLE_RATE = 44_100
BLOCK_MS = 20
BLOCK_SAMPLES = int(SAMPLE_RATE * BLOCK_MS / 1000)
BASELINE_SEC = 30
PEAK_DB_OVER_BASELINE = 18.0       # peak must tower over ambient median
SHARPNESS_RISE_DB = 14.0           # block just before must be much quieter (transient)
MIN_ABSOLUTE_PEAK_DB = -22.0       # peak must also be genuinely loud in absolute terms
DOUBLE_CLAP_MIN_MS = 150
DOUBLE_CLAP_MAX_MS = 700           # wider window so slower double-claps still register
COOLDOWN_SEC = 3.0
BASELINE_EXCLUDE_MS = 200

# Icon cycling — three animation families for the three "on" states.
#   radar_0N → double-clap launcher only
#   mic_0N   → dictate only
#   super_0N → both enabled
# radar_disabled is shown (static) when everything is off.
RADAR_FRAMES = ["radar_01", "radar_02", "radar_03", "radar_04"]
MIC_FRAMES = ["mic_01", "mic_02", "mic_03", "mic_04"]
SUPER_FRAMES = ["super_01", "super_02", "super_03", "super_04"]
DISABLED_FRAME = "radar_disabled"
FRAME_COUNT = 4
ANIM_CYCLE_SEC = 2.0
FRAME_INTERVAL = ANIM_CYCLE_SEC / FRAME_COUNT


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {"enabled": True, "skip_if_running": False}


def claude_is_running() -> bool:
    """True if a `claude --dangerously-skip-permissions` process is alive."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "claude --dangerously-skip-permissions"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def save_state(state: dict) -> None:
    try:
        STATE.write_text(json.dumps(state))
    except Exception:
        pass


class Detector:
    """Audio listener with explicit start/stop so the mic indicator disappears
    when the user disables Summon."""

    def __init__(self, on_double_clap):
        self.on_double_clap = on_double_clap
        self.stream: sd.InputStream | None = None
        self.blocks: deque[tuple[float, float]] = deque()
        self.pending_peak_ts: float | None = None
        self.last_trigger_ts: float = 0.0

    def start(self) -> bool:
        if self.stream is not None:
            return True
        try:
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                blocksize=BLOCK_SAMPLES,
                dtype="float32",
                callback=self._callback,
            )
            self.stream.start()
            log("audio stream open")
            return True
        except Exception as e:
            log(f"audio stream error: {e!r}")
            self.stream = None
            return False

    def stop(self) -> None:
        if self.stream is None:
            return
        try:
            self.stream.stop()
            self.stream.close()
        except Exception as e:
            log(f"stream close error: {e!r}")
        finally:
            self.stream = None
            self.blocks.clear()
            self.pending_peak_ts = None
            log("audio stream closed")

    def _callback(self, indata, frames, time_info, status):  # noqa: ARG002
        try:
            mono = np.asarray(indata[:, 0], dtype=np.float32)
            rms = float(np.sqrt(np.mean(mono * mono)))
            if rms <= 0:
                return
            db = 20.0 * np.log10(rms + 1e-12)
            now = time.time()
            self.blocks.append((now, db))
            # Trim to last BASELINE_SEC seconds
            cut_old = now - BASELINE_SEC
            while self.blocks and self.blocks[0][0] < cut_old:
                self.blocks.popleft()
            # Need enough history to trust the baseline
            if len(self.blocks) < 100:
                return
            # Baseline = median of blocks older than `now - BASELINE_EXCLUDE_MS`
            cutoff = now - BASELINE_EXCLUDE_MS / 1000.0
            older = [d for t, d in self.blocks if t < cutoff]
            if len(older) < 50:
                return
            baseline = float(np.median(older))
            # Gate 1: relative loudness (must tower over baseline)
            if db <= baseline + PEAK_DB_OVER_BASELINE:
                return
            # Gate 2: absolute loudness (not just quiet-room-relative)
            if db < MIN_ABSOLUTE_PEAK_DB:
                return
            # Gate 3: sharp attack — previous block must be much quieter.
            # Claps are transients; speech/music ramps in gradually.
            prev_db = self.blocks[-2][1] if len(self.blocks) >= 2 else db
            if db - prev_db < SHARPNESS_RISE_DB:
                return
            # Peak — enforce cooldown since last trigger
            if now - self.last_trigger_ts < COOLDOWN_SEC:
                return
            if self.pending_peak_ts is None:
                self.pending_peak_ts = now
                return
            gap_ms = (now - self.pending_peak_ts) * 1000.0
            if gap_ms < DOUBLE_CLAP_MIN_MS:
                # Same clap echoing through adjacent blocks — ignore.
                return
            if gap_ms > DOUBLE_CLAP_MAX_MS:
                # First clap timed out; treat current as new first clap.
                self.pending_peak_ts = now
                return
            # Double clap
            self.last_trigger_ts = now
            self.pending_peak_ts = None
            log(f"double-clap (gap={gap_ms:.0f}ms, db={db:.1f}, base={baseline:.1f}, rise={db-prev_db:.1f})")
            try:
                self.on_double_clap()
            except Exception as e:
                log(f"on_double_clap error: {e!r}")
        except Exception as e:
            log(f"callback error: {e!r}")


class SummonApp(rumps.App):
    def __init__(self) -> None:
        first_frame = str(ICONS / (RADAR_FRAMES[0] + ".png"))
        super().__init__(
            "Summon",
            icon=first_frame,
            template=True,
            quit_button=None,
        )
        state = load_state()
        self._enabled = bool(state.get("enabled", True))
        self._skip_if_running = bool(state.get("skip_if_running", False))
        self._anim_idx = 0

        self._item_enabled = rumps.MenuItem("Double-clap launcher", callback=self._toggle)
        self._item_enabled.state = 1 if self._enabled else 0
        self._item_skip = rumps.MenuItem(
            "Skip if Claude already running", callback=self._toggle_skip
        )
        self._item_skip.state = 1 if self._skip_if_running else 0

        # Dictate integration — owns its own hotkey tap + submenu items
        self.dictate = DictateController()
        self._item_dictate = rumps.MenuItem("Dictate", callback=self._toggle_dictate)
        self._item_dictate.state = 1 if self.dictate.is_master_enabled() else 0

        self._dictate_menu = rumps.MenuItem("Dictate settings")
        for item in self.dictate.menu_items():
            if item is None:
                self._dictate_menu.add(rumps.separator)
            else:
                self._dictate_menu.add(item)

        self.menu = [
            self._item_enabled,
            self._item_skip,
            rumps.MenuItem("Open Claude now", callback=self._open_now),
            None,
            self._item_dictate,
            self._dictate_menu,
            None,
            rumps.MenuItem("View log", callback=self._view_log),
            rumps.MenuItem("Quit Summon", callback=rumps.quit_application),
        ]

        self._apply_icon()

        self.detector = Detector(on_double_clap=self._launch_claude)
        if self._enabled and not self.detector.start():
            # Couldn't open the mic — start disabled instead of lying about state.
            self._enabled = False
            self._item_enabled.state = 0
            self._persist()

        # Start dictate hotkey listener
        if not self.dictate.start():
            log("dictate: failed to start (check Input Monitoring permission)")

        self._anim_timer = rumps.Timer(self._tick_anim, FRAME_INTERVAL)
        self._anim_timer.start()

        # Poll dictate for queue/iTerm-focus events + menu refresh
        self._dictate_timer = rumps.Timer(self._tick_dictate, 0.3)
        self._dictate_timer.start()

    def _any_feature_on(self) -> bool:
        return self._enabled or self.dictate.is_master_enabled()

    def _current_frames(self) -> list[str] | None:
        clap = self._enabled
        dict_on = self.dictate.is_master_enabled()
        if clap and dict_on:
            return SUPER_FRAMES
        if clap:
            return RADAR_FRAMES
        if dict_on:
            return MIC_FRAMES
        return None

    def _apply_icon(self) -> None:
        frames = self._current_frames()
        if frames is None:
            name = DISABLED_FRAME
        else:
            name = frames[self._anim_idx % len(frames)]
        self.icon = str(ICONS / (name + ".png"))
        self.template = True

    def _tick_anim(self, _sender) -> None:
        if self._current_frames() is None:
            return
        self._anim_idx = (self._anim_idx + 1) % FRAME_COUNT
        self._apply_icon()

    def _tick_dictate(self, _sender) -> None:
        try:
            self.dictate.tick()
        except Exception as e:
            log(f"dictate tick error: {e!r}")
        # Surface recording/queue state in the menu bar title
        suffix = self.dictate.title_suffix()
        self.title = suffix if suffix else None

    def _toggle_dictate(self, sender) -> None:
        new = not self.dictate.is_master_enabled()
        self.dictate.set_master_enabled(new)
        sender.state = 1 if new else 0
        log(f"toggle -> dictate_master_enabled={new}")
        self._apply_icon()

    def _persist(self) -> None:
        save_state({
            "enabled": self._enabled,
            "skip_if_running": self._skip_if_running,
        })

    def _toggle(self, sender) -> None:
        new_enabled = not self._enabled
        if new_enabled:
            if not self.detector.start():
                log("toggle: failed to start audio stream, staying disabled")
                return
        else:
            self.detector.stop()
            self._anim_idx = 0
        self._enabled = new_enabled
        sender.state = 1 if self._enabled else 0
        self._persist()
        log(f"toggle -> enabled={self._enabled}")
        self._apply_icon()

    def _toggle_skip(self, sender) -> None:
        self._skip_if_running = not self._skip_if_running
        sender.state = 1 if self._skip_if_running else 0
        self._persist()
        log(f"toggle -> skip_if_running={self._skip_if_running}")

    def _open_now(self, _sender) -> None:
        # Manual menu-bar launch always fires, regardless of the skip toggle.
        self._launch_claude(force=True)

    def _view_log(self, _sender) -> None:
        subprocess.Popen(["open", "-a", "Console", str(LOG)])

    def _launch_claude(self, force: bool = False) -> None:
        if not force and self._skip_if_running and claude_is_running():
            log("skipped launch: claude already running")
            return
        try:
            subprocess.Popen(["/bin/bash", str(LAUNCHER)])
            log("launched iTerm claude")
        except Exception as e:
            log(f"launch error: {e!r}")


if __name__ == "__main__":
    SummonApp().run()
