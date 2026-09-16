"""
Módulo de pipeline do cam-tool.

Orquestra todas as etapas da análise de uma gota:
    1. Segmentação
    2. Extração de contorno
    3. Ajuste de baseline
    4. Ajuste de elipse (validada contra a baseline)
    5. Cálculo de ângulos
    6. Renderização do overlay

Uso típico:
    from cam_tool.pipeline import DropletAnalyzer, ParametrosAnalise
    analyzer = DropletAnalyzer(ParametrosAnalise(roi_x1=750, roi_x2=1700))
    resultado = analyzer.analisar(frame)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from cam_tool.angle import AngulosContato, AngleCalculator
from cam_tool.baseline import BaselineFitter, LinhaBase
from cam_tool.contour import ContourExtractor, ResultadoContorno
from cam_tool.ellipse import EllipseFitter, Elipse
from cam_tool.log import get_logger
from cam_tool.overlay import EstiloOverlay, OverlayRenderer
from cam_tool.segmentation import ParametrosSegmentacao, Segmenter

log = get_logger()


# ---------------------------------------------------------------------------
# Parâmetros de análise
# ---------------------------------------------------------------------------

@dataclass
class ParametrosAnalise:
    """Reúne todos os parâmetros que o pipeline precisa."""
    roi_x1: int = 750
    roi_x2: int = 1700
    baseline_threshold: float = 15.0
    droplet_threshold: float = 50.0
    tolerancia_contato_px: float = 2.0
    tolerancia_baseline_elipse_px: float = 50.0
    passo_varredura_graus: float = 1.0
    kernel_blur: int = 7
    kernel_morph_open: int = 5
    kernel_morph_close: int = 9
    estilo: EstiloOverlay = field(default_factory=EstiloOverlay)

    @classmethod
    def de_config(cls, cfg) -> "ParametrosAnalise":
        """Constrói um ParametrosAnalise a partir de um ConfigManager."""
        estilo = EstiloOverlay(
            roi_cor=(cfg.obter("region_b"), cfg.obter("region_g"), cfg.obter("region_r")),
            roi_desenhar=cfg.obter("draw_region"),

            contorno_cor=(cfg.obter("contour_b"), cfg.obter("contour_g"), cfg.obter("contour_r")),
            contorno_desenhar=cfg.obter("draw_contour"),

            gota_cor=(cfg.obter("droplet_b"), cfg.obter("droplet_g"), cfg.obter("droplet_r")),
            gota_desenhar=cfg.obter("draw_droplet"),

            baseline_cor=(cfg.obter("baseline_b"), cfg.obter("baseline_g"), cfg.obter("baseline_r")),
            baseline_desenhar=cfg.obter("draw_baseline"),

            tangente_cor=(cfg.obter("tangent_b"), cfg.obter("tangent_g"), cfg.obter("tangent_r")),
            tangente_desenhar=cfg.obter("draw_tangent"),

            angulo_cor=(cfg.obter("angle_b"), cfg.obter("angle_g"), cfg.obter("angle_r")),
            angulo_desenhar=cfg.obter("draw_angle"),
            angulo_fonte_tamanho=cfg.obter("angle_font_size"),
            angulo_fonte_espessura=cfg.obter("angle_font_thickness"),
            angulo_offset_esq=(
                cfg.obter("left_angle_x_pos") - 170,
                cfg.obter("left_angle_y_pos") - 90,
            ),
            angulo_offset_dir=(
                cfg.obter("right_angle_x_pos") + 30,
                cfg.obter("right_angle_y_pos") - 90,
            ),

            tempo_cor_texto=(
                cfg.obter("label_text_b"),
                cfg.obter("label_text_g"),
                cfg.obter("label_text_r"),
            ),
            tempo_cor_fundo=(
                cfg.obter("label_background_b"),
                cfg.obter("label_background_g"),
                cfg.obter("label_background_r"),
            ),
            tempo_fundo_desenhar=cfg.obter("draw_label_background"),
            tempo_desenhar=cfg.obter("draw_label_text"),
            tempo_fonte_tamanho=cfg.obter("label_font_size"),
            tempo_fonte_espessura=cfg.obter("label_font_thickness"),
            tempo_offset=(cfg.obter("label_offset_x"), cfg.obter("label_offset_y")),
        )

        return cls(
            roi_x1=cfg.obter("roi_x1"),
            roi_x2=cfg.obter("roi_x2"),
            baseline_threshold=cfg.obter("baseline_threshold"),
            droplet_threshold=cfg.obter("droplet_threshold"),
            estilo=estilo,
        )


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class ResultadoAnalise:
    """Resultado completo de uma análise de gota."""
    angulos: Optional[AngulosContato] = None
    contorno: Optional[ResultadoContorno] = None
    baseline: Optional[LinhaBase] = None
    elipse: Optional[Elipse] = None
    imagem_anotada: Optional[np.ndarray] = None
    sucesso: bool = False
    erro: Optional[str] = None

    @property
    def angulo_esquerdo(self) -> Optional[float]:
        return self.angulos.esquerdo if self.angulos else None

    @property
    def angulo_direito(self) -> Optional[float]:
        return self.angulos.direito if self.angulos else None

    @property
    def angulo_medio(self) -> Optional[float]:
        return self.angulos.media if self.angulos else None


# ---------------------------------------------------------------------------
# DropletAnalyzer
# ---------------------------------------------------------------------------

class DropletAnalyzer:
    """Orquestra o pipeline de análise de uma gota."""

    def __init__(self, parametros: Optional[ParametrosAnalise] = None):
        self.parametros = parametros or ParametrosAnalise()

        self._segmenter = Segmenter(ParametrosSegmentacao(
            roi_x1=self.parametros.roi_x1,
            roi_x2=self.parametros.roi_x2,
            kernel_blur=self.parametros.kernel_blur,
            kernel_morph_open=self.parametros.kernel_morph_open,
            kernel_morph_close=self.parametros.kernel_morph_close,
        ))
        self._extrator_contorno = ContourExtractor(
            roi_x1=self.parametros.roi_x1,
            roi_x2=self.parametros.roi_x2,
        )
        self._baseline_fitter = BaselineFitter()
        self._ellipse_fitter = EllipseFitter()
        self._angle_calculator = AngleCalculator(
            tolerancia_px=self.parametros.tolerancia_contato_px,
            passo_graus=self.parametros.passo_varredura_graus,
        )
        self._overlay_renderer = OverlayRenderer(self.parametros.estilo)

    def analisar(
        self,
        imagem: np.ndarray,
        texto_tempo: Optional[str] = None,
    ) -> ResultadoAnalise:
        """Executa o pipeline completo em uma imagem."""
        if imagem is None or imagem.size == 0:
            return ResultadoAnalise(sucesso=False, erro="Imagem vazia ou inválida")

        try:
            # 1. Segmentação
            mascara = self._segmenter.processar(imagem)
            if mascara is None or mascara.size == 0:
                return ResultadoAnalise(sucesso=False, erro="Segmentação falhou")

            # 2. Contorno
            contorno = self._extrator_contorno.extrair(mascara)
            if contorno.pontos is None or len(contorno.pontos) < 5:
                return ResultadoAnalise(
                    contorno=contorno,
                    sucesso=False,
                    erro="Contorno não encontrado",
                )

            # 3. Baseline PRIMEIRO
            baseline = self._baseline_fitter.ajustar(
                contorno.pontos,
                percentual_baixos=self.parametros.baseline_threshold,
            )
            if baseline is None:
                return ResultadoAnalise(
                    contorno=contorno,
                    sucesso=False,
                    erro="Ajuste de baseline falhou",
                )

            # 4. Elipse, VALIDADA contra a baseline
            elipse = self._ellipse_fitter.ajustar(
                contorno.pontos,
                percentual_altos=self.parametros.droplet_threshold,
                imagem_forma=imagem.shape[:2],
                baseline=baseline,
                tolerancia_baseline=self.parametros.tolerancia_baseline_elipse_px,
            )
            if elipse is None:
                return ResultadoAnalise(
                    contorno=contorno,
                    baseline=baseline,
                    sucesso=False,
                    erro="Ajuste de elipse falhou",
                )

            # 5. Ângulos
            angulos = self._angle_calculator.calcular(elipse, baseline)
            if angulos.esquerdo is None or angulos.direito is None:
                return ResultadoAnalise(
                    contorno=contorno,
                    baseline=baseline,
                    elipse=elipse,
                    angulos=angulos,
                    sucesso=False,
                    erro="Cálculo de ângulos falhou",
                )

            # 6. Overlay
            imagem_anotada = self._overlay_renderer.renderizar(
                imagem,
                contorno=contorno,
                baseline=baseline,
                elipse=elipse,
                angulos=angulos,
                roi_x1=self.parametros.roi_x1 if self.parametros.estilo.roi_desenhar else None,
                roi_x2=self.parametros.roi_x2 if self.parametros.estilo.roi_desenhar else None,
                texto_tempo=texto_tempo,
            )

            return ResultadoAnalise(
                angulos=angulos,
                contorno=contorno,
                baseline=baseline,
                elipse=elipse,
                imagem_anotada=imagem_anotada,
                sucesso=True,
            )

        except Exception as e:
            log.error(f"Erro no pipeline de análise: {e}")
            return ResultadoAnalise(sucesso=False, erro=str(e))


# ---------------------------------------------------------------------------
# Função de conveniência
# ---------------------------------------------------------------------------

def analisar_frame(
    imagem: np.ndarray,
    parametros: Optional[ParametrosAnalise] = None,
    texto_tempo: Optional[str] = None,
) -> ResultadoAnalise:
    """Atalho funcional."""
    return DropletAnalyzer(parametros).analisar(imagem, texto_tempo=texto_tempo)