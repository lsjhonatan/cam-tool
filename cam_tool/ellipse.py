"""
Módulo de ajuste de elipse do cam-tool.

A elipse é ajustada aos pontos mais altos do contorno (o "domo" da gota).
Serve para calcular as tangentes nos pontos de contato.

Uso típico:
    from cam_tool.ellipse import EllipseFitter
    fitter = EllipseFitter()
    elipse = fitter.ajustar(pontos_do_contorno, percentual_altos=50.0)
    # elipse.centro, elipse.eixos, elipse.angulo
    ponto = elipse.ponto_em(theta_graus)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from cam_tool.log import get_logger

log = get_logger()


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class Elipse:
    """
    Representa uma elipse ajustada.

    Atributos (padrão OpenCV):
        centro:   (cx, cy)
        eixos:    (eixo_maior, eixo_menor)  — diâmetros, não raios
        angulo:   ângulo de rotação em graus (sentido horário a partir do eixo X)
    """
    centro: tuple[float, float]
    eixos: tuple[float, float]
    angulo: float

    def ponto_em(self, theta_graus: float) -> tuple[float, float]:
        """
        Retorna o ponto da elipse no parâmetro theta (em graus).

        theta = 0   → extremidade do eixo maior no sentido positivo
        theta = 90  → extremidade do eixo menor
        """
        return ponto_elipse(self.centro, self.eixos, self.angulo, theta_graus)

    def tangente_em(self, theta_graus: float) -> tuple[float, float]:
        """
        Retorna o vetor tangente (não normalizado) à elipse em theta.

        Use normalizar_vetor() se precisar de vetor unitário.
        """
        return tangente_elipse(self.centro, self.eixos, self.angulo, theta_graus)


# ---------------------------------------------------------------------------
# Matemática da elipse
# ---------------------------------------------------------------------------

def ponto_elipse(
    centro: tuple[float, float],
    eixos: tuple[float, float],
    angulo_graus: float,
    theta_graus: float,
) -> tuple[float, float]:
    """
    Calcula o ponto sobre a elipse parametrizado por theta.

    Fórmula:
        x_local = a * cos(theta)
        y_local = b * sin(theta)
        onde a = eixo_maior / 2, b = eixo_menor / 2

    O ponto é rotacionado por `angulo` e transladado pelo `centro`.
    """
    a = eixos[0] / 2.0
    b = eixos[1] / 2.0

    theta = np.radians(theta_graus)
    angulo = np.radians(angulo_graus)

    x_local = a * np.cos(theta)
    y_local = b * np.sin(theta)

    # Rotação
    x_rot = x_local * np.cos(angulo) - y_local * np.sin(angulo)
    y_rot = x_local * np.sin(angulo) + y_local * np.cos(angulo)

    return (centro[0] + x_rot, centro[1] + y_rot)


def tangente_elipse(
    centro: tuple[float, float],
    eixos: tuple[float, float],
    angulo_graus: float,
    theta_graus: float,
) -> tuple[float, float]:
    """
    Calcula o vetor tangente à elipse no ponto parametrizado por theta.

    Fórmula (derivada da parametrização):
        dx_local = -a * sin(theta)
        dy_local =  b * cos(theta)

    O vetor é rotacionado por `angulo`.
    """
    a = eixos[0] / 2.0
    b = eixos[1] / 2.0

    theta = np.radians(theta_graus)
    angulo = np.radians(angulo_graus)

    dx_local = -a * np.sin(theta)
    dy_local = b * np.cos(theta)

    dx_rot = dx_local * np.cos(angulo) - dy_local * np.sin(angulo)
    dy_rot = dx_local * np.sin(angulo) + dy_local * np.cos(angulo)

    return (dx_rot, dy_rot)


def normalizar_vetor(v: tuple[float, float]) -> tuple[float, float]:
    """Normaliza um vetor (retorna vetor unitário)."""
    x, y = v
    norma = np.hypot(x, y)
    if norma < 1e-12:
        return (0.0, 0.0)
    return (x / norma, y / norma)


# ---------------------------------------------------------------------------
# EllipseFitter
# ---------------------------------------------------------------------------

class EllipseFitter:
    """
    Ajusta uma elipse aos pontos mais altos do contorno.

    O algoritmo:
        1. Ordena os pontos por Y (menor primeiro = mais altos)
        2. Seleciona os N% mais altos (o topo da gota)
        3. Ajusta uma elipse com cv2.fitEllipse
    """

    def ajustar(
        self,
        pontos: np.ndarray,
        percentual_altos: float = 50.0,
    ) -> Optional[Elipse]:
        """
        Ajusta uma elipse aos pontos mais altos.

        Parâmetros:
            pontos:            array (N, 2)
            percentual_altos:  % dos pontos mais altos usados no ajuste

        Retorna:
            Elipse ou None se não for possível ajustar.
        """
        if pontos is None or len(pontos) < 5:
            log.warning(f"Pontos insuficientes para ajustar elipse: {len(pontos) if pontos is not None else 0}")
            return None

        percentual_altos = max(0.0, min(100.0, percentual_altos))

        # Ordena por Y crescente (menor Y = mais alto na imagem)
        indices = np.argsort(pontos[:, 1])
        pontos_ordenados = pontos[indices]

        # Seleciona N% mais altos
        n_altos = max(5, int(len(pontos_ordenados) * percentual_altos / 100.0))
        pontos_altos = pontos_ordenados[:n_altos]

        if len(pontos_altos) < 5:
            log.warning(f"Poucos pontos altos: {len(pontos_altos)}")
            return None

        # OpenCV exige int32 ou float32
        pontos_cv = pontos_altos.astype(np.float32).reshape(-1, 1, 2)

        try:
            (cx, cy), (eixo_a, eixo_b), angulo = cv2.fitEllipse(pontos_cv)
            elipse = Elipse(
                centro=(float(cx), float(cy)),
                eixos=(float(eixo_a), float(eixo_b)),
                angulo=float(angulo),
            )
            log.debug(
                f"Elipse ajustada: centro=({cx:.1f},{cy:.1f}), "
                f"eixos=({eixo_a:.1f},{eixo_b:.1f}), ângulo={angulo:.1f}°"
            )
            return elipse
        except Exception as e:
            log.error(f"Falha ao ajustar elipse: {e}")
            return None


# ---------------------------------------------------------------------------
# Função de conveniência
# ---------------------------------------------------------------------------

def ajustar_elipse(
    pontos: np.ndarray,
    percentual_altos: float = 50.0,
) -> Optional[Elipse]:
    """Atalho funcional."""
    return EllipseFitter().ajustar(pontos, percentual_altos)