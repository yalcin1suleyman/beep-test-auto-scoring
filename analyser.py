"""
analyser.py — TEK ÇİZGİ Gidiş-Dönüş Değerlendirmesi (v3)

MİMARİ DEĞİŞİKLİK:
  Eski: İki çizgi (başlangıç + 20m), her iki çizgide ayrı geçiş tespiti.
  Yeni: TEK çizgi (sadece koşucuların güvenilir göründüğü bölgede).
        Her geçiş (yukarı veya aşağı) = 1 mekik tamamlandı.

NEDEN:
  Kamera arkadan çekim yaptığında, koşucular 20m çizgisinde çok küçük
  piksel boyutuna düşüyor ve hiçbir model onları tespit edemiyor.
  Tek çizgi yaklaşımı, koşucuların görülebildiği alanda çalışır.

MANTIK:
  1. Koşucu çizgiyi YUKARI geçer (to_far) → Mekik 1 tamamlandı
  2. Koşucu uzağa gider, geri döner (bu sürede görünmez olabilir)
  3. Koşucu çizgiyi AŞAĞI geçer (to_near) → Mekik 2 tamamlandı
  4. Tekrar...

v3.1: Logging eklendi.
"""

from pathlib import Path
import pandas as pd

from config import (
    LATE_TOLERANCE_SEC,
    MAX_CONSECUTIVE_LATE,
    CROSSING_HYSTERESIS_PX,
    RunnerState,
    RunnerStatus,
)
from timer import ShuttleTimer
from logger import get_logger

log = get_logger(__name__)


class ShuttleEvaluator:
    """
    TEK ÇİZGİ gidiş-dönüş değerlendirme motoru.
    Koşucuların ayak bileği Y koordinatının tek bir yatay çizgiyi
    her geçişi bir mekik olarak sayılır.
    """

    def __init__(
        self,
        detection_line_y: int,
        shuttle_timer: ShuttleTimer,
        tolerance_sec: float = LATE_TOLERANCE_SEC,
        max_consecutive_late: int = MAX_CONSECUTIVE_LATE,
        hysteresis_px: int = CROSSING_HYSTERESIS_PX,
    ):
        """
        Args:
            detection_line_y: Tespit çizgisi Y piksel.
                              Koşucuların güvenilir tespit edilebildiği bölgede olmalı.
            shuttle_timer: Matematiksel zamanlayıcı.
            tolerance_sec: Deadline sonrası tolerans (saniye).
            max_consecutive_late: Ardışık gecikme sınırı.
            hysteresis_px: Titreşim önleme marjı.
        """
        self.detection_line_y = detection_line_y
        self.timer = shuttle_timer
        self.tolerance_sec = tolerance_sec
        self.max_consecutive_late = max_consecutive_late
        self.hysteresis_px = hysteresis_px

        # Koşucu durumları
        self._runners: dict[int, RunnerStatus] = {}
        # Son bilinen Y
        self._last_y: dict[int, float] = {}
        # Beklenen mekik indeksi
        self._expected_shuttle: dict[int, int] = {}

        # Deadline listesi
        self._deadlines = shuttle_timer.get_deadline_times()

    def update(self, track_id: int, ankle_y: float, current_time_sec: float):
        """Koşucu Y pozisyonunu güncelle, çizgi geçişini kontrol et."""
        # Yeni koşucu
        if track_id not in self._runners:
            self._runners[track_id] = RunnerStatus(track_id=track_id)
            self._last_y[track_id] = ankle_y
            self._expected_shuttle[track_id] = 0
            return

        # Elenmiş → atla
        if self._runners[track_id].state == RunnerState.ELIMINATED:
            return

        prev_y = self._last_y.get(track_id, ankle_y)
        self._last_y[track_id] = ankle_y

        # Çizgi geçiş tespiti (tek çizgi, her iki yön)
        crossing = self._detect_crossing(prev_y, ankle_y)
        if crossing is None:
            return

        runner = self._runners[track_id]
        runner.total_crossings += 1
        runner.last_crossing_time = current_time_sec
        runner.last_direction = crossing

        # Zamanlama değerlendirmesi
        expected_idx = self._expected_shuttle.get(track_id, 0)
        if expected_idx < len(self._deadlines):
            deadline = self._deadlines[expected_idx] + self.tolerance_sec
            if current_time_sec <= deadline:
                status = "Zamaninda"
                runner.on_time_count += 1
                runner.consecutive_late = 0
                runner.state = RunnerState.ACTIVE
            else:
                status = "Gec"
                runner.late_count += 1
                runner.consecutive_late += 1
                if runner.consecutive_late >= self.max_consecutive_late:
                    runner.state = RunnerState.ELIMINATED
                    runner.elimination_time = current_time_sec
                    status = "ELENDI"
                else:
                    runner.state = RunnerState.WARNING
        else:
            status = "Test Sonu"
            runner.on_time_count += 1
            runner.consecutive_late = 0

        runner.crossing_log.append({
            "time": round(current_time_sec, 3),
            "direction": crossing,
            "status": status,
            "shuttle_no": expected_idx + 1,
        })
        self._expected_shuttle[track_id] = expected_idx + 1

    def check_deadlines(self, current_time_sec: float):
        """
        Deadline geçtiğinde henüz çizgiyi geçmemiş koşucuları kontrol eder.
        NOT: Koşucu uzakta (görünmez) olabilir — toleransı GENİŞ tutuyoruz.
        """
        for track_id, runner in self._runners.items():
            if runner.state == RunnerState.ELIMINATED:
                continue

            expected_idx = self._expected_shuttle.get(track_id, 0)
            if expected_idx >= len(self._deadlines):
                continue

            deadline = self._deadlines[expected_idx]
            # Uzak tespit kaybı için ekstra tolerans: mekik süresi + normal tolerans
            # Koşucu gidip dönene kadar görünmez olabilir
            grace = deadline + self.tolerance_sec + 3.0  # +3 saniye ekstra

            if current_time_sec > grace:
                runner.late_count += 1
                runner.consecutive_late += 1
                runner.crossing_log.append({
                    "time": round(current_time_sec, 3),
                    "direction": "yok",
                    "status": "Gec (gecis yok)",
                    "shuttle_no": expected_idx + 1,
                })
                if runner.consecutive_late >= self.max_consecutive_late:
                    runner.state = RunnerState.ELIMINATED
                    runner.elimination_time = current_time_sec
                else:
                    runner.state = RunnerState.WARNING

                self._expected_shuttle[track_id] = expected_idx + 1

    def _detect_crossing(self, prev_y: float, curr_y: float) -> str | None:
        """
        TEK ÇİZGİ geçiş tespiti.

        Koşucu çizgiyi yukarı geçerse (Y azalıyor) → to_far
        Koşucu çizgiyi aşağı geçerse (Y artıyor) → to_near
        Her geçiş = 1 mekik tamamlandı.
        """
        h = self.hysteresis_px
        line_y = self.detection_line_y

        # Yukarı geçiş (to_far): koşucu çizginin altından üstüne geçti
        if prev_y > line_y + h and curr_y <= line_y:
            return "to_far"

        # Aşağı geçiş (to_near): koşucu çizginin üstünden altına geçti
        if prev_y < line_y - h and curr_y >= line_y:
            return "to_near"

        return None

    def get_runner_status(self, track_id: int) -> RunnerStatus | None:
        return self._runners.get(track_id)

    def get_all_runner_statuses(self) -> dict[int, RunnerStatus]:
        return self._runners.copy()

    def get_active_count(self) -> int:
        return sum(1 for r in self._runners.values()
                   if r.state != RunnerState.ELIMINATED)

    def get_results_dataframe(self) -> pd.DataFrame:
        rows = []
        for tid, st in sorted(self._runners.items()):
            rows.append({
                "Kosucu ID": tid,
                "Durum": st.state.value,
                "Toplam Gecis": st.total_crossings,
                "Zamaninda": st.on_time_count,
                "Gec": st.late_count,
                "Ardisik Gec": st.consecutive_late,
                "Eleme Zamani (s)": (
                    round(st.elimination_time, 2) if st.elimination_time else "-"
                ),
            })
        return pd.DataFrame(rows)

    def get_detailed_log_dataframe(self) -> pd.DataFrame:
        rows = []
        for tid, st in sorted(self._runners.items()):
            for entry in st.crossing_log:
                rows.append({
                    "Kosucu ID": tid,
                    "Zaman (s)": entry["time"],
                    "Yon": entry["direction"],
                    "Sonuc": entry["status"],
                    "Mekik No": entry["shuttle_no"],
                })
        return pd.DataFrame(rows)

    def export_results(self, output_dir: str | Path):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        summary_df = self.get_results_dataframe()
        summary_df.to_csv(output_dir / "sonuc_ozet.csv",
                          index=False, encoding="utf-8-sig")

        log_df = self.get_detailed_log_dataframe()
        log_df.to_csv(output_dir / "sonuc_detay.csv",
                      index=False, encoding="utf-8-sig")

        excel_path = output_dir / "sonuc_rapor.xlsx"
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            summary_df.to_excel(writer, sheet_name="Ozet", index=False)
            log_df.to_excel(writer, sheet_name="Detay", index=False)

        print(f"[Evaluator] Raporlar kaydedildi: {output_dir}")
