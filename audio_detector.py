"""
audio_detector.py — Video Sesinden Bip Tespiti
Mekik testi bip seslerini video ses kanalından otomatik olarak tespit eder.

Algoritma:
  1. ffmpeg ile video sesini mono WAV formatına çıkarır
  2. Sliding-window FFT ile bip frekans bandı (800–1500 Hz) enerjisini ölçer
  3. Enerji piklerini bip zamanları olarak döndürür
"""

import subprocess
import tempfile
import shutil
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import find_peaks

from config import (
    BEEP_FREQ_MIN_HZ,
    BEEP_FREQ_MAX_HZ,
    BEEP_MIN_GAP_SEC,
    BEEP_ENERGY_THRESHOLD_PERCENTILE,
    BEEP_STRONG_THRESHOLD_RATIO,
)


class BeepDetector:
    """
    Ses frekans analizi ile mekik testi bip seslerini tespit eder.
    ffmpeg ile video sesini WAV'a çıkarır; scipy ile analiz eder.
    """

    def __init__(
        self,
        freq_min_hz: float = BEEP_FREQ_MIN_HZ,
        freq_max_hz: float = BEEP_FREQ_MAX_HZ,
        min_gap_sec: float = BEEP_MIN_GAP_SEC,
        threshold_percentile: float = BEEP_ENERGY_THRESHOLD_PERCENTILE,
        strong_threshold_ratio: float = BEEP_STRONG_THRESHOLD_RATIO,
        sample_rate: int = 22050,
        window_ms: float = 50.0,
        hop_ms: float = 10.0,
    ):
        self.freq_min = freq_min_hz
        self.freq_max = freq_max_hz
        self.min_gap = min_gap_sec
        self.threshold_percentile = threshold_percentile
        self.strong_threshold_ratio = strong_threshold_ratio
        self.sample_rate = sample_rate
        self.window_ms = window_ms
        self.hop_ms = hop_ms

    def detect_beeps(self, video_path: Path) -> list[float]:
        """
        Video dosyasından bip zamanlarını tespit eder.

        Returns:
            Video başından itibaren bip zamanları (saniye).
            Ses çıkarılamazsa boş liste döner.
        """
        tmp_wav = Path(tempfile.gettempdir()) / "mekik_audio_tmp.wav"
        print(f"\n[BeepDetector] Ses çıkarılıyor: {video_path.name}")

        if not self._extract_audio(video_path, tmp_wav):
            print("[BeepDetector] UYARI: Ses çıkarılamadı.")
            print("  → ffmpeg kurulu olmalı. Kurmak için:")
            print("    Windows: https://ffmpeg.org/download.html (PATH'e ekleyin)")
            print("  → Matematiksel zamanlayıcıya geri dönülüyor.")
            return []

        try:
            beep_times = self._analyze_wav(tmp_wav)
        except Exception as exc:
            print(f"[BeepDetector] HATA: Ses analizi başarısız — {exc}")
            beep_times = []
        finally:
            if tmp_wav.exists():
                tmp_wav.unlink(missing_ok=True)

        return beep_times

    # ------------------------------------------------------------------
    # Dahili Yardımcılar
    # ------------------------------------------------------------------

    def _extract_audio(self, video_path: Path, out_wav: Path) -> bool:
        """ffmpeg ile video sesini mono 22050 Hz WAV olarak kaydeder."""
        ffmpeg_cmd = self._find_ffmpeg()
        if ffmpeg_cmd is None:
            print("  ffmpeg bulunamadı (PATH veya imageio-ffmpeg)")
            return False

        cmd = [
            ffmpeg_cmd, "-y",
            "-i", str(video_path),
            "-vn",          # video akışı yok
            "-ac", "1",     # mono
            "-ar", str(self.sample_rate),
            "-f", "wav",
            str(out_wav),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=180)
            ok = result.returncode == 0 and out_wav.exists() and out_wav.stat().st_size > 0
            if not ok and result.stderr:
                # ffmpeg hata mesajının son satırı yeterli
                err_lines = result.stderr.decode(errors="ignore").strip().splitlines()
                if err_lines:
                    print(f"  ffmpeg: {err_lines[-1]}")
            return ok
        except FileNotFoundError:
            print("  ffmpeg bulunamadı (PATH'e eklenmiş mi?)")
            return False
        except subprocess.TimeoutExpired:
            print("  ffmpeg zaman aşımı.")
            return False

    @staticmethod
    def _find_ffmpeg() -> str | None:
        """Sistem ffmpeg'ini veya imageio-ffmpeg paketindeki binary'yi bulur."""
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return system_ffmpeg

        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return None

    def _analyze_wav(self, wav_path: Path) -> list[float]:
        """
        Sliding-window FFT ile bip frekans bandı enerjisi analizi.
        Yüksek enerjili pikler bip anı olarak işaretlenir.
        """
        sr, data = wavfile.read(str(wav_path))

        # Stereo → mono
        if data.ndim > 1:
            data = data.mean(axis=1)

        # Float [-1, 1] normalize
        data = data.astype(np.float32)
        peak = np.abs(data).max()
        if peak > 0:
            data /= peak

        win_size = max(64, int(sr * self.window_ms / 1000.0))
        hop_size = max(1, int(sr * self.hop_ms / 1000.0))
        hann_win = np.hanning(win_size)

        frame_times: list[float] = []
        band_energies: list[float] = []

        for start in range(0, len(data) - win_size, hop_size):
            segment = data[start : start + win_size] * hann_win
            fft_mag = np.abs(np.fft.rfft(segment))
            freqs = np.fft.rfftfreq(win_size, d=1.0 / sr)

            mask = (freqs >= self.freq_min) & (freqs <= self.freq_max)
            energy = float(fft_mag[mask].mean()) if mask.any() else 0.0

            frame_times.append(start / sr)
            band_energies.append(energy)

        times = np.array(frame_times)
        energies = np.array(band_energies)

        percentile_threshold = float(np.percentile(energies, self.threshold_percentile))
        max_threshold = float(energies.max() * self.strong_threshold_ratio) if energies.size else 0.0
        threshold = max(percentile_threshold, max_threshold)
        min_dist = max(1, int(self.min_gap / (self.hop_ms / 1000.0)))

        peak_idxs, props = find_peaks(
            energies, height=threshold, distance=min_dist
        )
        beep_times = times[peak_idxs].tolist()

        print(f"[BeepDetector] {len(beep_times)} bip tespit edildi "
              f"(eşik: {threshold:.4f}, band: {self.freq_min:.0f}–{self.freq_max:.0f} Hz)")
        if beep_times:
            print(f"  İlk bip: {beep_times[0]:.2f}s | Son bip: {beep_times[-1]:.2f}s")

        return beep_times

    def print_beep_schedule(self, beep_times: list[float], max_show: int = 10):
        """İlk N bipin tablosunu yazdırır."""
        print(f"\n  {'#':>3} | {'Bip Zamanı (s)':>16} | {'Süre Farkı (s)':>16}")
        print(f"  ----+-----------------+-----------------")
        prev = 0.0
        for i, t in enumerate(beep_times[:max_show]):
            diff = t - prev if i > 0 else 0.0
            print(f"  {i+1:>3} | {t:>16.3f} | {diff:>16.3f}")
            prev = t
        if len(beep_times) > max_show:
            print(f"  ... ({len(beep_times) - max_show} bip daha)")
