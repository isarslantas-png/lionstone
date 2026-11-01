"""Audio decoding helpers (numpy)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np


def decode_mono(path: str | Path, sr: int = 8000, start: float = 0.0,
                duration: float | None = None) -> np.ndarray:
    args = ["ffmpeg", "-v", "error", "-nostdin"]
    if start > 0:
        args += ["-ss", f"{start:.3f}"]
    args += ["-i", str(path)]
    if duration:
        args += ["-t", f"{duration:.3f}"]
    args += ["-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(args, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def rms_db(x: np.ndarray, sr: int, hop: float = 0.1) -> np.ndarray:
    """Frame RMS in dBFS, one value per `hop` seconds."""
    n = max(1, int(sr * hop))
    frames = len(x) // n
    if frames == 0:
        return np.full(1, -120.0)
    f = x[: frames * n].reshape(frames, n)
    r = np.sqrt(np.mean(f * f, axis=1) + 1e-12)
    return 20 * np.log10(r + 1e-12)


def onset_envelope(x: np.ndarray, sr: int, hop: float = 0.01) -> np.ndarray:
    """Rectified log-energy derivative — robust across very different microphones."""
    e = rms_db(x, sr, hop)
    d = np.diff(e, prepend=e[:1])
    d[d < 0] = 0
    d -= d.mean()
    return d / (d.std() + 1e-9)


def xcorr_lag(a: np.ndarray, b: np.ndarray, max_lag: int) -> tuple[int, float]:
    """Lag L (samples) maximising sum a[n] * b[n + L]; returns (L, normalised peak)."""
    n = len(a) + len(b)
    size = 1 << (n - 1).bit_length()
    A = np.fft.rfft(a, size)
    B = np.fft.rfft(b, size)
    c = np.fft.irfft(np.conj(A) * B, size)
    lags = np.concatenate([np.arange(0, max_lag + 1), np.arange(-max_lag, 0)])
    vals = np.concatenate([c[: max_lag + 1], c[size - max_lag:]])
    i = int(np.argmax(vals))
    peak = float(vals[i] / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    return int(lags[i]), peak
