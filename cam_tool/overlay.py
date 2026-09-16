"""
Módulo de overlay do cam-tool.

Responsável por desenhar:
- Retângulo da ROI
- Contorno completo
- Linha de base
- Linhas de dimensão (largura, altura)
- Rótulos de medidas (largura, altura, raio)
- Rótulo de tempo

Uso típico:
    from cam_tool.overlay import OverlayRenderer, EstiloOverlay
    estilo = EstiloOverlay()
    renderer = OverlayRenderer(estilo)
    imagem_anotada = renderer.renderizar(frame, contorno, baseline, medidas)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from cam_tool.baseline import LinhaBase
from cam_tool.contour import ResultadoContorno
from cam_tool.log import get_logger
from cam_tool.measurements import MedidasGota

log = get_logger()


# ---------------------------------------------------------------------------
# Fontes candidatas
# ---------------------------------------------------------------------------

FONTES_CANDIDATAS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]


# ---------------------------------------------------------------------------
# Estilo
# ---------------------------------------------------------------------------

@dataclass
class EstiloOverlay:
    """Define as cores e configurações de cada elemento do overlay."""
    # ROI
    roi_cor: tuple[int, int, int] = (0, 125, 255)
    roi_desenhar: bool = True
    roi_espessura: int = 2

    # Contorno
    contorno_cor: tuple[int, int, int] = (0, 255, 255)
    contorno_desenhar: bool = True
    contorno_espessura: int = 2

    # Baseline
    baseline_cor: tuple[int, int, int] = (0, 0, 255)
    baseline_desenhar: bool = True
    baseline_espessura: int = 2

    # Linhas de dimensão (largura, altura, raio)
    linha_dimensao_cor: tuple[int, int, int] = (0, 0, 0)  # preto
    linha_dimensao_desenhar: bool = True
    linha_dimensao_espessura: int = 1

    # Medidas (texto)
    medida_cor: tuple[int, int, int] = (0, 0, 0)  # preto
    medida_desenhar: bool = True
    medida_fonte_tamanho: int = 22
    medida_fonte_espessura: int = 0
    medida_fundo_cor: tuple[int, int, int] = (255, 255, 255)  # branco
    medida_fundo_desenhar: bool = True
    medida_fundo_padding: int = 4
    medida_offset: tuple[int, int] = (0, 0)

    # Texto de tempo
    tempo_cor_texto: tuple[int, int, int] = (0, 0, 0)
    tempo_cor_fundo: tuple[int, int, int] = (255, 255, 255)
    tempo_fundo_desenhar: bool = True
    tempo_desenhar: bool = True
    tempo_fonte_tamanho: int = 24
    tempo_fonte_espessura: int = 0
    tempo_offset: tuple[int, int] = (0, 0)
    tempo_fundo_padding: int = 6


# ---------------------------------------------------------------------------
# Renderizador
# ---------------------------------------------------------------------------

class OverlayRenderer:
    """Renderiza todos os elementos do overlay na imagem."""

    def __init__(self, estilo: Optional[EstiloOverlay] = None):
        self.estilo = estilo or EstiloOverlay()

    def renderizar(
        self,
        imagem: np.ndarray,
        contorno: Optional[ResultadoContorno] = None,
        baseline: Optional[LinhaBase] = None,
        medidas: Optional[MedidasGota] = None,
        roi_x1: Optional[int] = None,
        roi_x2: Optional[int] = None,
        texto_tempo: Optional[str] = None,
        unidade: str = "nm",
    ) -> np.ndarray:
        """Desenha todos os elementos na imagem."""
        if imagem is None or imagem.size == 0:
            log.error("Imagem vazia recebida pelo overlay")
            return imagem

        resultado = imagem.copy()
        e = self.estilo

        # 1. ROI
        if e.roi_desenhar and roi_x1 is not None and roi_x2 is not None:
            self._desenhar_roi(resultado, roi_x1, roi_x2)

        # 2. Contorno
        if e.contorno_desenhar and contorno is not None and contorno.contorno is not None:
            cv2.drawContours(resultado, [contorno.contorno], -1, e.contorno_cor, e.contorno_espessura)

        # 3. Baseline
        if e.baseline_desenhar and baseline is not None:
            self._desenhar_baseline(resultado, baseline, roi_x1, roi_x2)

        # 4. Medidas (linhas + texto)
        if medidas is not None:
            if e.linha_dimensao_desenhar:
                self._desenhar_linhas_dimensao(resultado, medidas)
            if e.medida_desenhar:
                self._desenhar_texto_medidas(resultado, medidas, unidade)

        # 5. Texto de tempo
        if e.tempo_desenhar and texto_tempo:
            self._desenhar_texto_tempo(resultado, texto_tempo)

        return resultado

    # ------------------------------------------------------------------
    # Elementos
    # ------------------------------------------------------------------

    def _desenhar_roi(self, imagem: np.ndarray, x1: int, x2: int) -> None:
        e = self.estilo
        h = imagem.shape[0]
        cv2.rectangle(imagem, (x1, 0), (x2, h - 1), e.roi_cor, e.roi_espessura)

    def _desenhar_baseline(
        self,
        imagem: np.ndarray,
        baseline: LinhaBase,
        roi_x1: Optional[int],
        roi_x2: Optional[int],
    ) -> None:
        e = self.estilo
        w = imagem.shape[1]
        x1 = roi_x1 if roi_x1 is not None else 0
        x2 = roi_x2 if roi_x2 is not None else w - 1
        y1 = int(baseline.avaliar(x1))
        y2 = int(baseline.avaliar(x2))
        cv2.line(imagem, (x1, y1), (x2, y2), e.baseline_cor, e.baseline_espessura)

    def _desenhar_linhas_dimensao(self, imagem: np.ndarray, medidas: MedidasGota) -> None:
        """Desenha as linhas de largura e altura."""
        e = self.estilo
        cor = e.linha_dimensao_cor
        esp = e.linha_dimensao_espessura

        x_esq, y_esq = medidas.ponto_esq
        x_dir, y_dir = medidas.ponto_dir
        x_topo, y_topo = medidas.ponto_topo

        # Linha de largura (na base): de x_esq a x_dir, em y médio dos contatos
        y_base = (y_esq + y_dir) / 2
        cv2.line(imagem, (int(x_esq), int(y_base)), (int(x_dir), int(y_base)), cor, esp)

        # Linhas verticais nas extremidades da largura
        cv2.line(imagem, (int(x_esq), int(y_base - 5)), (int(x_esq), int(y_base + 5)), cor, esp)
        cv2.line(imagem, (int(x_dir), int(y_base - 5)), (int(x_dir), int(y_base + 5)), cor, esp)

        # Linha de altura (vertical, do topo até a base)
        x_centro = (x_esq + x_dir) / 2
        cv2.line(imagem, (int(x_centro), int(y_topo)), (int(x_centro), int(y_base)), cor, esp)

        # Linhas horizontais no topo e na base da altura
        cv2.line(imagem, (int(x_centro - 5), int(y_topo)), (int(x_centro + 5), int(y_topo)), cor, esp)
        cv2.line(imagem, (int(x_centro - 5), int(y_base)), (int(x_centro + 5), int(y_base)), cor, esp)

    def _desenhar_texto_medidas(
        self,
        imagem: np.ndarray,
        medidas: MedidasGota,
        unidade: str,
    ) -> None:
        """Desenha os rótulos com largura, altura e raio."""
        e = self.estilo

        # Converte para a unidade pedida
        fator = self._fator_unidade(medidas.escala_nm_por_px, unidade)

        largura = medidas.largura_px * fator
        altura = medidas.altura_px * fator
        raio = medidas.raio_px * fator

        # Monta as linhas de texto
        linhas = [
            f"Largura: {largura:.2f} {unidade}",
            f"Altura:  {altura:.2f} {unidade}",
            f"Raio R:  {raio:.2f} {unidade}",
        ]

        # Ponto de ancoragem: canto superior esquerdo da ROI, com offset
        x0 = int(medidas.ponto_esq[0]) + e.medida_offset[0]
        y0 = int(medidas.ponto_topo[1]) - 80 + e.medida_offset[1]

        # Desenha cada linha
        for i, linha in enumerate(linhas):
            pos = (x0, y0 + i * (e.medida_fonte_tamanho + 6))
            self._desenhar_texto_com_fundo(
                imagem,
                texto=linha,
                posicao=pos,
                tamanho=e.medida_fonte_tamanho,
                cor_texto=e.medida_cor,
                cor_fundo=e.medida_fundo_cor,
                desenhar_fundo=e.medida_fundo_desenhar,
                padding=e.medida_fundo_padding,
                espessura=e.medida_fonte_espessura,
            )

    def _desenhar_texto_tempo(self, imagem: np.ndarray, texto: str) -> None:
        """Desenha o rótulo de tempo no centro inferior."""
        e = self.estilo
        h, w = imagem.shape[:2]
        font = self._carregar_fonte(e.tempo_fonte_tamanho)
        tw, th = self._medir_texto(texto, font)

        x = (w - tw) // 2 + e.tempo_offset[0]
        y = h - th - 20 + e.tempo_offset[1]

        self._desenhar_texto_com_fundo(
            imagem,
            texto=texto,
            posicao=(x, y),
            tamanho=e.tempo_fonte_tamanho,
            cor_texto=e.tempo_cor_texto,
            cor_fundo=e.tempo_cor_fundo,
            desenhar_fundo=e.tempo_fundo_desenhar,
            padding=e.tempo_fundo_padding,
            espessura=e.tempo_fonte_espessura,
        )

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------

    @staticmethod
    def _fator_unidade(escala_nm_por_px: float, unidade: str) -> float:
        """
        Retorna o fator de conversão de pixels para a unidade pedida,
        dado que a escala_nm_por_px converte px → nm.

        Ex: se escala=500 nm/px e unidade="µm", o fator é 0.5 (nm→µm).
        """
        # Valor em nm por pixel
        nm_por_px = escala_nm_por_px

        # Fatores de conversão de nm para a unidade
        fatores = {
            "nm": 1.0,
            "µm": 1e-3,
            "um": 1e-3,
            "mm": 1e-6,
            "cm": 1e-7,
            "m": 1e-9,
        }
        fator = fatores.get(unidade.lower(), 1.0)
        return nm_por_px * fator

    @staticmethod
    def _carregar_fonte(tamanho: int) -> ImageFont.FreeTypeFont:
        for caminho in FONTES_CANDIDATAS:
            if Path(caminho).is_file():
                try:
                    return ImageFont.truetype(caminho, tamanho)
                except (IOError, OSError) as e:
                    log.warning(f"Fonte {caminho} falhou: {e}")
                    continue
        log.warning("Nenhuma fonte TrueType encontrada; usando padrão do PIL")
        return ImageFont.load_default()

    @staticmethod
    def _medir_texto(texto: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
        try:
            bbox = font.getbbox(texto)
            return (bbox[2] - bbox[0], bbox[3] - bbox[1])
        except Exception:
            return (len(texto) * 10, 20)

    @staticmethod
    def _desenhar_texto_com_fundo(
        imagem_bgr: np.ndarray,
        texto: str,
        posicao: tuple[int, int],
        tamanho: int,
        cor_texto: tuple[int, int, int],
        cor_fundo: tuple[int, int, int],
        desenhar_fundo: bool,
        padding: int,
        espessura: int,
    ) -> None:
        """Desenha texto com fundo, suportando Unicode (incluindo µm, °)."""
        imagem_rgb = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(imagem_rgb)
        draw = ImageDraw.Draw(pil)

        font = OverlayRenderer._carregar_fonte(tamanho)

        cor_texto_rgb = (cor_texto[2], cor_texto[1], cor_texto[0])
        cor_fundo_rgb = (cor_fundo[2], cor_fundo[1], cor_fundo[0])

        x, y = posicao

        if desenhar_fundo:
            bbox = draw.textbbox((x, y), texto, font=font, stroke_width=espessura)
            draw.rectangle(
                (bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding),
                fill=cor_fundo_rgb,
            )

        try:
            draw.text(
                (x, y),
                texto,
                font=font,
                fill=cor_texto_rgb,
                stroke_width=espessura,
                stroke_fill=cor_texto_rgb,
            )
        except Exception as e:
            log.warning(f"Falha ao desenhar texto '{texto}': {e}")

        resultado = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        imagem_bgr[:] = resultado


# ---------------------------------------------------------------------------
# Função de conveniência
# ---------------------------------------------------------------------------

def renderizar_overlay(
    imagem: np.ndarray,
    contorno: Optional[ResultadoContorno] = None,
    baseline: Optional[LinhaBase] = None,
    medidas: Optional[MedidasGota] = None,
    roi_x1: Optional[int] = None,
    roi_x2: Optional[int] = None,
    texto_tempo: Optional[str] = None,
    unidade: str = "nm",
    estilo: Optional[EstiloOverlay] = None,
) -> np.ndarray:
    """Atalho funcional."""
    return OverlayRenderer(estilo).renderizar(
        imagem,
        contorno=contorno,
        baseline=baseline,
        medidas=medidas,
        roi_x1=roi_x1,
        roi_x2=roi_x2,
        texto_tempo=texto_tempo,
        unidade=unidade,
    )