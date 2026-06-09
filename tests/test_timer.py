"""
test_timer.py — ShuttleTimer modülü testleri
"""

import pytest
from timer import ShuttleTimer


class TestShuttleTimer:
    """ShuttleTimer testleri."""
    
    def test_timer_initialization(self):
        """Timer başlatma testi."""
        timer = ShuttleTimer(start_offset_sec=0.0)
        assert timer is not None
        assert timer.start_offset == 0.0
    
    def test_get_current_shuttle_level_1(self):
        """Level 1 seviyesindeki shuttle'ı al."""
        timer = ShuttleTimer(start_offset_sec=0.0)
        shuttle = timer.get_current_shuttle(t=0.0)
        assert shuttle is not None
        # İlk shuttle bilgisi kontrol
        assert shuttle.get("speed_kmh") == 7.0
    
    def test_get_level_info_level_1(self):
        """Level 1 bilgisini al."""
        timer = ShuttleTimer(start_offset_sec=0.0)
        level, shuttle_in_level = timer.get_level_info(t=0.0)
        assert level >= 1
    
    def test_get_deadline_times(self):
        """Deadline zamanlarını al."""
        timer = ShuttleTimer(start_offset_sec=0.0)
        deadlines = timer.get_deadline_times()
        assert deadlines is not None
        assert len(deadlines) > 0
        # İlk deadline float olmalı
        assert isinstance(deadlines[0], float)
    
    def test_timer_with_offset(self):
        """Offset ile timer başlatma."""
        timer = ShuttleTimer(start_offset_sec=10.0)
        assert timer.start_offset == 10.0
    
    def test_speed_progression(self):
        """Hız progresyonu kontrol."""
        timer = ShuttleTimer(start_offset_sec=0.0)
        # Shuttle nesnelerini al
        shuttle1 = timer.get_current_shuttle(t=0.0)
        # get_current_shuttle mevcut shuttle'ı döndürür
        assert shuttle1["speed_kmh"] == 7.0  # Mekik 1
