"""
Janela principal da GUI do cam-tool.

Orquestra:
- Criação do ConfigManager
- Criação do DropletAnalyzer
- Criação das abas (Settings, Logging)
- Loop principal do Dear PyGui

Uso típico:
    from cam_tool.gui.app import App
    app = App()
    app.run()
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import dearpygui.dearpygui as dpg

from cam_tool.config import ConfigManager
from cam_tool.gui.logging_tab import LoggingTab
from cam_tool.gui.settings_tab import SettingsTab
from cam_tool.log import get_logger
from cam_tool.pipeline import DropletAnalyzer, ParametrosAnalise

log = get_logger()


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TITULO = "cam-tool — Medição de Ângulo de Contato"
TAG_JANELA = "main_window"
LARGURA_VIEWPORT = 940
ALTURA_VIEWPORT = 1080


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class App:
    """
    Aplicação principal do cam-tool.
    """

    def __init__(self, caminho_config: Optional[Path] = None):
        if caminho_config is None:
            caminho_config = Path.home() / "cam-tool" / "Settings.txt"

        self.config = ConfigManager(caminho_config)
        self.config.carregar()

        params = ParametrosAnalise.de_config(self.config)
        self.analyzer = DropletAnalyzer(params)

        self.settings_tab: Optional[SettingsTab] = None
        self.logging_tab: Optional[LoggingTab] = None

        log.info("App inicializado")

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    def criar_interface(self) -> None:
        """Cria toda a interface gráfica."""
        dpg.create_context()

        # Texture registry (usado pelo preview)
        with dpg.texture_registry(tag="texreg"):
            pass

        # Janela principal (com TAG!)
        with dpg.window(
            label="cam-tool",
            tag=TAG_JANELA,
            no_collapse=True,
            no_close=True,
            no_move=True,
            no_resize=True,
            no_title_bar=True,
        ):
            with dpg.tab_bar(tag="main_tab_bar"):
                # Aba Settings (criada primeiro, registra callback no config)
                self.settings_tab = SettingsTab(self.config, self.analyzer)
                self.settings_tab.criar()

                # Aba Logging (criada depois, registra callback no logger)
                self.logging_tab = LoggingTab()
                self.logging_tab.criar()

        # Viewport
        dpg.create_viewport(
            title=TITULO,
            width=LARGURA_VIEWPORT,
            height=ALTURA_VIEWPORT,
        )
        dpg.setup_dearpygui()
        dpg.show_viewport()

        # Define a janela principal como primária (usando a TAG)
        dpg.set_primary_window(TAG_JANELA, True)

        log.info("Interface criada")

    # ------------------------------------------------------------------
    # Loop principal
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Roda o loop principal do Dear PyGui."""
        try:
            self.criar_interface()

            log.info("cam-tool iniciado")
            log.info(f"Config: {self.config.caminho}")

            dpg.start_dearpygui()

        except Exception as e:
            log.error(f"Erro fatal no loop principal: {e}")
            raise
        finally:
            self._finalizar()

    def _finalizar(self) -> None:
        """Limpa recursos ao sair."""
        try:
            dpg.destroy_context()
            log.info("cam-tool encerrado")
        except Exception as e:
            log.warning(f"Falha ao finalizar: {e}")