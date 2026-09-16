"""
Aba de configurações da GUI do cam-tool.

Contém todos os controles da aplicação:
- Seleção de vídeo
- Calibração (escala nm/px, unidade)
- Configurações de fonte
- Tabela de cores
- Configurações de coleta (num_images, ROI, etc.)
- Configurações de compilação (formato, duração)
- Thresholds de análise
- Preview da imagem analisada
- Botões de ação (Save/Load/Reset Settings, Atualizar Preview, Compile)

Uso típico:
    from cam_tool.gui.settings_tab import SettingsTab
    tab = SettingsTab(config=cfg, analyzer=analyzer)
    tab.criar()
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from tkinter import Tk, filedialog
from typing import Optional

import cv2
import dearpygui.dearpygui as dpg
import numpy as np

from cam_tool.config import ConfigManager
from cam_tool.export import Medicao, exportar_csv, exportar_xlsx, gerar_nome_planilha
from cam_tool.gui.preview import PreviewWidget
from cam_tool.gui.widgets import (
    atualizar_preview_cor,
    color_picker_row,
    input_float_com_clamp,
    input_int_com_clamp,
)
from cam_tool.log import get_logger
from cam_tool.pipeline import DropletAnalyzer, ParametrosAnalise
from cam_tool.slideshow import construir_slideshow
from cam_tool.video import VideoReader, formatar_tempo

log = get_logger()


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TAG_TAB = "settings_tab"
TAG_VIDEO_NAME = "video_file_name"
TAG_VIDEO_PATH = "video_file_path"
TAG_STATUS = "status_text"


# ---------------------------------------------------------------------------
# SettingsTab
# ---------------------------------------------------------------------------

class SettingsTab:
    """
    Aba principal de configurações.

    Recebe o ConfigManager e o DropletAnalyzer do App. Cria todos
    os widgets, registra callbacks, e implementa as ações
    (atualizar preview, compilar slideshow, salvar/carregar config).
    """

    def __init__(self, config: ConfigManager, analyzer: DropletAnalyzer):
        self.config = config
        self.analyzer = analyzer
        self.preview = PreviewWidget()

        self._ultima_imagem_anotada: Optional[np.ndarray] = None
        self._ultimo_frame: Optional[np.ndarray] = None

    # ------------------------------------------------------------------
    # Criação
    # ------------------------------------------------------------------

    def criar(self) -> None:
        """Cria a aba dentro do tab_bar atual."""
        with dpg.tab(label="Settings", tag=TAG_TAB):
            self._secao_video()
            dpg.add_separator()
            self._secao_calibracao()
            dpg.add_separator()
            self._secao_fontes()
            dpg.add_separator()
            self._secao_cores()
            dpg.add_separator()
            self._secao_coleta()
            dpg.add_separator()
            self._secao_compilacao()
            dpg.add_separator()
            self._secao_analise()
            dpg.add_separator()
            self._secao_preview()
            dpg.add_separator()
            self._secao_acoes()

        # Registra callback no config pra reconstruir analyzer quando params mudam
        self.config.registrar_callback(self._on_config_changed)

        log.debug("SettingsTab criado")

    # ------------------------------------------------------------------
    # Seções
    # ------------------------------------------------------------------

    def _secao_video(self) -> None:
        dpg.add_text("Arquivo de Vídeo:")
        with dpg.table(header_row=True, width=770, policy=dpg.mvTable_SizingStretchProp):
            dpg.add_table_column(label="Vídeo")
            dpg.add_table_column(label="Caminho")
            dpg.add_table_column(label="Ação")
            with dpg.table_row():
                dpg.add_input_text(
                    tag=TAG_VIDEO_NAME, readonly=True, width=180,
                    default_value="",
                )
                dpg.add_input_text(
                    tag=TAG_VIDEO_PATH, readonly=True, width=470,
                    default_value="",
                )
                dpg.add_button(
                    label="Selecionar vídeo",
                    callback=self._escolher_video,
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
                    label="Tempo (tamanho)", tag="label_font_size",
                    default_value=20, min_value=1, max_value=100,
                    callback=self._on_param_changed,
                )
                input_int_com_clamp(
                    label="Tempo (espessura)", tag="label_font_thickness",
                    default_value=0, min_value=0, max_value=10,
                    callback=self._on_param_changed,
                )
            dpg.add_spacer(width=20)
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

            # Linha 1: ROI
            color_picker_row(
                label="Região de Interesse",
                r_tag="region_r", g_tag="region_g", b_tag="region_b",
                draw_tag="draw_region", preview_tag="preview_region",
                default_color=(255, 125, 0), default_draw=True,
                callback=self._on_cor_changed,
            )
            # Linha 2: Contorno
            color_picker_row(
                label="Contorno",
                r_tag="contour_r", g_tag="contour_g", b_tag="contour_b",
                draw_tag="draw_contour", preview_tag="preview_contour",
                default_color=(255, 255, 0), default_draw=True,
                callback=self._on_cor_changed,
            )
            # Linha 3: Baseline
            color_picker_row(
                label="Baseline",
                r_tag="baseline_r", g_tag="baseline_g", b_tag="baseline_b",
                draw_tag="draw_baseline", preview_tag="preview_baseline",
                default_color=(255, 0, 0), default_draw=True,
                callback=self._on_cor_changed,
            )
            # Linha 4: Linhas de dimensão
            color_picker_row(
                label="Linhas de Dimensão",
                r_tag="dimension_line_r", g_tag="dimension_line_g", b_tag="dimension_line_b",
                draw_tag="draw_dimension_line", preview_tag="preview_dim",
                default_color=(0, 0, 0), default_draw=True,
                callback=self._on_cor_changed,
            )
            # Linha 5: Medidas
            color_picker_row(
                label="Medidas",
                r_tag="measure_r", g_tag="measure_g", b_tag="measure_b",
                draw_tag="draw_measure", preview_tag="preview_measure",
                default_color=(0, 0, 0), default_draw=True,
                callback=self._on_cor_changed,
            )
            # Linha 6: Texto de tempo
            color_picker_row(
                label="Texto de Tempo",
                r_tag="label_text_r", g_tag="label_text_g", b_tag="label_text_b",
                draw_tag="draw_label_text", preview_tag="preview_label_text",
                default_color=(0, 0, 0), default_draw=True,
                callback=self._on_cor_changed,
            )
            # Linha 7: Fundo do rótulo
            color_picker_row(
                label="Fundo do Rótulo",
                r_tag="label_background_r", g_tag="label_background_g", b_tag="label_background_b",
                draw_tag="draw_label_background", preview_tag="preview_label_bg",
                default_color=(255, 255, 255), default_draw=True,
                callback=self._on_cor_changed,
            )

    def _secao_coleta(self) -> None:
        dpg.add_text("Coleta de imagens:")
        with dpg.group(horizontal=True):
            with dpg.group():
                input_int_com_clamp(
                    label="Número de imagens", tag="num_images",
                    default_value=10, min_value=1, max_value=10000,
                    callback=self._on_param_changed,
                )
                input_float_com_clamp(
                    label="Intervalo (s)", tag="time_increment",
                    default_value=1.0, min_value=0.001, max_value=3600.0,
                    step=0.1, step_fast=1.0, format="%.2f",
                    callback=self._on_param_changed,
                )
                input_float_com_clamp(
                    label="Tempo inicial (s)", tag="start_time",
                    default_value=8.0, min_value=0.0, max_value=100000.0,
                    step=0.1, step_fast=1.0, format="%.2f",
                    callback=self._on_param_changed,
                )
            dpg.add_spacer(width=20)
            with dpg.group():
                input_int_com_clamp(
                    label="ROI x1", tag="roi_x1",
                    default_value=750, min_value=0, max_value=100000,
                    callback=self._on_param_changed,
                )
                input_int_com_clamp(
                    label="ROI x2", tag="roi_x2",
                    default_value=1700, min_value=1, max_value=100000,
                    callback=self._on_param_changed,
                )

    def _secao_compilacao(self) -> None:
        dpg.add_text("Compilação:")
        with dpg.group(horizontal=True):
            input_float_com_clamp(
                label="Duração por imagem (s)", tag="img_duration",
                default_value=0.5, min_value=0.1, max_value=5.0,
                step=0.1, step_fast=0.5, format="%.1f",
                callback=self._on_param_changed,
            )
            dpg.add_spacer(width=10)
            dpg.add_combo(
                label="Formato", tag="output_format",
                items=["GIF", "MP4"], default_value="GIF", width=100,
                callback=self._on_param_changed,
            )
            dpg.add_spacer(width=10)
            dpg.add_input_text(
                label="Sufixo de tempo", tag="txt_suffix",
                default_value="s", width=80,
                callback=self._on_param_changed,
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

    def _secao_preview(self) -> None:
        dpg.add_text("Preview:")
        self.preview.criar()

    def _secao_acoes(self) -> None:
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Atualizar Preview",
                callback=self._atualizar_preview,
                width=160,
            )
            dpg.add_button(
                label="Compilar Slideshow",
                callback=self._compilar_slideshow,
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
        """
        Chamado quando um parâmetro numérico muda.

        Sincroniza o valor do widget com o ConfigManager.
        """
        if sender is None:
            return

        tag = sender
        try:
            valor = dpg.get_value(tag)
            self.config.definir(tag, valor)
        except Exception as e:
            log.warning(f"Falha ao sincronizar {tag}: {e}")

    def _on_cor_changed(self, sender=None, app_data=None, user_data=None) -> None:
        """
        Chamado quando uma cor ou checkbox "draw" muda.

        Atualiza o preview visual da cor e sincroniza com o ConfigManager.
        """
        if sender is None:
            return

        # Atualiza preview visual da cor
        if user_data is not None and isinstance(user_data, tuple):
            try:
                r_tag, g_tag, b_tag, preview_tag = user_data
                atualizar_preview_cor(r_tag, g_tag, b_tag, preview_tag)
            except Exception as e:
                log.warning(f"Falha ao atualizar preview da cor: {e}")

        # Sincroniza valor com o config
        try:
            valor = dpg.get_value(sender)
            self.config.definir(sender, valor)
        except Exception as e:
            log.warning(f"Falha ao sincronizar cor {sender}: {e}")

    def _on_config_changed(self, chave: str, valor) -> None:
        """
        Chamado quando um valor do config muda.

        Reconstrói o analyzer se algum parâmetro de análise mudou.
        """
        # Parâmetros que afetam a análise
        params_analise = {
            "roi_x1", "roi_x2", "baseline_threshold", "tolerancia_contato_px",
            "escala_nm_por_px", "unidade_saida",
        }
        if chave in params_analise:
            self._reconstruir_analyzer()

    def _reconstruir_analyzer(self) -> None:
        """Recria o DropletAnalyzer com os parâmetros atuais do config."""
        try:
            params = ParametrosAnalise.de_config(self.config)
            self.analyzer = DropletAnalyzer(params)
            log.debug("Analyzer reconstruído com novos parâmetros")
        except Exception as e:
            log.error(f"Falha ao reconstruir analyzer: {e}")

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------

    def _escolher_video(self) -> None:
        """Abre diálogo pra escolher um vídeo."""
        root = Tk()
        root.withdraw()

        # Diretório inicial
        caminho_atual = self.config.obter("video_file_path")
        if caminho_atual and Path(caminho_atual).is_file():
            initialdir = str(Path(caminho_atual).parent)
        else:
            initialdir = str(Path.home())

        caminho = filedialog.askopenfilename(
            title="Selecione um vídeo",
            initialdir=initialdir,
            filetypes=[
                ("Vídeos", "*.mp4 *.avi *.mov *.mkv"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        root.destroy()

        if not caminho:
            return

        # Atualiza config
        self.config.definir("video_file_path", caminho)
        self.config.definir("video_file_name", Path(caminho).name)

        # Atualiza UI
        if dpg.does_item_exist(TAG_VIDEO_PATH):
            dpg.set_value(TAG_VIDEO_PATH, caminho)
        if dpg.does_item_exist(TAG_VIDEO_NAME):
            dpg.set_value(TAG_VIDEO_NAME, Path(caminho).name)

        self._set_status(f"Vídeo carregado: {Path(caminho).name}")
        log.info(f"Vídeo selecionado: {caminho}")

        # Atualiza preview automaticamente
        self._atualizar_preview()

    def _atualizar_preview(self) -> None:
        """Lê um frame do vídeo, analisa, e mostra no preview."""
        caminho = self.config.obter("video_file_path")
        if not caminho or not Path(caminho).is_file():
            self._set_status("Selecione um vídeo primeiro.")
            return

        try:
            with VideoReader(Path(caminho)) as video:
                # Frame no tempo inicial
                tempo = self.config.obter("start_time")
                if tempo > video.duracao:
                    tempo = 0.0

                frame = video.ler_frame_em(tempo)
                if frame is None:
                    self._set_status("Não foi possível ler o frame.")
                    return

                self._ultimo_frame = frame

                # Analisa
                texto_tempo = f"{tempo:.0f} {self.config.obter('txt_suffix')}"
                resultado = self.analyzer.analisar(frame, texto_tempo=texto_tempo)

                if not resultado.sucesso:
                    self._set_status(f"Análise falhou: {resultado.erro}")
                    self.preview.atualizar(frame)
                    return

                self._ultima_imagem_anotada = resultado.imagem_anotada
                self.preview.atualizar(resultado.imagem_anotada)

                self._set_status(
                    f"Preview atualizado: "
                    f"L={resultado.largura_nm:.0f}nm "
                    f"H={resultado.altura_nm:.0f}nm "
                    f"R={resultado.raio_nm:.0f}nm "
                    f"θ={resultado.angulo_graus:.1f}°"
                )
                log.info(
                    f"Preview: L={resultado.largura_nm:.0f}nm, "
                    f"H={resultado.altura_nm:.0f}nm, "
                    f"R={resultado.raio_nm:.0f}nm, "
                    f"θ={resultado.angulo_graus:.1f}°"
                )

        except Exception as e:
            log.error(f"Erro no preview: {e}")
            self._set_status(f"Erro: {e}")

    def _compilar_slideshow(self) -> None:
        """Processa vários frames, gera imagens + slideshow + planilha."""
        caminho = self.config.obter("video_file_path")
        if not caminho or not Path(caminho).is_file():
            self._set_status("Selecione um vídeo primeiro.")
            return

        try:
            self._set_status("Processando...")
            log.info("Iniciando compilação do slideshow...")

            num_images = self.config.obter("num_images")
            tempo_inicial = self.config.obter("start_time")
            intervalo = self.config.obter("time_increment")
            img_duration = self.config.obter("img_duration")
            formato = self.config.obter("output_format")
            sufixo = self.config.obter("txt_suffix")
            escala = self.config.obter("escala_nm_por_px")

            # Diretório de saída
            nome_base = Path(caminho).stem
            out_dir = Path.home() / "cam-tool" / "Output" / nome_base
            img_dir = out_dir / "Images"
            img_dir.mkdir(parents=True, exist_ok=True)

            frames_anotados = []
            medicoes = []

            with VideoReader(Path(caminho)) as video:
                for i in range(num_images):
                    tempo_abs = tempo_inicial + i * intervalo
                    if tempo_abs > video.duracao:
                        log.warning(f"Frame {i} excede duração do vídeo; parando.")
                        break

                    frame = video.ler_frame_em(tempo_abs)
                    if frame is None:
                        continue

                    tempo_rel = tempo_abs - tempo_inicial
                    texto_tempo = f"{tempo_rel:.0f} {sufixo}"

                    resultado = self.analyzer.analisar(frame, texto_tempo=texto_tempo)
                    if not resultado.sucesso:
                        log.warning(f"Frame {i} falhou: {resultado.erro}")
                        continue

                    frames_anotados.append(resultado.imagem_anotada)
                    medicoes.append(Medicao.de_resultado(resultado, tempo=tempo_rel))

                    # Salva imagem anotada
                    nome_img = f"frame_{tempo_rel:.1f}{sufixo}.png"
                    cv2.imwrite(str(img_dir / nome_img), resultado.imagem_anotada)

            if not frames_anotados:
                self._set_status("Nenhum frame processado com sucesso.")
                return

            # Monta slideshow
            ext = formato.lower()
            caminho_slideshow = out_dir / f"{nome_base}.{ext}"
            sucesso = construir_slideshow(
                frames_anotados,
                caminho_slideshow,
                formato=formato,
                duracao_ms=int(img_duration * 1000),
            )

            if not sucesso:
                self._set_status("Falha ao montar slideshow.")
                return

            # Salva planilha
            nome_xlsx = gerar_nome_planilha(nome_base, "xlsx")
            caminho_xlsx = out_dir / nome_xlsx
            exportar_xlsx(medicoes, caminho_xlsx)

            self._set_status(
                f"Concluído: {len(frames_anotados)} frames, "
                f"{formato}, planilha salva."
            )
            log.info(f"Slideshow concluído: {caminho_slideshow}")
            log.info(f"Planilha: {caminho_xlsx}")

        except Exception as e:
            log.error(f"Erro na compilação: {e}")
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