"""
exemplo_cone_detection.py — Exemplo de uso do sistema de detecção de cones

Este exemplo mostra como usar o cone_detector independentemente,
útil para testes e experimentação.

Uso:
    python exemplo_cone_detection.py --video seu_video.mp4
"""

import argparse
import cv2
from pathlib import Path

from cone_detector import ConeDetector, DynamicLineTracker


def main():
    parser = argparse.ArgumentParser(description="Teste de detecção de cones")
    parser.add_argument("--video", type=str, default="0metre.mp4", help="Arquivo de vídeo")
    args = parser.parse_args()
    
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"[ERRO] Arquivo não encontrado: {video_path}")
        return
    
    # Inicializa detector e rastreador
    detector = ConeDetector()
    tracker = DynamicLineTracker(smoothing_alpha=0.7)
    
    # Abre vídeo
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print("[ERRO] Não conseguiu abrir o vídeo")
        return
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_idx = 0
    
    print(f"[Vídeo] {video_path.name} - {fps:.1f} FPS")
    print("[Processando] ESC para sair")
    print()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Detecta cones
        cones = detector.detect_cones(frame)
        
        # Cria linha
        cone_line = detector.get_line_from_cones(cones)
        
        # Suaviza
        smooth_line = tracker.update(cone_line)
        
        # Desenha
        ann = frame.copy()
        
        # Debug: desenha todos os cones
        detector.draw_cones(ann, cones, draw_centers=True, draw_bases=True)
        
        # Desenha linha suavizada
        if smooth_line is not None:
            smooth_line.draw(ann, (0, 255, 0), thickness=3)
            
            # Info: bases
            left_base = smooth_line.left_base
            right_base = smooth_line.right_base
            
            cv2.putText(ann, 
                       f"Esq: ({int(left_base[0])}, {int(left_base[1])})",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(ann,
                       f"Dir: ({int(right_base[0])}, {int(right_base[1])})",
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Info geral
        cv2.putText(ann,
                   f"Frame {frame_idx} | Cones: {len(cones)}",
                   (10, ann.shape[0] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
        
        # Mostra
        cv2.imshow("Detecção de Cones", ann)
        
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            break
        
        frame_idx += 1
    
    cap.release()
    cv2.destroyAllWindows()
    print(f"\n[Concluído] {frame_idx} frames processados")


if __name__ == "__main__":
    main()
