"""
cone_line_adapter.py — Adapta sistema de detecção de cones ao PerspectiveLine.

Fornece funções para converter linhas de cones detectadas (ConeLine)
para o formato PerspectiveLine esperado pelo resto do sistema.
"""

from typing import Optional
from cone_detector import Cone, ConeLine, ConeDetector, DynamicLineTracker
from line_geometry import PerspectiveLine
import numpy as np


class ConeLineAdapter:
    """Integra detecção de cones com PerspectiveLine do sistema existente."""
    
    def __init__(self, frame_width: int, frame_height: int):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.cone_detector = ConeDetector()
        self.line_tracker = DynamicLineTracker(smoothing_alpha=0.7)
    
    def detect_and_create_line(self, frame: np.ndarray) -> Optional[PerspectiveLine]:
        """
        Detecta cones no frame e cria PerspectiveLine a partir deles.
        
        Args:
            frame: Frame BGR do OpenCV
            
        Returns:
            PerspectiveLine ou None se não encontrar cones
        """
        try:
            # Detecta cones
            cones = self.cone_detector.detect_cones(frame)
            
            if len(cones) < 2:
                # Não há cones suficientes, tenta usar frame anterior
                if len(self.cone_detector._prev_cones) >= 2:
                    cones = self.cone_detector._prev_cones
                else:
                    return None
            
            # Cria linha a partir dos cones (extremos)
            cone_line = self.cone_detector.get_line_from_cones(cones, fallback_to_prev=True)
            
            if cone_line is None:
                return None
            
            # Suaviza a linha ao longo do tempo
            smooth_line = self.line_tracker.update(cone_line)
            
            if smooth_line is None:
                return None
            
            # Converte ConeLine para PerspectiveLine
            return self._cone_line_to_perspective_line(smooth_line)
        except Exception as e:
            # Erro na detecção, registra e retorna None para usar linha base
            import traceback
            print(f"[ConeLineAdapter] Erro ao detectar cones: {e}")
            traceback.print_exc()
            return None
    
    def _cone_line_to_perspective_line(self, cone_line: ConeLine) -> PerspectiveLine:
        """Converte ConeLine para PerspectiveLine com interpolação suave através de todos os cones."""
        left_x, left_y = cone_line.left_base
        right_x, right_y = cone_line.right_base
        
        # Validação básica
        if left_x >= right_x:
            # Pista: se as coordenadas forem inválidas, retorna uma linha horizontal de fallback
            print(f"[ConeLineAdapter] AVISO: Coordenadas inválidas left_x={left_x} >= right_x={right_x}")
            num_points = max(5, int(self.frame_width / 100))
            points = []
            for i in range(num_points):
                x = (i / (num_points - 1)) * self.frame_width
                points.append((int(x), int(left_y)))
            return PerspectiveLine.from_points(points)
        
        # Obtém os cones originais detectados para usar todos, não apenas extremos
        all_cones = self.cone_detector._prev_cones
        
        if len(all_cones) >= 2:
            # Cria pontos usando TODOS os cones, ordenados por X (esquerda para direita)
            cone_bases = sorted([(c.base_x, c.base_y) for c in all_cones], key=lambda p: p[0])
            
            # Garante que os extremos são usados corretamente
            if len(cone_bases) > 0:
                # Força o primeiro e último ponto aos extremos detectados
                cone_bases[0] = (left_x, left_y)
                cone_bases[-1] = (right_x, right_y)
            
            # Cria pontos: todos os cones + interpolação entre eles
            points = []
            
            for i in range(len(cone_bases) - 1):
                x0, y0 = cone_bases[i]
                x1, y1 = cone_bases[i + 1]
                
                # Adiciona ponto da base
                points.append((int(round(x0)), int(round(y0))))
                
                # Interpola entre este cone e o próximo (mais suave)
                dx = x1 - x0
                if dx > 40:  # Se há espaço significativo, interpola
                    num_interp = max(3, int(dx / 25))  # Mais pontos = linha mais suave
                    for j in range(1, num_interp):
                        t = j / num_interp
                        x = x0 + t * dx
                        y = y0 + t * (y1 - y0)
                        points.append((int(round(x)), int(round(y))))
            
            # Adiciona o último cone
            if cone_bases:
                x_last, y_last = cone_bases[-1]
                points.append((int(round(x_last)), int(round(y_last))))
            
            if len(points) >= 2:
                try:
                    return PerspectiveLine.from_points(points)
                except ValueError:
                    print(f"[ConeLineAdapter] Erro ao criar PerspectiveLine com {len(points)} pontos")
        
        # Fallback para interpolação simples entre extremos
        num_points = max(5, int((right_x - left_x) / 50))  # 1 ponto a cada 50px
        points = []
        
        for i in range(num_points):
            t = i / max(1, num_points - 1)
            x = left_x + t * (right_x - left_x)
            y = cone_line.y_at(x)
            points.append((int(round(x)), int(round(y))))
        
        try:
            return PerspectiveLine.from_points(points)
        except ValueError as e:
            print(f"[ConeLineAdapter] Erro ao criar fallback PerspectiveLine: {e}")
            # Retorna uma linha horizontal como último recurso
            return PerspectiveLine.horizontal(int((left_y + right_y) / 2), self.frame_width)
    
    def draw_debug_cones(self, frame: np.ndarray):
        """Desenha cones detectados para debug."""
        cones = self.cone_detector._prev_cones
        self.cone_detector.draw_cones(frame, cones, draw_centers=True, draw_bases=True)
    
    def draw_debug_line(self, frame: np.ndarray, color: tuple = (0, 255, 0)):
        """Desenha a linha suavizada para debug."""
        if self.line_tracker._smoothed_line is not None:
            self.line_tracker._smoothed_line.draw(frame, color, thickness=2)
    
    def reset(self):
        """Reseta detectores e rastreadores."""
        self.cone_detector._prev_cones = []
        self.line_tracker.reset()
