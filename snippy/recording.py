"""Screen recording - frames are grabbed on a background thread and piped
into a bundled ffmpeg process, which handles the mp4/mkv/flv/webm muxing.

Framework-agnostic: plain threading + subprocess, no UI toolkit dependency,
ported unchanged from the Tkinter build.
"""

import subprocess
import sys
import threading
import time

import imageio_ffmpeg
from PIL import Image, ImageGrab


class ScreenRecorder:
    """Captures a configurable source (the whole desktop, one monitor, or a
    single window - see `grab_fn`) to a video file. Pausing simply stops
    feeding frames to ffmpeg, so paused time never appears in the output
    (no frozen frames, no gap to edit out)."""

    def __init__(self, fps, codec_args, output_path, on_error=None,
                 grab_fn=None, scale=1.0):
        self.fps = fps
        self.codec_args = codec_args
        self.output_path = output_path
        self.on_error = on_error
        self.grab_fn = grab_fn or (lambda: ImageGrab.grab(all_screens=True))
        self.scale = scale if scale and 0 < scale < 1.0 else 1.0
        self.is_recording = False
        self.paused = False
        self.size = None
        self._proc = None
        self._thread = None
        self._stop_event = threading.Event()
        self._start_time = None
        self._paused_elapsed = 0.0
        self._pause_started = None

    def start(self):
        probe = self.grab_fn()
        if probe is None:
            raise RuntimeError("Recording source is not available.")
        w, h = probe.size
        if self.scale != 1.0:
            w, h = max(2, round(w * self.scale)), max(2, round(h * self.scale))
        w -= w % 2  # even dimensions required by yuv420p
        h -= h % 2
        self.size = (w, h)

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ffmpeg_exe, "-y", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{w}x{h}", "-r", str(self.fps), "-i", "-",
               *self.codec_args, "-r", str(self.fps), self.output_path]
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL,
                                      creationflags=creationflags)
        self.is_recording = True
        self.paused = False
        self._start_time = time.perf_counter()
        self._paused_elapsed = 0.0
        self._pause_started = None
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        interval = 1.0 / self.fps
        frames_written = 0
        try:
            while not self._stop_event.is_set():
                if self.paused:
                    time.sleep(0.02)
                    continue
                # How many fps-slots of *active* (unpaused) time should
                # already have a frame by now? If capture keeps up this is
                # always frames_written+1; if it falls behind (a big/multi
                # -monitor grab takes longer than 1/fps), skip straight to
                # grabbing rather than sleeping - there's nothing to wait for.
                target_frames = int(self.elapsed() / interval) + 1
                if target_frames <= frames_written:
                    time.sleep(interval / 4)
                    continue
                try:
                    frame = self.grab_fn()
                except Exception as exc:
                    if self.on_error:
                        self.on_error(str(exc))
                    return
                if frame is None:
                    if self.on_error:
                        self.on_error("Recording source is no longer "
                                      "available (window closed?).")
                    return
                if self.scale != 1.0:
                    # record_scale downsamples every frame to a fixed
                    # target size regardless of small native-size wobble,
                    # so this also absorbs a resized recorded window for
                    # free.
                    frame = frame.resize(self.size, Image.Resampling.BILINEAR)
                elif frame.size != self.size:
                    # e.g. the recorded window was resized - re-frame onto
                    # the original canvas instead of erroring on the pipe's
                    # fixed-size raw-frame contract.
                    padded = Image.new("RGB", self.size, (0, 0, 0))
                    padded.paste(frame.convert("RGB"), (0, 0))
                    frame = padded
                frame_bytes = frame.convert("RGB").tobytes()
                # Duplicate this frame for every slot that elapsed while it
                # was being captured, so the encoded timeline (frame count /
                # fps) always tracks real active recording time. Without
                # this, a capture that can't keep up with the requested fps
                # (common on large/multi-monitor grabs at a high fps target)
                # gets compressed into a much shorter, sped-up clip, since
                # ffmpeg assumes every frame it receives is exactly 1/fps
                # long regardless of how long it actually took to arrive.
                target_frames = max(target_frames,
                                    int(self.elapsed() / interval) + 1)
                while frames_written < target_frames and \
                        not self._stop_event.is_set():
                    self._proc.stdin.write(frame_bytes)
                    frames_written += 1
        except (BrokenPipeError, OSError) as exc:
            if self.on_error:
                self.on_error(str(exc))

    def pause(self):
        if not self.paused:
            self.paused = True
            self._pause_started = time.perf_counter()

    def resume(self):
        if self.paused:
            self.paused = False
            self._paused_elapsed += time.perf_counter() - self._pause_started
            self._pause_started = None

    def elapsed(self):
        if self._start_time is None:
            return 0.0
        now = time.perf_counter()
        paused = self._paused_elapsed
        if self.paused and self._pause_started:
            paused += now - self._pause_started
        return max(0.0, now - self._start_time - paused)

    def stop(self):
        self.is_recording = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        if self._proc:
            try:
                self._proc.stdin.close()
            except OSError:
                pass
            try:
                self._proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        return self.output_path
