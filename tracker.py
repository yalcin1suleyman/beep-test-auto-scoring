"""
tracker.py — YOLOv8-Pose + ByteTrack Entegrasyonu
Koşucuların ayak bileği noktalarını tespit eder ve kimlik takibi yapar.

v2.1: Çıkarım çözünürlüğü (imgsz) ve düşük güven eşiği ile
      uzak mesafe (küçük nesne) tespiti iyileştirildi.
      
v3.0: Error handling, logging ve model validation eklendi.
"""

import numpy as np
from pathlib import Path
from ultralytics import YOLO

from config import (
    YOLO_MODEL,
    TRACKER_CONFIG,
    CONFIDENCE_THRESHOLD,
    IOU_THRESHOLD,
    INFER_IMGSZ,
    LEFT_ANKLE_IDX,
    RIGHT_ANKLE_IDX,
    ROI_X_MIN,
    ROI_X_MAX,
    PROJECT_ROOT,
    RunnerData,
)
from logger import get_logger
from validators import validate_yolo_model, validate_file_exists

log = get_logger(__name__)


class PoseTracker:
    """
    YOLOv8-Pose modeli ile ayak bileği tespiti ve
    ByteTrack ile çoklu nesne takibi.
    """

    def __init__(
        self,
        model_path: str = YOLO_MODEL,
        tracker_config: str = TRACKER_CONFIG,
        confidence: float = CONFIDENCE_THRESHOLD,
        iou: float = IOU_THRESHOLD,
        imgsz: int = INFER_IMGSZ,
    ):
        """
        Args:
            model_path: YOLOv8-Pose model dosya yolu.
            tracker_config: ByteTrack yapılandırma dosyası.
            confidence: Minimum güvenilirlik eşiği.
            iou: NMS IoU eşiği.
            imgsz: Çıkarım çözünürlüğü (px). Yüksek = uzak nesnelerde daha iyi.
        
        Raises:
            FileNotFoundError: Model veya config dosyası yoksa
            Exception: Model yükleme başarısız olursa
        """
        log.info(f"PoseTracker başlatılıyor... (model: {model_path})")
        if not Path(model_path).is_absolute() and not Path(model_path).exists():
            model_path = PROJECT_ROOT / model_path
        if not Path(tracker_config).is_absolute() and not Path(tracker_config).exists():
            tracker_config = PROJECT_ROOT / tracker_config
        
        # Model dosyasını doğrula
        try:
            validated_model_path = validate_yolo_model(model_path)
        except Exception as e:
            log.error(f"Model doğrulama başarısız: {e}")
            raise
        
        # Tracker config'ini doğrula
        try:
            validate_file_exists(
                tracker_config,
                description="ByteTrack yapılandırması",
                required=True
            )
        except Exception as e:
            log.error(f"Tracker config doğrulama başarısız: {e}")
            raise
        
        # YOLO modelini yükle
        try:
            self.model = YOLO(str(validated_model_path))
            log.info(f"✓ YOLO modeli yüklendi: {validated_model_path}")
        except Exception as e:
            log.error(f"YOLO modeli yüklenemedi: {e}")
            raise RuntimeError(
                f"YOLO modeli yüklenemedi: {e}\n"
                f"Lütfen modeli indirin: "
                f"python -c \"from ultralytics import YOLO; YOLO('yolov8n-pose.pt')\""
            ) from e
        
        self.tracker_config = str(tracker_config)
        self.confidence = confidence
        self.iou = iou
        self.imgsz = imgsz

        # İlk çalıştırmada modelin ısınması için
        self._warmed_up = False
        log.debug(
            f"Tracker konfigürasyonu: conf={confidence}, iou={iou}, imgsz={imgsz}"
        )

    def process_frame(self, frame: np.ndarray) -> list[RunnerData]:
        """
        Tek bir video karesini işleyerek koşucu verilerini döndürür.

        Args:
            frame: BGR formatında OpenCV görüntüsü.

        Returns:
            Her koşucu için RunnerData listesi.
            Ayak bileği tespit edilemeyenler filtrelenir.
        
        Raises:
            ValueError: frame None veya geçersiz şekilde ise
        """
        if frame is None:
            log.warning("Frame None: process_frame'e geçersiz frame")
            return []
        
        if not isinstance(frame, np.ndarray):
            log.warning(f"Geçersiz frame tipi: {type(frame)}")
            return []
        
        try:
            # ByteTrack ile takip — persist=True ID sürekliliği sağlar
            # imgsz yüksek tutularak uzaktaki küçük koşucuların da tespit edilmesi sağlanır
            results = self.model.track(
                source=frame,
                tracker=self.tracker_config,
                conf=self.confidence,
                iou=self.iou,
                imgsz=self.imgsz,
                persist=True,
                verbose=False,
            )

            runners: list[RunnerData] = []

            if results is None or len(results) == 0:
                return runners

            result = results[0]  # Tek görüntü → tek sonuç

            # Takip ID'leri mevcut değilse atla
            if result.boxes is None or result.boxes.id is None:
                return runners

            # Keypoint verisi yoksa atla
            if result.keypoints is None:
                return runners

            track_ids = result.boxes.id.cpu().numpy().astype(int)
            boxes = result.boxes.xyxy.cpu().numpy()
            confidences = result.boxes.conf.cpu().numpy()
            keypoints_xy = result.keypoints.xy.cpu().numpy()  # (N, 17, 2)

            for i, track_id in enumerate(track_ids):
                kpts = keypoints_xy[i]
                bbox = tuple(boxes[i].tolist())
                conf = float(confidences[i])

                # Ayak bileği orta noktasını hesapla
                ankle_mid = self._compute_ankle_midpoint(kpts)
                if ankle_mid is None:
                    continue

                mid_x, mid_y = ankle_mid

                # ROI filtresi: parkur dışındaki kişileri atla
                if ROI_X_MIN is not None and mid_x < ROI_X_MIN:
                    continue
                if ROI_X_MAX is not None and mid_x > ROI_X_MAX:
                    continue

                runners.append(
                    RunnerData(
                        track_id=int(track_id),
                        ankle_mid_x=mid_x,
                        ankle_mid_y=mid_y,
                        bbox=bbox,
                        confidence=conf,
                    )
                )

            return runners
        
        except Exception as e:
            log.error(f"Frame işlemesi başarısız: {e}", exc_info=True)
            raise RuntimeError("Poz takibi basarisiz; sonuclar guvenilir degil.") from e

    @staticmethod
    def _compute_ankle_midpoint(
        keypoints: np.ndarray,
    ) -> tuple[float, float] | None:
        """
        Sol ve sağ ayak bileği noktalarının ortalamasını hesaplar.

        Args:
            keypoints: (17, 2) şeklinde keypoint koordinatları.

        Returns:
            (mid_x, mid_y) veya tespit edilemezse None.
        """
        left_ankle = keypoints[LEFT_ANKLE_IDX]   # [x, y]
        right_ankle = keypoints[RIGHT_ANKLE_IDX]  # [x, y]

        # (0, 0) olan noktalar tespit edilememiş demektir
        left_valid = not (left_ankle[0] == 0 and left_ankle[1] == 0)
        right_valid = not (right_ankle[0] == 0 and right_ankle[1] == 0)

        if left_valid and right_valid:
            mid_x = (left_ankle[0] + right_ankle[0]) / 2.0
            mid_y = (left_ankle[1] + right_ankle[1]) / 2.0
            return (mid_x, mid_y)
        elif left_valid:
            return (float(left_ankle[0]), float(left_ankle[1]))
        elif right_valid:
            return (float(right_ankle[0]), float(right_ankle[1]))
        else:
            return None

    def get_all_keypoints(self, frame: np.ndarray) -> list[dict]:
        """
        Hata ayıklama / görselleştirme için tüm keypoint'leri döndürür.
        Tracking olmadan sadece tespit yapar.

        Args:
            frame: BGR formatında OpenCV görüntüsü.

        Returns:
            Her kişi için {'keypoints': np.ndarray, 'bbox': tuple, 'conf': float} listesi.
        """
        results = self.model(
            frame,
            conf=self.confidence,
            iou=self.iou,
            imgsz=self.imgsz,
            verbose=False,
        )

        detections = []
        if results and results[0].keypoints is not None:
            result = results[0]
            keypoints_xy = result.keypoints.xy.cpu().numpy()
            boxes = result.boxes.xyxy.cpu().numpy()
            confidences = result.boxes.conf.cpu().numpy()

            for i in range(len(keypoints_xy)):
                detections.append({
                    "keypoints": keypoints_xy[i],
                    "bbox": tuple(boxes[i].tolist()),
                    "conf": float(confidences[i]),
                })

        return detections
