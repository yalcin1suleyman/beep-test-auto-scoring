"""
line_calibrator.py — İnteraktif Çift Çizgi Kalibrasyon Sistemi

Kullanıcı her iki kamerayla (başlangıç ve 20m) birbirinden bağımsız olarak
çizgileri fare ile belirleyebilir.

Kullanım:
  - Video oynatılır
  - Kullanıcı fare ile başlangıç (0m) çizgisini klikleyerek tanımlar
  - Ardından 20m çizgisini klikleyerek tanımlar
  - Çizgiler kaydedilir ve analiz için kullanılır
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List
from line_geometry import PerspectiveLine


class LineCalibrator:
    """İnteraktif çizgi kalibrasyon sistemi."""
    
    def __init__(self, camera_name: str = "Camera"):
        self.camera_name = camera_name
        self.points: List[Tuple[int, int]] = []
        self.current_frame = None
        self.frame_display = None
        self.finished = False
        self.window_name = f"Line Calibration - {camera_name}"
        
    def mouse_callback(self, event, x, y, flags, param):
        """Fare olaylarını işle."""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.points.append((x, y))
            self._update_display()
            
            if len(self.points) >= 2:
                print(f"\n✓ {self.camera_name}: Çizgi tanımlandı!")
                print(f"  Noktalar: {self.points}")
                self.finished = True
                
    def _update_display(self):
        """Güncel çizimi güncelle."""
        if self.current_frame is None:
            return
            
        self.frame_display = self.current_frame.copy()
        
        # Var olan noktaları çiz
        for i, (x, y) in enumerate(self.points):
            cv2.circle(self.frame_display, (x, y), 5, (0, 255, 0), -1)
            cv2.putText(self.frame_display, f"P{i+1}", (x+10, y-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Noktaları birleştir
        if len(self.points) >= 2:
            points_array = np.array(self.points, dtype=np.int32)
            cv2.polylines(self.frame_display, [points_array], False, (0, 255, 0), 2)
        
        # Talimatları göster
        if len(self.points) == 0:
            instruction = "Ilk noktayi tiklayiniz (solda/ust)"
        elif len(self.points) == 1:
            instruction = "Ikinci noktayi tiklayiniz (sagda/alt)"
        else:
            instruction = "Cizgi tamamlandi! Devam etmek icin bir tus basin."
            
        cv2.putText(self.frame_display, instruction, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(self.frame_display, f"Noktalar: {len(self.points)}/2", (10, 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        cv2.imshow(self.window_name, self.frame_display)
        
    def calibrate(self, frame: np.ndarray) -> Optional[PerspectiveLine]:
        """
        Kalibrasyonu başlat.
        
        Args:
            frame: Kalibrasyon yapılacak video frame
            
        Returns:
            Tanımlanmış PerspectiveLine nesnesi
        """
        self.current_frame = frame.copy()
        self.points = []
        self.finished = False
        
        # Pencereyi oluştur ve fare callback'ini ayarla
        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self.mouse_callback)
        
        print(f"\n{'='*60}")
        print(f"{self.camera_name} İçin Çizgi Kalibrasyon")
        print(f"{'='*60}")
        print(f"Lütfen video pencerede çizginin iki noktasını fare ile tiklayiniz.")
        print(f"- İlk nokta: Solda/Üst")
        print(f"- İkinci nokta: Sağda/Alt")
        print(f"İpucu: Atletlerin baş seviyesi civarında olsun.")
        
        # İlk çizmesi yap
        self._update_display()
        
        # Kalibrasyon tamamlanana kadar bekle
        while not self.finished:
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # ESC veya 'q'
                cv2.destroyWindow(self.window_name)
                print("⚠ Kalibrasyon iptal edildi.")
                return None
        
        # Biraz bekle ve pencereyi kapat
        cv2.waitKey(500)
        cv2.destroyWindow(self.window_name)
        
        # PerspectiveLine oluştur ve döndür
        line = PerspectiveLine.from_points(self.points)
        return line


class DualLineCalibrator:
    """Çift kamera kalibrasyon yöneticisi."""
    
    def __init__(self):
        self.start_calibrator = LineCalibrator("Başlangıç (0m)")
        self.far_calibrator = LineCalibrator("20m")
        self.start_line: Optional[PerspectiveLine] = None
        self.far_line: Optional[PerspectiveLine] = None
        
    def calibrate_both(
        self, 
        start_frame: np.ndarray,
        far_frame: np.ndarray
    ) -> Tuple[Optional[PerspectiveLine], Optional[PerspectiveLine]]:
        """
        Her iki kameranın çizgisini sırayla kalibre et.
        
        Args:
            start_frame: Başlangıç (0m) kamerası frame
            far_frame: 20m kamerası frame
            
        Returns:
            (start_line, far_line) tuple
        """
        print("\n" + "="*60)
        print("ÇIFT KAMERA KALİBRASYONU BAŞLANIYOR")
        print("="*60)
        
        # Başlangıç çizgisini kalibre et
        print("\n[1/2] Başlangıç (0m) çizgisini kalibre et...")
        self.start_line = self.start_calibrator.calibrate(start_frame)
        if self.start_line is None:
            print("✗ Kalibrasyon başarısız!")
            return None, None
        
        print(f"✓ Başlangıç çizgisi kaydedildi: {self.start_line.points}")
        
        # 20m çizgisini kalibre et
        print("\n[2/2] 20m çizgisini kalibre et...")
        self.far_line = self.far_calibrator.calibrate(far_frame)
        if self.far_line is None:
            print("✗ Kalibrasyon başarısız!")
            return self.start_line, None
        
        print(f"✓ 20m çizgisi kaydedildi: {self.far_line.points}")
        print("\n" + "="*60)
        print("✓ KALİBRASYON TAMAMLANDI!")
        print("="*60)
        
        return self.start_line, self.far_line
    
    def save_calibration(self, output_path: Path):
        """
        Kalibrasyon sonuçlarını kaydet.
        
        Args:
            output_path: Çıktı dosyası yolu
        """
        if self.start_line is None or self.far_line is None:
            print("⚠ Kalibrasyon henüz yapılmamış!")
            return
        
        import json
        
        calibration_data = {
            "start_line_points": list(self.start_line.points),
            "far_line_points": list(self.far_line.points),
            "start_line_y": self.start_line.median_y,
            "far_line_y": self.far_line.median_y,
        }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(calibration_data, f, indent=2)
        
        print(f"✓ Kalibrasyon kaydedildi: {output_path}")
    
    @staticmethod
    def load_calibration(input_path: Path) -> Tuple[Optional[PerspectiveLine], Optional[PerspectiveLine]]:
        """
        Kaydedilmiş kalibrasyon verilerini yükle.
        
        Args:
            input_path: Kalibrasyon dosyası yolu
            
        Returns:
            (start_line, far_line) tuple
        """
        if not input_path.exists():
            print(f"⚠ Kalibrasyon dosyası bulunamadı: {input_path}")
            return None, None
        
        import json
        
        try:
            with open(input_path, 'r') as f:
                data = json.load(f)
            
            start_line = PerspectiveLine.from_points(data["start_line_points"])
            far_line = PerspectiveLine.from_points(data["far_line_points"])
            
            print(f"✓ Kalibrasyon yüklendi: {input_path}")
            return start_line, far_line
        except Exception as e:
            print(f"✗ Kalibrasyon yükleme hatası: {e}")
            return None, None
