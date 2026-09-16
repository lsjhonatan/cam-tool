"""
Aba de configurações da GUI do cam-tool.

Modo atual: processamento em lote de imagens de uma pasta.

Contém:
- Seleção de pasta de imagens
- Calibração (escala nm/px, unidade)
- Configurações de fonte
- Tabela de cores
- Thresholds de análise
- Preview da primeira imagem analisada
- Botões de ação (Processar pasta, Save/Load/Reset)

Uso típico:
    from cam_tool.gui.settings_tab import SettingsTab
    tab = SettingsTab(config=cfg, analyzer=analyzer)
    tab.criar()
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from tkinter import Tk, filedialog
from typing import List, Optional

import cv2
import dearpygui.dearpygui as dpg
import numpy as np

from cam_tool.config import ConfigManager
from cam_tool.export import Medicao, exportar_xlsx, gerar_nome_planilha
from cam_tool.gui.preview import PreviewWidget
from cam_tool.gui.widgets import (
    atualizar_preview_cor,
    color_picker_row,
    input_float_com_clamp,
    input_int_com_clamp,
)
from cam_tool.image import ImageLoader, ImageWriter
from cam_tool.log import get_logger
from cam_tool.pipeline import DropletAnalyzer, ParametrosAnalise

log = get_logger()


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TAG_TAB = "settings_tab"
TAG_PASTA = "pasta_imagens"
TAG_STATUS = "status_text"

# Extensões suportadas
EXTENSOES_IMAGEM = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


# ---------------------------------------------------------------------------
# SettingsTab
# ---------------------------------------------------------------------------

class SettingsTab:
    """
    Aba principal de configurações (modo lote de imagens).

    Recebe o ConfigManager e o DropletAnalyzer do App. Cria todos
    os widgets, registra callbacks, e implementa as ações.
    """

    def __init__(self, config: ConfigManager, analyzer: DropletAnalyzer):
        self.config = config
        self.analyzer = analyzer
        self.preview = PreviewWidget()

        self._ultima_imagem_anotada: Optional[np.ndarray] = None
        self._primeira_imagem: Optional[np.ndarray] = None

    # ------------------------------------------------------------------
    # Criação
    # ------------------------------------------------------------------

    def criar(self) -> None:
        """Cria a aba dentro do tab_bar atual."""
        with dpg.tab(label="Settings", tag=TAG_TAB):
            self._secao_pasta()
            dpg.add_separator()
            self._secao_calibracao()
            dpg.add_separator()
            self._secao_fontes()
            dpg.add_separator()
            self._secao_cores()
            dpg.add_separator()
            self._secao_analise()
            dpg.add_separator()
            self._secao_preview()
            dpg.add_separator()
            self._secao_acoes()

        self.config.registrar_callback(self._on_config_changed)
        log.debug("SettingsTab criado")

    # ------------------------------------------------------------------
    # Seções
    # ------------------------------------------------------------------

    def _secao_pasta(self) -> None:
        dpg.add_text("Pasta de Imagens:")
        with dpg.table(header_row=True, width=770, policy=dpg.mvTable_SizingStretchProp):
            dpg.add_table_column(label="Pasta")
            dpg.add_table_column(label="Nº de imagens")
            dpg.add_table_column(label="Ação")
            with dpg.table_row():
                dpg.add_input_text(
                    tag=TAG_PASTA, readonly=True, width=470,
                    default_value="",
                )
                dpg.add_input_text(
                    tag="contagem_imagens", readonly=True, width=100,
                    default_value="0",
                )
                dpg.add_button(
                    label="Selecionar pasta",
                    callback=self._escolher_pasta,
                )

    def _secao_calibracao(self) -> None:
        dpg.add_text("Calibração:")
        with dpg.group(horizontal=True):
            input_float_com_clamp(
                label="Escala (nm/px)", tag="escala_nm_por_px",
                default_value=1.0, min_value=0.0001, max_value=1e6,
                step=0.1, step_fast=1.0, format="%.4f",
                callback=self._on_param_changed,
            )
            dpg.add_spacer(width=10)
            dpg.add_combo(
                label="Unidade de saída", tag="unidade_saida",
                items=["nm", "µm", "mm"], default_value="nm", width=100,
                callback=self._on_param_changed,
            )

    def _secao_fontes(self) -> None:
        dpg.add_text("Fontes dos rótulos:")
        with dpg.group(horizontal=True):
            with dpg.group():
                input_int_com_clamp(
                    label="Medidas (tamanho)", tag="measure_font_size",
                    default_value=22, min_value=1, max_value=100,
                    callback=self._on_param_changed,
                )
                input_int_com_clamp(
                    label="Medidas (espessura)", tag="measure_font_thickness",
                    default_value=1, min_value=0, max_value=10,
                    callback=self._on_param_changed,
                )
            dpg.add_spacer(width=20)
            with dpg.group():
                input_int_com_clamp(
                    label="Offset X", tag="measure_offset_x",
                    default_value=0, min_value=-2000, max_value=2000,
                    callback=self._on_param_changed,
                )
                input_int_com_clamp(
                    label="Offset Y", tag="measure_offset_y",
                    default_value=0, min_value=-2000, max_value=2000,
                    callback=self._on_param_changed,
                )

    def _secao_cores(self) -> None:
        dpg.add_text("Cores dos elementos:")
        with dpg.table(
            header_row=True, width=770,
            borders_innerH=True, borders_outerH=True,
            borders_innerV=True, borders_outerV=True,
            policy=dpg.mvTable_SizingStretchProp,
        ):
            dpg.add_table_column(label="Elemento")
            dpg.add_table_column(label="R")
            dpg.add_table_column(label="G")
            dpg.add_table_column(label="B")
            dpg.add_table_column(label="Preview")
            dpg.add_table_column(label="Cor")
            dpg.add_table_column(label="Desenhar")

            color_picker_row(
                label="Região de Interesse",
                r_tag="region_r", g_tag="region_g", b_tag="region_b",
                draw_tag="draw_region", preview_tag="preview_region",
                default_color=(255, 125, 0), default_draw=True,
                callback=self._on_cor_changed,
            )
            color_picker_row(
                label="Contorno",
                r_tag="contour_r", g_tag="contour_g", b_tag="contour_b",
                draw_tag="draw_contour", preview_tag="preview_contour",
                default_color=(255, 255, 0), default_draw=True,
                callback=self._on_cor_changed,
            )
            color_picker_row(
                label="Baseline",
                r_tag="baseline_r", g_tag="baseline_g", b_tag="baseline_b",
                draw_tag="draw_baseline", preview_tag="preview_baseline",
                default_color=(255, 0, 0), default_draw=True,
                callback=self._on_cor_changed,
            )
            color_picker_row(
                label="Linhas de Dimensão",
                r_tag="dimension_line_r", g_tag="dimension_line_g", b_tag="dimension_line_b",
                draw_tag="draw_dimension_line", preview_tag="preview_dim",
                default_color=(0, 0, 0), default_draw=True,
                callback=self._on_cor_changed,
            )
            color_picker_row(
                label="Medidas",
                r_tag="measure_r", g_tag="measure_g", b_tag="measure_b",
                draw_tag="draw_measure", preview_tag="preview_measure",
                default_color=(0, 0, 0), default_draw=True,
                callback=self._on_cor_changed,
            )
            color_picker_row(
                label="Texto de Tempo",
                r_tag="label_text_r", g_tag="label_text_g", b_tag="label_text_b",
                draw_tag="draw_label_text", preview_tag="preview_label_text",
                default_color=(0, 0, 0), default_draw=True,
                callback=self._on_cor_changed,
            )
            color_picker_row(
                label="Fundo do Rótulo",
                r_tag="label_background_r", g_tag="label_background_g", b_tag="label_background_b",
                draw_tag="draw_label_background", preview_tag="preview_label_bg",
                default_color=(255, 255, 255), default_draw=True,
                callback=self._on_cor_changed,
            )

    def _secao_analise(self) -> None:
        dpg.add_text("Análise:")
        with dpg.group(horizontal=True):
            input_float_com_clamp(
                label="Threshold baseline (%)", tag="baseline_threshold",
                default_value=15.0, min_value=0.0, max_value=100.0,
                step=1.0, step_fast=5.0, format="%.1f",
                callback=self._on_param_changed,
            )
            dpg.add_spacer(width=10)
            input_float_com_clamp(
                label="Tolerância contato (px)", tag="tolerancia_contato_px",
                default_value=3.0, min_value=0.1, max_value=50.0,
                step=0.1, step_fast=1.0, format="%.1f",
                callback=self._on_param_changed,
            )
            dpg.add_spacer(width=10)
            dpg.add_checkbox(
                label="Inverter segmentação",
                tag="inverter_segmentacao",
                default_value=True,
                callback=self._on_param_changed,
            )

    def _secao_preview(self) -> None:
        dpg.add_text("Preview (primeira imagem da pasta):")
        self.preview.criar()

    def _secao_acoes(self) -> None:
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Atualizar Preview",
                callback=self._atualizar_preview,
                width=160,
            )
            dpg.add_button(
                label="Processar pasta",
                callback=self._processar_pasta,
                width=180,
            )
        with dpg.group(horizontal=True):
            dpg.add_button(label="Salvar Config", callback=self._salvar_config, width=120)
            dpg.add_button(label="Carregar Config", callback=self._carregar_config, width=130)
            dpg.add_button(label="Resetar Config", callback=self._resetar_config, width=120)

        dpg.add_spacer(height=4)
        dpg.add_text("", tag=TAG_STATUS, color=(180, 180, 180))

    # ------------------------------------------------------------------
    # Callbacks de widget
    # ------------------------------------------------------------------

    def _on_param_changed(self, sender=None, app_data=None, user_data=None) -> None:
        if sender is None:
            return
        try:
            valor = dpg.get_value(sender)
            self.config.definir(sender, valor)
        except Exception as e:
            log.warning(f"Falha ao sincronizar {sender}: {e}")

    def _on_cor_changed(self, sender=None, app_data=None, user_data=None) -> None:
        if sender is None:
            return
        if user_data is not None and isinstance(user_data, tuple):
            try:
                r_tag, g_tag, b_tag, preview_tag = user_data
                atualizar_preview_cor(r_tag, g_tag, b_tag, preview_tag)
            except Exception as e:
                log.warning(f"Falha ao atualizar preview da cor: {e}")
        try:
            valor = dpg.get_value(sender)
            self.config.definir(sender, valor)
        except Exception as e:
            log.warning(f"Falha ao sincronizar cor {sender}: {e}")

    def _on_config_changed(self, chave: str, valor) -> None:
        params_analise = {
            "roi_x1", "roi_x2", "baseline_threshold", "tolerancia_contato_px",
            "escala_nm_por_px", "unidade_saida", "inverter_segmentacao",
        }
        if chave in params_analise:
            self._reconstruir_analyzer()

    def _reconstruir_analyzer(self) -> None:
        try:
            params = ParametrosAnalise.de_config(self.config)
            self.analyzer = DropletAnalyzer(params)
            log.debug("Analyzer reconstruído")
        except Exception as e:
            log.error(f"Falha ao reconstruir analyzer: {e}")

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------

    def _escolher_pasta(self) -> None:
        """Abre diálogo pra escolher uma pasta de imagens."""
        root = Tk()
        root.withdraw()

        pasta_atual = self.config.obter("pasta_imagens")
        if pasta_atual and Path(pasta_atual).is_dir():
            initialdir = pasta_atual
        else:
            initialdir = str(Path.home())

        pasta = filedialog.askdirectory(
            title="Selecione a pasta com imagens",
            initialdir=initialdir,
        )
        root.destroy()

        if not pasta:
            return

        pasta = str(Path(pasta).resolve())
        self.config.definir("pasta_imagens", pasta)

        # Conta imagens
        imagens = self._listar_imagens(Path(pasta))
        if dpg.does_item_exist(TAG_PASTA):
            dpg.set_value(TAG_PASTA, pasta)
        if dpg.does_item_exist("contagem_imagens"):
            dpg.set_value("contagem_imagens", str(len(imagens)))

        log.info(f"Pasta selecionada: {pasta} ({len(imagens)} imagens)")
        self._set_status(f"{len(imagens)} imagens encontradas.")

        # Atualiza preview
        self._atualizar_preview()

    def _listar_imagens(self, pasta: Path) -> List[Path]:
        """Retorna lista de imagens na pasta (não recursivo), ordenada por nome."""
        if not pasta.is_dir():
            return []
        imagens = [
            p for p in sorted(pasta.iterdir())
            if p.is_file() and p.suffix.lower() in EXTENSOES_IMAGEM
        ]
        return imagens

    def _atualizar_preview(self) -> None:
        """Lê a primeira imagem da pasta, analisa, e mostra no preview."""
        pasta = self.config.obter("pasta_imagens")
        if not pasta or not Path(pasta).is_dir():
            self._set_status("Selecione uma pasta primeiro.")
            return

        imagens = self._listar_imagens(Path(pasta))
        if not imagens:
            self._set_status("Nenhuma imagem encontrada na pasta.")
            self.preview.limpar()
            return

        try:
            primeira = imagens[0]
            frame = ImageLoader.carregar(primeira)
            if frame is None:
                self._set_status(f"Falha ao carregar: {primeira.name}")
                return

            self._primeira_imagem = frame

            resultado = self.analyzer.analisar(frame, texto_tempo=None)

            if not resultado.sucesso:
                self._set_status(f"Análise falhou: {resultado.erro}")
                self.preview.atualizar(frame)
                return

            self._ultima_imagem_anotada = resultado.imagem_anotada
            self.preview.atualizar(resultado.imagem_anotada)

            self._set_status(
                f"Preview: {primeira.name} — "
                f"L={resultado.largura_nm:.0f} "
                f"H={resultado.altura_nm:.0f} "
                f"R={resultado.raio_nm:.0f} "
                f"θ={resultado.angulo_graus:.1f}°"
            )
            log.info(
                f"Preview {primeira.name}: L={resultado.largura_nm:.0f}, "
                f"H={resultado.altura_nm:.0f}, R={resultado.raio_nm:.0f}, "
                f"θ={resultado.angulo_graus:.1f}°"
            )

        except Exception as e:
            log.error(f"Erro no preview: {e}")
            self._set_status(f"Erro: {e}")

    def _processar_pasta(self) -> None:
        """
        Processa todas as imagens da pasta.

        Para cada imagem: analisa, salva PNG anotado.
        No final: gera 1 XLSX com todas as medições.
        """
        pasta = self.config.obter("pasta_imagens")
        if not pasta or not Path(pasta).is_dir():
            self._set_status("Selecione uma pasta primeiro.")
            return

        imagens = self._listar_imagens(Path(pasta))
        if not imagens:
            self._set_status("Nenhuma imagem encontrada.")
            return

        try:
            self._set_status(f"Processando {len(imagens)} imagens...")
            log.info(f"Iniciando processamento de {len(imagens)} imagens")

            # Diretório de saída
            nome_base = Path(pasta).name or "saida"
            out_dir = Path.home() / "cam-tool" / "Output" / nome_base
            img_dir = out_dir / "Images"
            img_dir.mkdir(parents=True, exist_ok=True)

            medicoes: List[Medicao] = []
            sucessos = 0
            falhas = 0

            for i, caminho_img in enumerate(imagens):
                try:
                    frame = ImageLoader.carregar(caminho_img)
                    if frame is None:
                        log.warning(f"[{i+1}/{len(imagens)}] Falha ao carregar: {caminho_img.name}")
                        falhas += 1
                        continue

                    resultado = self.analyzer.analisar(frame, texto_tempo=None)
                    if not resultado.sucesso:
                        log.warning(
                            f"[{i+1}/{len(imagens)}] {caminho_img.name}: {resultado.erro}"
                        )
                        falhas += 1
                        continue

                    # Salva PNG anotado
                    nome_saida = f"{caminho_img.stem}_anotada.png"
                    ImageWriter.salvar(resultado.imagem_anotada, img_dir / nome_saida)

                    # Cria Medicao (tempo = 0 porque não é vídeo)
                    medicoes.append(
                        Medicao.de_resultado(resultado, tempo=float(i))
                    )

                    sucessos += 1
                    log.info(
                        f"[{i+1}/{len(imagens)}] {caminho_img.name}: "
                        f"L={resultado.largura_nm:.0f} "
                        f"H={resultado.altura_nm:.0f} "
                        f"R={resultado.raio_nm:.0f}"
                    )

                except Exception as e:
                    log.error(f"[{i+1}/{len(imagens)}] {caminho_img.name}: {e}")
                    falhas += 1

            # Gera XLSX (se houver medições)
            if medicoes:
                nome_xlsx = gerar_nome_planilha(nome_base, "xlsx")
                caminho_xlsx = out_dir / nome_xlsx
                exportar_xlsx(medicoes, caminho_xlsx)
                log.info(f"Planilha: {caminho_xlsx}")

            self._set_status(
                f"Concluído: {sucessos} sucessos, {falhas} falhas. "
                f"Saída em {out_dir}"
            )
            log.info(f"Processamento concluído: {sucessos} ok, {falhas} falhas")

        except Exception as e:
            log.error(f"Erro no processamento: {e}")
            self._set_status(f"Erro: {e}")

    # ------------------------------------------------------------------
    # Config (salvar/carregar/resetar)
    # ------------------------------------------------------------------

    def _salvar_config(self) -> None:
        try:
            caminho = Path.home() / "cam-tool" / "Settings.txt"
            self.config.caminho = caminho
            self.config.salvar()
            self._set_status(f"Config salva em {caminho}")
        except Exception as e:
            log.error(f"Falha ao salvar config: {e}")
            self._set_status(f"Erro: {e}")

    def _carregar_config(self) -> None:
        root = Tk()
        root.withdraw()
        caminho = filedialog.askopenfilename(
            title="Selecione um arquivo de configuração",
            initialdir=str(Path.home() / "cam-tool"),
            filetypes=[("Config", "*.txt"), ("Todos", "*.*")],
        )
        root.destroy()

        if not caminho:
            return

        try:
            self.config.caminho = Path(caminho)
            self.config.carregar()
            self._sincronizar_widgets_do_config()
            self._reconstruir_analyzer()
            self._set_status(f"Config carregada de {caminho}")
        except Exception as e:
            log.error(f"Falha ao carregar config: {e}")
            self._set_status(f"Erro: {e}")

    def _resetar_config(self) -> None:
        try:
            self.config.resetar()
            self._sincronizar_widgets_do_config()
            self._reconstruir_analyzer()
            self._set_status("Config resetada.")
        except Exception as e:
            log.error(f"Falha ao resetar config: {e}")
            self._set_status(f"Erro: {e}")

    def _sincronizar_widgets_do_config(self) -> None:
        """Atualiza todos os widgets da GUI com os valores do ConfigManager."""
        for chave, valor in self.config.todos().items():
            if dpg.does_item_exist(chave):
                try:
                    dpg.set_value(chave, valor)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------

    def _set_status(self, texto: str) -> None:
        """Atualiza o texto de status."""
        if dpg.does_item_exist(TAG_STATUS):
            dpg.set_value(TAG_STATUS, texto)