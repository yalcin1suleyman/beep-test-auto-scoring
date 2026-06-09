"""
timer.py — Matematiksel Mekik Zamanlayıcısı
Ses analizi yerine resmi beep test formülüne göre sanal bip zamanlarını hesaplar.

Formül:
    Hız (km/h) = 7.0 + (aşama - 1) * 0.5
    Bir mekik süresi (s) = 20 / (Hız * 1000 / 3600)
"""

from config import (
    SHUTTLE_DISTANCE_M,
    INITIAL_SPEED_KMH,
    SPEED_INCREMENT_KMH,
    SPEED_INCREMENT_EVERY_SHUTTLE,
    SHUTTLES_PER_LEVEL,
)


class ShuttleTimer:
    """
    Mekik testi matematiksel zamanlayıcı.
    Resmi beep test tablosuna göre her mekiğin bitiş zamanını hesaplar.
    """

    def __init__(self, start_offset_sec: float = 0.0):
        self.start_offset = start_offset_sec
        self._shuttle_deadlines: list[dict] = []
        self._build_schedule()

    def _build_schedule(self):
        """Tüm seviye ve mekikler için bitiş zamanlarını hesaplar."""
        self._shuttle_deadlines = []
        cumulative_time = self.start_offset
        global_idx = 0

        if SPEED_INCREMENT_EVERY_SHUTTLE:
            total_shuttles = sum(SHUTTLES_PER_LEVEL)
            for shuttle_idx in range(total_shuttles):
                level = shuttle_idx + 1
                speed_kmh = INITIAL_SPEED_KMH + shuttle_idx * SPEED_INCREMENT_KMH
                speed_ms = speed_kmh * 1000.0 / 3600.0
                shuttle_duration = SHUTTLE_DISTANCE_M / speed_ms
                cumulative_time += shuttle_duration
                global_idx += 1
                self._shuttle_deadlines.append({
                    "global_idx": global_idx,
                    "level": level,
                    "shuttle_in_level": 1,
                    "speed_kmh": round(speed_kmh, 1),
                    "duration_sec": round(shuttle_duration, 3),
                    "deadline_sec": round(cumulative_time, 3),
                })
            print(f"[ShuttleTimer] {global_idx} mekik zamanlandı, "
                  f"toplam süre: {cumulative_time/60:.1f} dk")
            return

        for level_idx, num_shuttles in enumerate(SHUTTLES_PER_LEVEL):
            level = level_idx + 1
            speed_kmh = INITIAL_SPEED_KMH + (level - 1) * SPEED_INCREMENT_KMH
            speed_ms = speed_kmh * 1000.0 / 3600.0
            shuttle_duration = SHUTTLE_DISTANCE_M / speed_ms

            for s in range(num_shuttles):
                cumulative_time += shuttle_duration
                global_idx += 1
                self._shuttle_deadlines.append({
                    "global_idx": global_idx,
                    "level": level,
                    "shuttle_in_level": s + 1,
                    "speed_kmh": round(speed_kmh, 1),
                    "duration_sec": round(shuttle_duration, 3),
                    "deadline_sec": round(cumulative_time, 3),
                })

        print(f"[ShuttleTimer] {global_idx} mekik zamanlandı, "
              f"toplam süre: {cumulative_time/60:.1f} dk")

    @property
    def total_shuttles(self) -> int:
        return len(self._shuttle_deadlines)

    def get_deadline_times(self) -> list[float]:
        """Tüm bitiş zamanlarını döndürür (her biri bir 'sanal bip')."""
        return [d["deadline_sec"] for d in self._shuttle_deadlines]

    def get_current_shuttle(self, t: float) -> dict | None:
        """Verilen zaman için mevcut mekik bilgisini döndürür."""
        if t < self.start_offset:
            return None
        for sh in self._shuttle_deadlines:
            if t <= sh["deadline_sec"]:
                return sh
        return None

    def get_shuttle_index_for_time(self, t: float) -> int:
        """Verilen zaman için mevcut mekik indeksini (0-tabanlı) döndürür."""
        if t < self.start_offset:
            return -1
        for i, sh in enumerate(self._shuttle_deadlines):
            if t <= sh["deadline_sec"]:
                return i
        return len(self._shuttle_deadlines)

    def get_expected_direction(self, shuttle_global_idx: int) -> str:
        """Tek=to_far (yukarı/20m), Çift=to_near (aşağı/başlangıç)."""
        return "to_far" if shuttle_global_idx % 2 == 1 else "to_near"

    def get_target_line(self, shuttle_global_idx: int) -> str:
        """Hedef çizgi: tek=20m, çift=start."""
        return "20m" if shuttle_global_idx % 2 == 1 else "start"

    def get_level_info(self, t: float) -> tuple[int, int]:
        """(level, shuttle_in_level) döndürür."""
        sh = self.get_current_shuttle(t)
        return (sh["level"], sh["shuttle_in_level"]) if sh else (0, 0)

    def print_schedule(self, max_levels: int = 3):
        """İlk N seviyenin tablosunu yazdırır."""
        print(f"\n  Svy | Mek | Hız(km/h) | Süre(s) | Bitiş(s) | Yön")
        print(f"  ----+-----+-----------+---------+----------+-------")
        for sh in self._shuttle_deadlines:
            if sh["level"] > max_levels:
                break
            d = self.get_expected_direction(sh["global_idx"])
            print(f"  {sh['level']:>3} | {sh['shuttle_in_level']:>3} | "
                  f"{sh['speed_kmh']:>9.1f} | {sh['duration_sec']:>7.3f} | "
                  f"{sh['deadline_sec']:>8.3f} | {d}")
