"""
Módulo de extração de contorno do cam-tool.

Responsável por:
- Encontrar o maior contorno na máscara segmentada
- Extrair os pontos do contorno como array NumPy
- Filtrar pontos dentro da ROI

Uso típico:
    from cam_tool.contour import ContourExtractor
    extrator = ContourExtractor(roi_x1=750, roi_x2=1700)
    contorno = extrator.extrair(mascara)
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
class ResultadoContorno:
    """
    Resultado da extração de contorno.

    Atributos:
        contorno:      contorno como array OpenCV (N, 1, 2) ou None
        pontos:        pontos do contorno como array (N, 2) ou None
        area:          área do contorno em pixels²
    """
    contorno: Optional[np.ndarray]
    pontos: Optional[np.ndarray]
    area: float


# ---------------------------------------------------------------------------
# ContourExtractor
# ---------------------------------------------------------------------------

class ContourExtractor:
    """
    Extrai o maior contorno de uma máscara binária.

    Exemplo:
        extrator = ContourExtractor(roi_x1=750, roi_x2=1700)
        resultado = extrator.extrair(mascara)
        if resultado.pontos is not None:
            print(f"Contorno com {len(resultado.pontos)} pontos")
    """

    def __init__(self, roi_x1: int, roi_x2: int):
        self.roi_x1 = roi_x1
        self.roi_x2 = roi_x2

    def extrair(self, mascara: np.ndarray) -> ResultadoContorno:
        """
        Encontra o maior contorno na máscara e retorna seus pontos.

        Retorna ResultadoContorno com contorno=None e pontos=None se
        nenhum contorno for encontrado.
        """
        if mascara is None or mascara.size == 0:
            log.warning("Máscara vazia recebida pelo extrator de contorno")
            return ResultadoContorno(None, None, 0.0)

        # Encontra todos os contornos externos
        contornos, _ = cv2.findContours(
            mascara,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        if not contornos:
            log.warning("Nenhum contorno encontrado na máscara")
            return ResultadoContorno(None, None, 0.0)

        # Pega o maior por área
        maior = max(contornos, key=cv2.contourArea)
        area = float(cv2.contourArea(maior))

        # Converte para array (N, 2)
        pontos = self._para_array_2d(maior)

        if pontos is None or len(pontos) < 5:
            log.warning(f"Contorno muito pequeno: {len(pontos) if pontos is not None else 0} pontos")
            return ResultadoContorno(maior, pontos, area)

        # Filtra pontos dentro da ROI
        pontos_filtrados = self._filtrar_roi(pontos)

        if len(pontos_filtrados) < 5:
            log.warning(f"Poucos pontos dentro da ROI: {len(pontos_filtrados)}")
            return ResultadoContorno(maior, pontos_filtrados, area)

        log.debug(f"Contorno extraído: {len(pontos_filtrados)} pontos, área={area:.0f}px²")
        return ResultadoContorno(maior, pontos_filtrados, area)

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------

    @staticmethod
    def _para_array_2d(contorno: np.ndarray) -> Optional[np.ndarray]:
        """
        Converte contorno OpenCV (N, 1, 2) para array (N, 2).

        Retorna None se não for possível converter.
        """
        if contorno is None or len(contorno) == 0:
            return None

        try:
            pontos = contorno.reshape(-1, 2)
            return pontos.astype(np.int32)
        except Exception as e:
            log.error(f"Falha ao converter contorno: {e}")
            return None

    def _filtrar_roi(self, pontos: np.ndarray) -> np.ndarray:
        """Mantém apenas pontos com X dentro de [roi_x1, roi_x2]."""
        mascara_x = (pontos[:, 0] >= self.roi_x1) & (pontos[:, 0] <= self.roi_x2)
        return pontos[mascara_x]