"""
Módulo de segmentação do cam-tool.

Responsável por isolar a gota do fundo, aplicando:
- Conversão para escala de cinza
- Desfoque gaussiano (reduz ruído)
- Inversão (gota escura vira clara)
- Binarização por Otsu (threshold automático)
- Operações morfológicas (abrir/fechar)
- Aplicação de máscara na região de interesse (ROI)

Uso típico:
    from cam_tool.segmentation import Segmenter, ParametrosSegmentacao
    seg = Segmenter(ParametrosSegmentacao(roi_x1=750, roi_x2=1700))
    mascara = seg.processar(frame)
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from cam_tool.log import get_logger

log = get_logger()


# ---------------------------------------------------------------------------
# Parâmetros
# ---------------------------------------------------------------------------

@dataclass
class ParametrosSegmentacao:
    """
    Parâmetros da segmentação.

    Atributos:
        roi_x1:             coordenada X inicial da região de interesse
        roi_x2:             coordenada X final da região de interesse
        kernel_blur:        tamanho do kernel do desfoque gaussiano (ímpar)
        kernel_morph_open:  tamanho do kernel da abertura morfológica
        kernel_morph_close: tamanho do kernel do fechamento morfológico
    """
    roi_x1: int = 750
    roi_x2: int = 1700
    kernel_blur: int = 7
    kernel_morph_open: int = 5
    kernel_morph_close: int = 9


# ---------------------------------------------------------------------------
# Segmenter
# ---------------------------------------------------------------------------

class Segmenter:
    """
    Segmenta a gota em uma imagem, retornando uma máscara binária.

    Pipeline:
        1. Converte para escala de cinza
        2. Aplica blur gaussiano
        3. Inverte (gota escura → clara)
        4. Binariza com Otsu
        5. Abre (remove ruído pequeno)
        6. Fecha (preenche buracos)
        7. Zera tudo fora da ROI

    Exemplo:
        seg = Segmenter(ParametrosSegmentacao(roi_x1=750, roi_x2=1700))
        mascara = seg.processar(frame)
    """

    def __init__(self, parametros: ParametrosSegmentacao | None = None):
        self.parametros = parametros or ParametrosSegmentacao()

    def processar(self, imagem_bgr: np.ndarray) -> np.ndarray:
        """
        Processa uma imagem BGR e retorna a máscara binária da gota.

        A máscara tem o mesmo tamanho da imagem original, mas apenas
        a região da ROI contém informação. Fora da ROI, tudo é preto (0).
        """
        p = self.parametros

        if imagem_bgr is None or imagem_bgr.size == 0:
            log.error("Imagem vazia recebida pela segmentação")
            return np.zeros((1, 1), dtype=np.uint8)

        # 1. Escala de cinza
        cinza = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2GRAY)

        # 2. Desfoque gaussiano (kernel ímpar)
        kernel_b = p.kernel_blur if p.kernel_blur % 2 == 1 else p.kernel_blur + 1
        blur = cv2.GaussianBlur(cinza, (kernel_b, kernel_b), 0)

        # 3. Inversão (gota escura vira clara)
        invertida = cv2.bitwise_not(blur)

        # 4. Binarização por Otsu
        _, mascara = cv2.threshold(
            invertida, 0, 255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        # 5. Abertura (remove pontos isolados)
        k_open = p.kernel_morph_open
        if k_open > 0:
            elem = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_open, k_open))
            mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, elem)

        # 6. Fechamento (preenche buracos)
        k_close = p.kernel_morph_close
        if k_close > 0:
            elem = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_close, k_close))
            mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, elem)

        # 7. Zera fora da ROI
        mascara_roi = np.zeros_like(mascara)
        x1 = max(0, min(p.roi_x1, mascara.shape[1]))
        x2 = max(0, min(p.roi_x2, mascara.shape[1]))
        if x2 > x1:
            mascara_roi[:, x1:x2] = mascara[:, x1:x2]

        return mascara_roi


# ---------------------------------------------------------------------------
# Função de conveniência
# ---------------------------------------------------------------------------

def segmentar(
    imagem_bgr: np.ndarray,
    roi_x1: int,
    roi_x2: int,
    kernel_blur: int = 7,
    kernel_morph_open: int = 5,
    kernel_morph_close: int = 9,
) -> np.ndarray:
    """
    Atalho funcional para segmentar uma imagem sem instanciar Segmenter.

    Útil para testes rápidos.
    """
    params = ParametrosSegmentacao(
        roi_x1=roi_x1,
        roi_x2=roi_x2,
        kernel_blur=kernel_blur,
        kernel_morph_open=kernel_morph_open,
        kernel_morph_close=kernel_morph_close,
    )
    return Segmenter(params).processar(imagem_bgr)