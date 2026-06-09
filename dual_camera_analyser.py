"""
dual_camera_analyser.py — Çift Çizgi + Ses Tabanlı Mekik Değerlendirmesi

MİMARİ:
  İki sanal çizgi kullanılır:
    start_line_y  : Başlangıç (0 m) çizgisi — kameraya yakın, büyük Y değeri
    far_line_y    : 20 m çizgisi           — kameradan uzak, küçük Y değeri

  Koşucu bölge durumu:
    NEAR   → start_line_y üstünde (büyük Y): başlangıç bölgesi
    FAR    → far_line_y altında (küçük Y)  : 20 m bölgesi
    MID    → iki çizgi arasında            : geçiş bölgesi

  Geçiş tespiti:
    NEAR → FAR girişi  = "to_far"  (başlangıçtan 20m'e)
    FAR  → NEAR girişi = "to_near" (20m'den başlangıca)

  Zamanlama:
    Gerçek bip zamanları ses analizinden gelir.
    Eğer ses tespiti başarısız olursa matematiksel zamanlayıcı devreye girer.

  Eleme:
    Ilk bip cikis sinyalidir; sonraki bipler hedef cizgi deadline'idir.
    Kosucu hedef cizgiyi bipten once gecmisse o mekik tamamlanmistir.
    Bip geldiginde hedef cizgi henuz gecilmediyse kosucu elenir.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import pandas as pd

from config import (
    LATE_TOLERANCE_SEC,
    MAX_CONSECUTIVE_LATE,
    MIN_SHUTTLE_INTERVAL_SEC,
    MASS_ELIMINATION_GUARD,
    CROSSING_HYSTERESIS_PX,
    RunnerState,
)
from timer import ShuttleTimer
from line_geometry import PerspectiveLine


# ---------------------------------------------------------------------------
# Yardımcı Veri Yapıları
# ---------------------------------------------------------------------------

class _Region(Enum):
    NEAR = "near"    # Başlangıç tarafı (büyük Y)
    FAR = "far"      # 20m tarafı (küçük Y)
    MID = "mid"      # Geçiş bölgesi


@dataclass
class DualRunnerStatus:
    """Çift kamera sisteminde bir koşucunun kümülatif durumu."""
    track_id: int
    state: RunnerState = RunnerState.ACTIVE
    total_crossings: int = 0
    far_crossings: int = 0        # 20m çizgisi geçişleri
    near_crossings: int = 0       # Başlangıç çizgisi geçişleri
    on_time_count: int = 0
    late_count: int = 0
    consecutive_late: int = 0
    expected_shuttle_idx: int = 0  # Sonraki beklenen mekik indeksi (0 tabanlı)
    last_crossing_time: float = 0.0
    elimination_time: float | None = None
    elimination_reason: str = ""
    last_completed_direction: str = ""
    last_completed_shuttle_no: int = 0
    passed_display_until: float | None = None
    last_seen_camera: str = ""
    last_seen_time: float = 0.0
    completed_shuttle_indices: set[int] = field(default_factory=set)
    crossing_log: list = field(default_factory=list)
    # crossing_log girişi:
    # {"time": float, "camera": str, "direction": str, "status": str, "shuttle_no": int}


# ---------------------------------------------------------------------------
# Ana Değerlendirici
# ---------------------------------------------------------------------------

class DualLineEvaluator:
    """
    Çift çizgi (başlangıç + 20m) ve ses tabanlı bip zamanları ile
    mekik testi değerlendirme motoru.

    Bip zamanları ses tespitinden veya matematiksel zamanlayıcıdan gelir.
    Her iki durumda aynı değerlendirme mantığı çalışır.
    """

    def __init__(
        self,
        start_line_y: int,
        far_line_y: int,
        beep_times: list[float],
        start_line_profile: PerspectiveLine | None = None,
        far_line_profile: PerspectiveLine | None = None,
        fallback_timer: ShuttleTimer | None = None,
        tolerance_sec: float = LATE_TOLERANCE_SEC,
        max_consecutive_late: int = MAX_CONSECUTIVE_LATE,
        min_shuttle_interval_sec: float = MIN_SHUTTLE_INTERVAL_SEC,
        mass_elimination_guard: bool = MASS_ELIMINATION_GUARD,
        hysteresis_px: int = CROSSING_HYSTERESIS_PX,
        start_target_side: str = "below",
        far_target_side: str = "above",
    ):
        """
        Args:
            start_line_y : Başlangıç çizgisi Y pikseli (büyük değer, alt bölge).
            far_line_y   : 20m çizgisi Y pikseli (küçük değer, üst bölge).
            beep_times   : Ses tespitinden gelen bip zamanları (s, koşu başından).
                           Boş ise fallback_timer kullanılır.
            fallback_timer: Ses tespiti başarısız olduğunda matematiksel zamanlayıcı.
            tolerance_sec: Bip sonrası tolerans süresi (saniye).
            hysteresis_px: Titreşim önleme piksel marjı.
        """
        self.start_line_y = start_line_y
        self.far_line_y = far_line_y
        self.start_line_profile = start_line_profile
        self.far_line_profile = far_line_profile
        self.tolerance_sec = tolerance_sec
        self.max_consecutive_late = max_consecutive_late
        self.min_shuttle_interval_sec = min_shuttle_interval_sec
        self.mass_elimination_guard = mass_elimination_guard
        self.hysteresis_px = hysteresis_px
        self.start_target_side = start_target_side
        self.far_target_side = far_target_side

        # Bip zamanları: ses tespiti yoksa matematiksel zamanlayıcı
        if beep_times:
            self._beep_times = beep_times
            self._using_audio = True
            print(f"[DualEval] Ses tabanlı bip zamanları: {len(beep_times)} bip")
        elif fallback_timer is not None:
            self._beep_times = fallback_timer.get_deadline_times()
            self._using_audio = False
            print(f"[DualEval] Matematiksel zamanlayıcı: {len(self._beep_times)} deadline")
        else:
            self._beep_times = []
            self._using_audio = False
            print("[DualEval] UYARI: Bip zamanı yok — değerlendirme yapılamaz.")

        # Koşucu durumları
        self._runners: dict[int, DualRunnerStatus] = {}
        # Her koşucu için son kararlı bölge
        self._last_region: dict[int, _Region] = {}
        # Son Y değeri (bölge değişimi sırasında referans için)
        self._last_y: dict[int, float] = {}
        # Çift kamera modunda her çizgi kendi kamera görüntüsünde yorumlanır.
        self._last_line_side: dict[tuple[int, str], str] = {}
        # Ayni kosucunun ayni anda iki uc cizgide tamamlanmasini engelleyen kilit.
        self._last_completed_camera: dict[int, str] = {}
        self._ignored_deadline_indices: set[int] = set()

    # ------------------------------------------------------------------
    # Genel API
    # ------------------------------------------------------------------

    def update(self, track_id: int, ankle_y: float, current_time: float):
        """Koşucu Y pozisyonunu güncelle, çizgi geçişini kontrol et."""
        if track_id not in self._runners:
            region = self._init_runner(track_id, ankle_y, current_time=current_time)
            runner = self._runners[track_id]
            initial_crossing = self._initial_crossing_if_on_target(runner, region)
            if initial_crossing is not None:
                self._on_crossing(runner, initial_crossing, current_time)
            return

        runner = self._runners[track_id]
        if runner.state == RunnerState.ELIMINATED:
            return

        self._last_y[track_id] = ankle_y
        crossing = self._detect_crossing(track_id, ankle_y)
        if crossing is not None:
            self._on_crossing(runner, crossing, current_time)

    def update_camera_line(
        self,
        track_id: int,
        ankle_x: float,
        ankle_y: float,
        current_time: float,
        target_line: str,
    ):
        """
        Tek kamera/tek çizgi güncellemesi.

        target_line="far"    → Kamera 2, 20m varışlarını (to_far) arar.
        target_line="start"  → Kamera 1, başlangıç dönüşlerini (to_near) arar.
        """
        if track_id not in self._runners:
            self._init_runner(track_id, ankle_y, current_time=current_time)

        runner = self._runners[track_id]
        if runner.state == RunnerState.ELIMINATED:
            return

        direction = "to_far" if target_line == "far" else "to_near"
        runner.last_seen_camera = "20m" if target_line == "far" else "baslangic"
        runner.last_seen_time = current_time
        side = self._line_side(ankle_y, target_line, ankle_x)
        key = (track_id, target_line)
        prev_side = self._last_line_side.get(key)
        passed_line = side == "target"

        if prev_side is None:
            self._last_line_side[key] = side
            if passed_line:
                self._on_crossing(runner, direction, current_time)
            return

        if passed_line:
            self._last_line_side[key] = side
            self._on_crossing(runner, direction, current_time)
            return

        if side != prev_side:
            self._last_line_side[key] = side

    def check_beep_deadlines(
        self,
        current_time: float,
        expected_direction: str | None = None,
    ):
        """
        Deadline geçmiş ama henüz geçiş yapılmamış koşucuları yakala.
        Her karede çağrılır; birden fazla kaçırılmış mekiği de yakalar.

        expected_direction verilirse sadece o hedef çizgiye ait deadline'lar
        kontrol edilir. Çift kamera simülasyonunda Kamera 2 görüntüsü ileriden
        okunduğu için bu ayrım, başlangıç çizgisi dönüşlerinin erken
        cezalandırılmasını engeller.
        """
        if self.mass_elimination_guard and expected_direction is not None:
            self._skip_mass_elimination_deadline(current_time, expected_direction)

        for runner in self._runners.values():
            if runner.state == RunnerState.ELIMINATED:
                continue

            # Geçmiş tüm deadline'ları işle
            while True:
                idx = runner.expected_shuttle_idx
                if idx >= len(self._beep_times):
                    break
                if idx in self._ignored_deadline_indices:
                    break

                deadline = self._beep_times[idx]
                grace = deadline + self.tolerance_sec

                if current_time <= grace:
                    break  # Deadline henüz geçmedi

                # Geçiş yapılmadan deadline geçti.
                expected_dir = "to_far" if idx % 2 == 0 else "to_near"
                if expected_direction is not None and expected_dir != expected_direction:
                    break

                cam = "20m" if expected_dir == "to_far" else "baslangic"
                if idx in runner.completed_shuttle_indices:
                    runner.completed_shuttle_indices.remove(idx)
                    runner.expected_shuttle_idx += 1
                    runner.consecutive_late = 0
                    runner.state = RunnerState.ACTIVE
                    runner.passed_display_until = None
                    runner.crossing_log.append({
                        "time": round(current_time, 3),
                        "camera": cam,
                        "direction": expected_dir,
                        "status": "AKTIF - bip geldi, gecis onaylandi",
                        "shuttle_no": idx + 1,
                    })
                    continue

                status = self._mark_late(
                    runner,
                    current_time,
                    (
                        f"{idx + 1}. mekik {cam} çizgisi bipten önce geçilmedi "
                        f"(bip {deadline:.2f}s)"
                    ),
                    warning_status="GEC - bipten once cizgi gecilmedi",
                    eliminated_status="ELENDI - bipten once cizgi gecilmedi",
                )
                runner.expected_shuttle_idx += 1
                runner.crossing_log.append({
                    "time": round(current_time, 3),
                    "camera": cam,
                    "direction": expected_dir,
                    "status": status,
                    "shuttle_no": idx + 1,
                })
                break

    def _mark_late(
        self,
        runner: DualRunnerStatus,
        current_time: float,
        elimination_reason: str,
        warning_status: str,
        eliminated_status: str,
    ) -> str:
        """Gecikme sayacını güncelle ve eşik dolduysa ele."""
        runner.late_count += 1
        runner.consecutive_late += 1
        runner.passed_display_until = None

        if runner.consecutive_late >= self.max_consecutive_late:
            runner.state = RunnerState.ELIMINATED
            runner.elimination_time = current_time
            runner.elimination_reason = elimination_reason
            return eliminated_status

        runner.state = RunnerState.ACTIVE
        return warning_status

    def _skip_mass_elimination_deadline(self, current_time: float, expected_direction: str):
        """
        Yanlis/erken ses pikleri tum aktif kosuculari ayni anda elemesin.

        Bir deadline gectiginde o hedefe hicbir kosucu ulasmamissa, bu proje
        verisinde en olasi neden ses adayinin gercek hedef bipi olmamasidir.
        Bu deadline'i tum ilgili kosucular icin atlayip sonraki biple devam eder.
        """
        active = [r for r in self._runners.values() if r.state != RunnerState.ELIMINATED]
        if not active:
            return

        pending = []
        for runner in active:
            idx = runner.expected_shuttle_idx
            if idx >= len(self._beep_times):
                continue
            expected_dir = "to_far" if idx % 2 == 0 else "to_near"
            if expected_dir != expected_direction:
                continue
            if current_time <= self._beep_times[idx] + self.tolerance_sec:
                continue
            pending.append(runner)

        if not pending or len(pending) != len(active):
            return

        idx = pending[0].expected_shuttle_idx
        if any(r.expected_shuttle_idx != idx for r in pending):
            return

        any_completed = any(
            (expected_direction == "to_far" and r.far_crossings > 0)
            or (expected_direction == "to_near" and r.near_crossings > 0)
            for r in active
        )
        if any_completed:
            return

        cam = "20m" if expected_direction == "to_far" else "baslangic"
        deadline = self._beep_times[idx]
        print(
            f"[DualEval] UYARI: {idx + 1}. mekik {cam} deadline {deadline:.2f}s "
            "toplu eleme yaratacagi icin supheli bip olarak atlandi."
        )
        self._ignored_deadline_indices.add(idx)
        for runner in pending:
            runner.crossing_log.append({
                "time": round(current_time, 3),
                "camera": cam,
                "direction": expected_direction,
                "status": "Atlandi - supheli erken bip",
                "shuttle_no": idx + 1,
            })

    def get_runner_status(self, track_id: int) -> DualRunnerStatus | None:
        return self._runners.get(track_id)

    def get_all_runner_statuses(self) -> dict[int, DualRunnerStatus]:
        return self._runners.copy()

    def get_active_count(self) -> int:
        return sum(1 for r in self._runners.values()
                   if r.state != RunnerState.ELIMINATED)

    def is_using_audio(self) -> bool:
        return self._using_audio

    def get_beep_times(self) -> list[float]:
        return self._beep_times

    def get_runner_display_state(self, track_id: int, current_time: float) -> str | None:
        runner = self._runners.get(track_id)
        if runner is None:
            return None
        if runner.state == RunnerState.ELIMINATED:
            return runner.state.value
        if runner.passed_display_until is not None and current_time < runner.passed_display_until:
            return f"GECTI M{runner.last_completed_shuttle_no}"
        return runner.state.value

    # ------------------------------------------------------------------
    # DataFrame & Raporlama
    # ------------------------------------------------------------------

    def get_results_dataframe(self) -> pd.DataFrame:
        rows = []
        for tid, st in sorted(self._runners.items()):
            rows.append({
                "Kosucu ID": tid,
                "Durum": st.state.value,
                "Toplam Gecis": st.total_crossings,
                "20m Gecis": st.far_crossings,
                "Baslangic Gecis": st.near_crossings,
                "Zamaninda": st.on_time_count,
                "Gec": st.late_count,
                "Ardisik Gec": st.consecutive_late,
                "Son Tamamlanan Yon": st.last_completed_direction or "-",
                "Son Gorulen Kamera": st.last_seen_camera or "-",
                "Eleme Zamani (s)": (
                    round(st.elimination_time, 2) if st.elimination_time else "-"
                ),
                "Eleme Nedeni": st.elimination_reason or "-",
            })
        return pd.DataFrame(rows)

    def get_detailed_log_dataframe(self) -> pd.DataFrame:
        rows = []
        for tid, st in sorted(self._runners.items()):
            for entry in st.crossing_log:
                rows.append({
                    "Kosucu ID": tid,
                    "Zaman (s)": entry["time"],
                    "Kamera": entry.get("camera", "-"),
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

        print(f"[DualEval] Raporlar kaydedildi: {output_dir}")

    # ------------------------------------------------------------------
    # Dahili Yardımcılar
    # ------------------------------------------------------------------

    def _init_runner(
        self,
        track_id: int,
        ankle_y: float,
        current_time: float = 0.0,
    ) -> _Region:
        """Yeni koşucuyu başlangıç bölgesine yerleştir."""
        runner = DualRunnerStatus(track_id=track_id)
        runner.expected_shuttle_idx = self._first_unexpired_shuttle_idx(current_time)
        self._runners[track_id] = runner
        self._last_y[track_id] = ankle_y

        # Başlangıç bölgesini belirle
        region = self._y_to_region(ankle_y)
        # İlk tespit için bölgeyi ayarla; MID ise NEAR varsay
        self._last_region[track_id] = region if region != _Region.MID else _Region.NEAR
        return region

    def _first_unexpired_shuttle_idx(self, current_time: float) -> int:
        """
        Yeni görülen bir track için geçmişte kalmış deadline'ları atla.

        YOLO/ByteTrack bazen aynı yarışmacıya ilerleyen saniyelerde yeni ID verir.
        Yeni ID'yi 0. mekikten başlatırsak sistem eski bipleri geriye dönük
        kaçırılmış sayar ve koşucu, ekranda bir sonraki bibe süre varken elenir.
        """
        idx = 0
        while idx < len(self._beep_times):
            if current_time <= self._beep_times[idx] + self.tolerance_sec:
                break
            idx += 1
        return idx

    def _initial_crossing_if_on_target(
        self,
        runner: DualRunnerStatus,
        region: _Region,
    ) -> str | None:
        """
        Yeni takip ilk kez hedef çizgi tarafında görünürse geçişi say.

        Tek video/iki kamera simülasyonunda 20m kamerası videoya ofsetli başladığı
        için atlet ilk karede zaten hedef bölgede olabilir; bu durumda bölge
        değişimi oluşmadığından klasik crossing mantığı geçişi kaçırır.
        """
        idx = runner.expected_shuttle_idx
        expected_dir = "to_far" if idx % 2 == 0 else "to_near"
        if expected_dir == "to_far" and region == _Region.FAR:
            return "to_far"
        if expected_dir == "to_near" and region == _Region.NEAR:
            return "to_near"
        return None

    def _y_to_region(self, y: float) -> _Region:
        """Y koordinatını bölgeye çevirir."""
        h = self.hysteresis_px
        if y < self.far_line_y - h:
            return _Region.FAR
        elif y > self.start_line_y + h:
            return _Region.NEAR
        return _Region.MID

    def _line_side(self, y: float, target_line: str, x: float | None = None) -> str:
        """
        Tek çizgide koşucu kutusunun alt tabanı hangi tarafta?

        Geçiş sadece alt taban çizginin hedef tarafına gerçekten geçtiğinde
        sayılır. "mid" bandı titreşim payıdır; artık geçti sayılmaz.

        Tek video simulasyonunda 20m'ye kosarken Y kuculur, baslangica
        donerken Y buyur. Iki fiziksel kamera modunda ise her iki hedef
        cizgide kosucu kameraya yaklasabilir; bu yuzden hedef taraflari
        disaridan verilebilir.
        """
        h = self.hysteresis_px
        line_y = self._line_y_at(target_line, x)
        target_side = self.far_target_side if target_line == "far" else self.start_target_side

        if target_side == "below":
            if y > line_y:
                return "target"
            if y < line_y - h:
                return "before"
        else:
            if y < line_y:
                return "target"
            if y > line_y + h:
                return "before"

        return "mid"

    def _line_y_at(self, target_line: str, x: float | None = None) -> float:
        if target_line == "far":
            if self.far_line_profile is not None and x is not None:
                return self.far_line_profile.y_at(x)
            return float(self.far_line_y)

        if self.start_line_profile is not None and x is not None:
            return self.start_line_profile.y_at(x)
        return float(self.start_line_y)

    def _detect_crossing(self, track_id: int, ankle_y: float) -> str | None:
        """
        Bölge geçiş tespiti.

        Sadece NEAR→FAR (to_far) ve FAR→NEAR (to_near) geçişleri sayılır.
        MID bölgeden geçiş sırasında last_region güncellenmez,
        böylece titreşim/salınım kaynaklı yanlış tespitler önlenir.
        """
        curr_region = self._y_to_region(ankle_y)
        prev_region = self._last_region.get(track_id, _Region.NEAR)

        if curr_region == _Region.MID:
            return None  # Geçiş bölgesinde kesin tespit yok

        if curr_region != prev_region:
            self._last_region[track_id] = curr_region
            if curr_region == _Region.FAR:
                return "to_far"
            elif curr_region == _Region.NEAR:
                return "to_near"

        return None

    def _on_crossing(self, runner: DualRunnerStatus, direction: str, current_time: float):
        """Tespit edilen bir geçişi değerlendir."""
        idx = runner.expected_shuttle_idx
        expected_dir = "to_far" if idx % 2 == 0 else "to_near"
        advance_expected = False

        # Beklenen yönde değilse atla (yanlış yönde geçiş)
        if direction != expected_dir:
            return

        if idx in runner.completed_shuttle_indices:
            return

        # Kamera etiketini belirle
        cam = "20m" if direction == "to_far" else "baslangic"
        prev_cam = self._last_completed_camera.get(runner.track_id)
        if prev_cam == cam:
            return
        if (
            prev_cam is not None
            and runner.last_crossing_time > 0
            and current_time - runner.last_crossing_time < self.min_shuttle_interval_sec
        ):
            return

        # Sayaçları güncelle
        runner.total_crossings += 1
        runner.last_crossing_time = current_time
        if direction == "to_far":
            runner.far_crossings += 1
        else:
            runner.near_crossings += 1

        # Zamanlama değerlendirmesi
        if idx < len(self._beep_times):
            deadline = self._beep_times[idx] + self.tolerance_sec
            if idx in self._ignored_deadline_indices:
                status = "Gecti - supheli bip yok sayildi"
                runner.on_time_count += 1
                runner.consecutive_late = 0
                runner.state = RunnerState.ACTIVE
                runner.passed_display_until = current_time + 0.8
                runner.completed_shuttle_indices.add(idx)
            elif current_time <= deadline:
                status = "Gecti - bipten once tamamlandi"
                runner.on_time_count += 1
                runner.consecutive_late = 0
                runner.state = RunnerState.ACTIVE
                runner.passed_display_until = deadline
                runner.completed_shuttle_indices.add(idx)
            else:
                status = self._mark_late(
                    runner,
                    current_time,
                    (
                        f"{idx + 1}. mekik {cam} çizgisi bipten sonra geçildi "
                        f"({current_time:.2f}s > {deadline:.2f}s)"
                    ),
                    warning_status="GEC - gec gecis",
                    eliminated_status="ELENDI - gec gecis",
                )
                advance_expected = True
        else:
            status = "Test Sonu"
            runner.on_time_count += 1
            runner.consecutive_late = 0
            runner.state = RunnerState.ACTIVE
            runner.passed_display_until = current_time + 0.8
            advance_expected = True

        runner.last_completed_direction = direction
        runner.last_completed_shuttle_no = idx + 1
        self._last_completed_camera[runner.track_id] = cam
        runner.crossing_log.append({
            "time": round(current_time, 3),
            "camera": cam,
            "direction": direction,
            "status": status,
            "shuttle_no": idx + 1,
        })
        if advance_expected:
            runner.expected_shuttle_idx += 1
