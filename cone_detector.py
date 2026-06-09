"""
cone_detector.py — Detecção em tempo real de cones para linha dinâmica.

Sistema de detecção de cones baseado em cor (laranja/vermelho) que:
1. Identifica cones em cada frame
2. Encontra a base (ponto inferior) de cada cone
3. Cria uma linha dinamicamente entre o cone mais à esquerda e mais à direita
4. A linha se adapta aos movimentos de câmera
"""

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


@dataclass
class Cone:
    """Representa um cone detectado."""
    center_x: float
    center_y: float
    base_x: float  # Coordenada X da base
    base_y: float  # Coordenada Y da base (onde toca o chão)
    radius: float
    confidence: float


@dataclass
class ConeLine:
    """Linha criada pela base dos cones."""
    left_cone: Cone
    right_cone: Cone
    
    @property
    def left_base(self) -> tuple[float, float]:
        return (self.left_cone.base_x, self.left_cone.base_y)
    
    @property
    def right_base(self) -> tuple[float, float]:
        return (self.right_cone.base_x, self.right_cone.base_y)
    
    def y_at(self, x: float) -> float:
        """Interpola a coordenada Y para dado X entre os cones."""
        x0, y0 = self.left_base
        x1, y1 = self.right_base
        
        if x <= x0:
            return y0
        if x >= x1:
            return y1
        
        # Interpolação linear entre os dois pontos
        t = (x - x0) / (x1 - x0)
        return y0 + t * (y1 - y0)
    
    def draw(self, frame: np.ndarray, color: tuple[int, int, int], thickness: int):
        """Desenha a linha entre as bases dos cones com interpolação suave."""
        left_x, left_y = self.left_base
        right_x, right_y = self.right_base
        
        # Cria muitos pontos intermediários para uma linha suave
        num_points = max(10, int(abs(right_x - left_x) / 30))  # 1 ponto a cada 30px
        points = []
        
        for i in range(num_points):
            t = i / max(1, num_points - 1)
            x = left_x + t * (right_x - left_x)
            y = self.y_at(x)
            points.append([int(round(x)), int(round(y))])
        
        pts = np.array(points, dtype=np.int32)
        cv2.polylines(frame, [pts], isClosed=False, color=color, thickness=thickness)
        
        # Marca os pontos da base com círculos
        cv2.circle(frame, (int(round(left_x)), int(round(left_y))), 5, color, -1)
        cv2.circle(frame, (int(round(right_x)), int(round(right_y))), 5, color, -1)


class ConeDetector:
    """Detecção de cones baseada em cor (HSV)."""
    
    def __init__(self, 
                 lower_hue_range: tuple[int, int, int] = (0, 80, 80),
                 upper_hue_range: tuple[int, int, int] = (15, 255, 255),
                 secondary_lower: tuple[int, int, int] = (170, 80, 80),
                 secondary_upper: tuple[int, int, int] = (180, 255, 255),
                 min_cone_area: int = 200,
                 max_cone_area: int = 50000,
                 min_circularity: float = 0.4):
        """
        Inicializa detector de cones.
        
        Args:
            lower_hue_range: Limite inferior HSV para laranja
            upper_hue_range: Limite superior HSV para laranja
            secondary_lower: Limite inferior HSV para vermelho adicional
            secondary_upper: Limite superior HSV para vermelho adicional
            min_cone_area: Área mínima em pixels²
            max_cone_area: Área máxima em pixels²
            min_circularity: Circularidade mínima (0-1)
        """
        self.lower_hue = np.array(lower_hue_range, dtype=np.uint8)
        self.upper_hue = np.array(upper_hue_range, dtype=np.uint8)
        self.secondary_lower = np.array(secondary_lower, dtype=np.uint8)
        self.secondary_upper = np.array(secondary_upper, dtype=np.uint8)
        self.min_cone_area = min_cone_area
        self.max_cone_area = max_cone_area
        self.min_circularity = min_circularity
        self._prev_cones: list[Cone] = []
    
    def detect_cones(self, frame: np.ndarray) -> list[Cone]:
        """
        Detecta cones no frame.
        
        Returns:
            Lista de cones detectados ordenados por X (esquerda para direita)
        """
        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        except cv2.error as e:
            print(f"[ConeDetector] Erro ao converter para HSV: {e}")
            return []
        
        # Máscara para laranja + vermelho
        mask1 = cv2.inRange(hsv, self.lower_hue, self.upper_hue)
        mask2 = cv2.inRange(hsv, self.secondary_lower, self.secondary_upper)
        mask = cv2.bitwise_or(mask1, mask2)
        
        # Morfologia para limpar ruído
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # Encontra contornos
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        cones: list[Cone] = []
        
        for contour in contours:
            try:
                area = cv2.contourArea(contour)
                if area < self.min_cone_area or area > self.max_cone_area:
                    continue
                
                # Verifica circularidade (cones são aproximadamente circulares no topo)
                perimeter = cv2.arcLength(contour, True)
                if perimeter == 0:
                    continue
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                
                if circularity < self.min_circularity:
                    continue
                
                # Ajusta contorno e encontra círculo aproximado
                epsilon = 0.02 * perimeter
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Encontra o círculo que melhor se ajusta
                (cx, cy), radius = cv2.minEnclosingCircle(contour)
                
                # A base do cone é o ponto mais baixo (maior Y)
                # Reshape contour para ter forma (n, 2)
                contour_2d = contour.reshape(-1, 2)
                
                # Encontra a região inferior do contorno (base)
                bottom_idx = np.argmax(contour_2d[:, 1])
                extreme_bottom = contour_2d[bottom_idx]
                base_x = float(extreme_bottom[0])
                base_y = float(extreme_bottom[1])
                
                # Refina a base: pega a média dos pontos inferiores (mais robusta)
                # para evitar outliers
                max_y = contour_2d[:, 1].max()
                bottom_points = contour_2d[contour_2d[:, 1] > max_y - 10]
                if len(bottom_points) > 0:
                    base_x = float(bottom_points[:, 0].mean())
                    base_y = float(bottom_points[:, 1].mean())
                
                cone = Cone(
                    center_x=float(cx),
                    center_y=float(cy),
                    base_x=base_x,
                    base_y=base_y,
                    radius=float(radius),
                    confidence=circularity
                )
                cones.append(cone)
            except Exception as e:
                print(f"[ConeDetector] Erro ao processar contorno: {e}")
                continue
        
        # Ordena por X (esquerda para direita)
        cones.sort(key=lambda c: c.center_x)
        self._prev_cones = cones
        
        if len(cones) > 0:
            print(f"[ConeDetector] Detectados {len(cones)} cones (bases: {[(int(c.base_x), int(c.base_y)) for c in cones]})")
        
        return cones
    
    def get_line_from_cones(self, cones: list[Cone], 
                           fallback_to_prev: bool = True) -> Optional[ConeLine]:
        """
        Cria uma linha a partir dos cones detectados.
        
        Usa o cone mais à esquerda e o cone mais à direita.
        
        Args:
            cones: Lista de cones detectados
            fallback_to_prev: Se True e não houver 2+ cones, usa frame anterior
            
        Returns:
            ConeLine ou None se não houver cones suficientes
        """
        # Tenta usar cones atuais
        if len(cones) >= 2:
            # Se houver muitos cones, usa apenas os dois extremos
            left_cone = cones[0]
            right_cone = cones[-1]
            print(f"[ConeDetector] Linha criada com {len(cones)} cones: "
                  f"left={left_cone.base_x:.1f},{left_cone.base_y:.1f} "
                  f"right={right_cone.base_x:.1f},{right_cone.base_y:.1f}")
            return ConeLine(left_cone, right_cone)
        
        # Fallback para frame anterior se disponível
        if fallback_to_prev and len(self._prev_cones) >= 2:
            left_cone = self._prev_cones[0]
            right_cone = self._prev_cones[-1]
            print(f"[ConeDetector] Fallback: usando cones do frame anterior")
            return ConeLine(left_cone, right_cone)
        
        print(f"[ConeDetector] AVISO: Não há cones suficientes (atuais={len(cones)}, anteriores={len(self._prev_cones)})")
        return None
    
    def draw_cones(self, frame: np.ndarray, cones: list[Cone], 
                   draw_centers: bool = True, draw_bases: bool = True):
        """Desenha cones detectados para debug/visualização."""
        for cone in cones:
            # Desenha círculo aproximado
            cv2.circle(frame, 
                      (int(cone.center_x), int(cone.center_y)),
                      int(cone.radius),
                      (0, 165, 255), 2)  # Laranja
            
            if draw_centers:
                cv2.circle(frame,
                          (int(cone.center_x), int(cone.center_y)),
                          3, (255, 0, 0), -1)  # Azul no centro
            
            if draw_bases:
                cv2.circle(frame,
                          (int(cone.base_x), int(cone.base_y)),
                          4, (0, 0, 255), -1)  # Vermelho na base
                # Linha do centro até base
                cv2.line(frame,
                        (int(cone.center_x), int(cone.center_y)),
                        (int(cone.base_x), int(cone.base_y)),
                        (200, 200, 0), 1)  # Ciano


class DynamicLineTracker:
    """Rastreia linha de cones com suavização temporal."""
    
    def __init__(self, smoothing_alpha: float = 0.7):
        """
        Args:
            smoothing_alpha: Fator de suavização exponencial (0-1)
                           0 = muito suave, 1 = sem suavização
        """
        self.smoothing_alpha = smoothing_alpha
        self._last_line: Optional[ConeLine] = None
        self._smoothed_line: Optional[ConeLine] = None
    
    def update(self, new_line: Optional[ConeLine]) -> Optional[ConeLine]:
        """
        Atualiza a linha com suavização temporal.
        
        Args:
            new_line: Linha detectada no frame atual
            
        Returns:
            Linha suavizada
        """
        if new_line is None:
            # Se não há linha nova, retorna última conhecida
            return self._smoothed_line
        
        if self._smoothed_line is None:
            # Primeira detecção
            self._smoothed_line = new_line
            self._last_line = new_line
            return new_line
        
        # Suaviza as posições da base dos cones
        old_line = self._smoothed_line
        
        # Suaviza coordenadas dos pontos da base
        alpha = self.smoothing_alpha
        
        smooth_left_base_x = (1 - alpha) * old_line.left_base[0] + alpha * new_line.left_base[0]
        smooth_left_base_y = (1 - alpha) * old_line.left_base[1] + alpha * new_line.left_base[1]
        
        smooth_right_base_x = (1 - alpha) * old_line.right_base[0] + alpha * new_line.right_base[0]
        smooth_right_base_y = (1 - alpha) * old_line.right_base[1] + alpha * new_line.right_base[1]
        
        # Cria cones suavizados
        smooth_left_cone = Cone(
            center_x=smooth_left_base_x,
            center_y=smooth_left_base_y,
            base_x=smooth_left_base_x,
            base_y=smooth_left_base_y,
            radius=new_line.left_cone.radius,
            confidence=new_line.left_cone.confidence
        )
        
        smooth_right_cone = Cone(
            center_x=smooth_right_base_x,
            center_y=smooth_right_base_y,
            base_x=smooth_right_base_x,
            base_y=smooth_right_base_y,
            radius=new_line.right_cone.radius,
            confidence=new_line.right_cone.confidence
        )
        
        self._smoothed_line = ConeLine(smooth_left_cone, smooth_right_cone)
        self._last_line = new_line
        return self._smoothed_line
    
    def reset(self):
        """Reseta o rastreador."""
        self._last_line = None
        self._smoothed_line = None
