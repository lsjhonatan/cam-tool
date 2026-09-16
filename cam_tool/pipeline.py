"""
Módulo de pipeline do cam-tool.

Orquestra todas as etapas da análise de uma gota:
    1. Segmentação
    2. Extração de contorno
    3. Ajuste de baseline
    4. Medições (largura, altura, raio, volume, área, ângulo)
    5. Renderização do overlay

Uso típico:
    from cam_tool.pipeline import DropletAnalyzer, ParametrosAnalise
    analyzer = DropletAnalyzer(ParametrosAnalise(roi_x1=750, roi_x2=1700))
    resultado = analyzer.analisar(frame)
    resultado.medidas.largura_nm
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from cam_tool.baseline import BaselineFitter, LinhaBase
from cam_tool.contour import ContourExtractor, ResultadoContorno
from cam_tool.log import get_logger
from cam_tool.measurements import MedidasGota, MedidorGota
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
    tolerancia_contato_px: float = 3.0
    escala_nm_por_px: float = 1.0
    unidade_saida: str = "nm"
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

            baseline_cor=(cfg.obter("baseline_b"), cfg.obter("baseline_g"), cfg.obter("baseline_r")),
            baseline_desenhar=cfg.obter("draw_baseline"),

            medida_cor=(cfg.obter("measure_b"), cfg.obter("measure_g"), cfg.obter("measure_r")),
            medida_desenhar=cfg.obter("draw_measure"),
            medida_fonte_tamanho=cfg.obter("measure_font_size"),
            medida_fonte_espessura=cfg.obter("measure_font_thickness"),
            medida_offset=(cfg.obter("measure_offset_x"), cfg.obter("measure_offset_y")),

            linha_dimensao_cor=(
                cfg.obter("dimension_line_b"),
                cfg.obter("dimension_line_g"),
                cfg.obter("dimension_line_r"),
            ),
            linha_dimensao_desenhar=cfg.obter("draw_dimension_line"),

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
            tolerancia_contato_px=cfg.obter("tolerancia_contato_px"),
            escala_nm_por_px=cfg.obter("escala_nm_por_px"),
            unidade_saida=cfg.obter("unidade_saida"),
            estilo=estilo,
        )


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class ResultadoAnalise:
    """Resultado completo de uma análise de gota."""
    medidas: Optional[MedidasGota] = None
    contorno: Optional[ResultadoContorno] = None
    baseline: Optional[LinhaBase] = None
    imagem_anotada: Optional[np.ndarray] = None
    sucesso: bool = False
    erro: Optional[str] = None

    # Atalhos convenientes
    @property
    def largura_nm(self) -> Optional[float]:
        return self.medidas.largura_nm if self.medidas else None

    @property
    def altura_nm(self) -> Optional[float]:
        return self.medidas.altura_nm if self.medidas else None

    @property
    def raio_nm(self) -> Optional[float]:
        return self.medidas.raio_nm if self.medidas else None

    @property
    def angulo_graus(self) -> Optional[float]:
        return self.medidas.angulo_graus if self.medidas else None


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
        self._medidor = MedidorGota(
            tolerancia_contato_px=self.parametros.tolerancia_contato_px,
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

            # 3. Baseline
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

            # 4. Medições
            medidas = self._medidor.medir(
                contorno,
                baseline,
                escala_nm_por_px=self.parametros.escala_nm_por_px,
            )
            if medidas is None:
                return ResultadoAnalise(
                    contorno=contorno,
                    baseline=baseline,
                    sucesso=False,
                    erro="Medição falhou",
                )

            # 5. Overlay
            imagem_anotada = self._overlay_renderer.renderizar(
                imagem,
                contorno=contorno,
                baseline=baseline,
                medidas=medidas,
                roi_x1=self.parametros.roi_x1 if self.parametros.estilo.roi_desenhar else None,
                roi_x2=self.parametros.roi_x2 if self.parametros.estilo.roi_desenhar else None,
                texto_tempo=texto_tempo,
                unidade=self.parametros.unidade_saida,
            )

            return ResultadoAnalise(
                medidas=medidas,
                contorno=contorno,
                baseline=baseline,
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