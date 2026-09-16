"""
Módulo de overlay do cam-tool.

Responsável por desenhar todos os elementos visuais sobre a imagem:
- Retângulo da ROI
- Contorno completo
- Contorno da gota
- Linha de base
- Elipse ajustada
- Tangentes
- Rótulos de ângulo (esquerdo e direito) com fundo branco
- Rótulo de tempo (ex: "0 s")

Uso típico:
    from cam_tool.overlay import OverlayRenderer, EstiloOverlay
    estilo = EstiloOverlay(...)
    renderer = OverlayRenderer(estilo)
    imagem_anotada = renderer.renderizar(frame, resultado)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from cam_tool.angle import AngulosContato
from cam_tool.baseline import LinhaBase
from cam_tool.contour import ResultadoContorno
from cam_tool.ellipse import Elipse
from cam_tool.log import get_logger

log = get_logger()


# ---------------------------------------------------------------------------
# Caminhos de fontes candidatas (procura na ordem)
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
# Estilo (cores e configurações de desenho)
# ---------------------------------------------------------------------------

@dataclass
class EstiloOverlay:
    """
    Define as cores e configurações de cada elemento do overlay.

    Cores no formato BGR (padrão OpenCV).
    """
    # ROI
    roi_cor: tuple[int, int, int] = (0, 125, 255)   # laranja
    roi_desenhar: bool = True
    roi_espessura: int = 2

    # Contorno completo
    contorno_cor: tuple[int, int, int] = (0, 255, 255)  # amarelo
    contorno_desenhar: bool = True
    contorno_espessura: int = 2

    # Contorno da gota (elipse)
    gota_cor: tuple[int, int, int] = (0, 255, 0)  # verde
    gota_desenhar: bool = True
    gota_espessura: int = 2

    # Baseline
    baseline_cor: tuple[int, int, int] = (0, 0, 255)  # vermelho
    baseline_desenhar: bool = True
    baseline_espessura: int = 2

    # Tangentes
    tangente_cor: tuple[int, int, int] = (255, 0, 0)  # azul
    tangente_desenhar: bool = True
    tangente_espessura: int = 2
    tangente_comprimento: int = 80

    # Rótulos de ângulo
    angulo_cor: tuple[int, int, int] = (0, 0, 0)  # preto
    angulo_desenhar: bool = True
    angulo_fonte_tamanho: int = 26
    angulo_fonte_espessura: int = 0
    angulo_fundo_cor: tuple[int, int, int] = (255, 255, 255)  # branco
    angulo_fundo_desenhar: bool = True
    angulo_fundo_padding: int = 4
    # Offsets (dx, dy) a partir do ponto de contato
    angulo_offset_esq: tuple[int, int] = (-170, -90)
    angulo_offset_dir: tuple[int, int] = (30, -90)

    # Rótulo de tempo
    tempo_cor_texto: tuple[int, int, int] = (0, 0, 0)  # preto
    tempo_cor_fundo: tuple[int, int, int] = (255, 255, 255)  # branco
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
    """
    Renderiza todos os elementos do overlay na imagem.

    Exemplo:
        estilo = EstiloOverlay()
        renderer = OverlayRenderer(estilo)
        imagem_anotada = renderer.renderizar(frame, contorno, baseline, elipse, angulos, roi_x1, roi_x2)
    """

    def __init__(self, estilo: Optional[EstiloOverlay] = None):
        self.estilo = estilo or EstiloOverlay()

    def renderizar(
        self,
        imagem: np.ndarray,
        contorno: Optional[ResultadoContorno] = None,
        baseline: Optional[LinhaBase] = None,
        elipse: Optional[Elipse] = None,
        angulos: Optional[AngulosContato] = None,
        roi_x1: Optional[int] = None,
        roi_x2: Optional[int] = None,
        texto_tempo: Optional[str] = None,
    ) -> np.ndarray:
        """
        Desenha todos os elementos na imagem.

        Retorna uma cópia da imagem com os desenhos aplicados.
        """
        if imagem is None or imagem.size == 0:
            log.error("Imagem vazia recebida pelo overlay")
            return imagem

        resultado = imagem.copy()
        e = self.estilo

        # 1. ROI
        if e.roi_desenhar and roi_x1 is not None and roi_x2 is not None:
            self._desenhar_roi(resultado, roi_x1, roi_x2)

        # 2. Contorno completo
        if e.contorno_desenhar and contorno is not None and contorno.contorno is not None:
            cv2.drawContours(resultado, [contorno.contorno], -1, e.contorno_cor, e.contorno_espessura)

        # 3. Baseline
        if e.baseline_desenhar and baseline is not None:
            self._desenhar_baseline(resultado, baseline, roi_x1, roi_x2)

        # 4. Elipse (contorno da gota)
        if e.gota_desenhar and elipse is not None:
            self._desenhar_elipse(resultado, elipse)

        # 5. Tangentes
        if e.tangente_desenhar and angulos is not None:
            self._desenhar_tangentes(resultado, angulos)

        # 6. Ângulos (com fundo branco)
        if e.angulo_desenhar and angulos is not None:
            self._desenhar_angulos(resultado, angulos)

        # 7. Texto de tempo (com fundo branco)
        if e.tempo_desenhar and texto_tempo:
            self._desenhar_texto_tempo(resultado, texto_tempo)

        return resultado

    # ------------------------------------------------------------------
    # Elementos individuais
    # ------------------------------------------------------------------

    def _desenhar_roi(self, imagem: np.ndarray, x1: int, x2: int) -> None:
        """Desenha o retângulo da região de interesse."""
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
        """Desenha a linha de base."""
        e = self.estilo
        w = imagem.shape[1]

        x1 = roi_x1 if roi_x1 is not None else 0
        x2 = roi_x2 if roi_x2 is not None else w - 1

        y1 = int(baseline.avaliar(x1))
        y2 = int(baseline.avaliar(x2))

        cv2.line(imagem, (x1, y1), (x2, y2), e.baseline_cor, e.baseline_espessura)

    def _desenhar_elipse(self, imagem: np.ndarray, elipse: Elipse) -> None:
        """Desenha a elipse ajustada."""
        e = self.estilo
        centro_int = (int(round(elipse.centro[0])), int(round(elipse.centro[1])))
        eixos_int = (int(round(elipse.eixos[0] / 2)), int(round(elipse.eixos[1] / 2)))
        cv2.ellipse(
            imagem,
            centro_int,
            eixos_int,
            elipse.angulo,
            0, 360,
            e.gota_cor,
            e.gota_espessura,
        )

    def _desenhar_tangentes(self, imagem: np.ndarray, angulos: AngulosContato) -> None:
        """Desenha as tangentes nos pontos de contato."""
        e = self.estilo
        comp = e.tangente_comprimento

        for ponto, tangente in [
            (angulos.ponto_esquerdo, angulos.tangente_esq),
            (angulos.ponto_direito, angulos.tangente_dir),
        ]:
            if ponto is None or tangente is None:
                continue

            x, y = ponto
            tx, ty = tangente

            x1 = int(round(x - tx * comp))
            y1 = int(round(y - ty * comp))
            x2 = int(round(x + tx * comp))
            y2 = int(round(y + ty * comp))

            cv2.line(imagem, (x1, y1), (x2, y2), e.tangente_cor, e.tangente_espessura)
            cv2.circle(imagem, (int(round(x)), int(round(y))), 4, e.tangente_cor, -1)

    def _desenhar_angulos(self, imagem: np.ndarray, angulos: AngulosContato) -> None:
        """Desenha os rótulos de ângulo com fundo branco."""
        e = self.estilo

        # Esquerdo
        if angulos.esquerdo is not None and angulos.ponto_esquerdo is not None:
            x, y = angulos.ponto_esquerdo
            pos = (int(x + e.angulo_offset_esq[0]), int(y + e.angulo_offset_esq[1]))
            self._desenhar_texto_com_fundo(
                imagem,
                texto=f"{angulos.esquerdo:.1f}°",
                posicao=pos,
                tamanho=e.angulo_fonte_tamanho,
                cor_texto=e.angulo_cor,
                cor_fundo=e.angulo_fundo_cor,
                desenhar_fundo=e.angulo_fundo_desenhar,
                padding=e.angulo_fundo_padding,
                espessura=e.angulo_fonte_espessura,
            )

        # Direito
        if angulos.direito is not None and angulos.ponto_direito is not None:
            x, y = angulos.ponto_direito
            pos = (int(x + e.angulo_offset_dir[0]), int(y + e.angulo_offset_dir[1]))
            self._desenhar_texto_com_fundo(
                imagem,
                texto=f"{angulos.direito:.1f}°",
                posicao=pos,
                tamanho=e.angulo_fonte_tamanho,
                cor_texto=e.angulo_cor,
                cor_fundo=e.angulo_fundo_cor,
                desenhar_fundo=e.angulo_fundo_desenhar,
                padding=e.angulo_fundo_padding,
                espessura=e.angulo_fonte_espessura,
            )

    def _desenhar_texto_tempo(self, imagem: np.ndarray, texto: str) -> None:
        """Desenha o rótulo de tempo no centro inferior, com fundo branco."""
        e = self.estilo
        h, w = imagem.shape[:2]

        # Calcula tamanho do texto
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
    # Auxiliares de texto
    # ------------------------------------------------------------------

    @staticmethod
    def _carregar_fonte(tamanho: int) -> ImageFont.FreeTypeFont:
        """
        Carrega uma fonte TrueType.

        Procura em FONTES_CANDIDATAS na ordem. Se nenhuma existir,
        usa a fonte padrão do PIL (bitmap, feia, mas funcional).
        """
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
        """Retorna (largura, altura) do texto renderizado."""
        try:
            bbox = font.getbbox(texto)
            return (bbox[2] - bbox[0], bbox[3] - bbox[1])
        except Exception:
            # Fallback: estimativa grosseira
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
        """
        Desenha texto (com suporte a Unicode) e, opcionalmente,
        um retângulo de fundo atrás dele.

        Modifica a imagem BGR in-place.
        """
        # BGR → RGB → PIL
        imagem_rgb = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(imagem_rgb)
        draw = ImageDraw.Draw(pil)

        font = OverlayRenderer._carregar_fonte(tamanho)

        # Cor em RGB (PIL usa RGB)
        cor_texto_rgb = (cor_texto[2], cor_texto[1], cor_texto[0])
        cor_fundo_rgb = (cor_fundo[2], cor_fundo[1], cor_fundo[0])

        x, y = posicao

        # Desenha fundo
        if desenhar_fundo:
            bbox = draw.textbbox((x, y), texto, font=font, stroke_width=espessura)
            draw.rectangle(
                (bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding),
                fill=cor_fundo_rgb,
            )

        # Desenha texto
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

        # PIL → RGB → BGR (in-place)
        resultado = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        imagem_bgr[:] = resultado


# ---------------------------------------------------------------------------
# Função de conveniência
# ---------------------------------------------------------------------------

def renderizar_overlay(
    imagem: np.ndarray,
    contorno: Optional[ResultadoContorno] = None,
    baseline: Optional[LinhaBase] = None,
    elipse: Optional[Elipse] = None,
    angulos: Optional[AngulosContato] = None,
    roi_x1: Optional[int] = None,
    roi_x2: Optional[int] = None,
    texto_tempo: Optional[str] = None,
    estilo: Optional[EstiloOverlay] = None,
) -> np.ndarray:
    """Atalho funcional para renderizar o overlay."""
    return OverlayRenderer(estilo).renderizar(
        imagem,
        contorno=contorno,
        baseline=baseline,
        elipse=elipse,
        angulos=angulos,
        roi_x1=roi_x1,
        roi_x2=roi_x2,
        texto_tempo=texto_tempo,
    )