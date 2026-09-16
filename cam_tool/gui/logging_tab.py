"""
Aba de log da GUI do cam-tool.

Mostra as mensagens de log em tempo real, com botões para limpar
e salvar em arquivo.

Uso típico:
    from cam_tool.gui.logging_tab import LoggingTab
    tab = LoggingTab()
    tab.criar()
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import dearpygui.dearpygui as dpg

from cam_tool.log import get_logger, registrar_callback

log = get_logger()


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TAG_LOG_TEXT = "log_text"
TAG_LOG_GROUP = "log_group"


# ---------------------------------------------------------------------------
# LoggingTab
# ---------------------------------------------------------------------------

class LoggingTab:
    """
    Aba de log da GUI.

    Recebe mensagens do logger (via registrar_callback) e mostra
    na área de texto. Tem botões para limpar e salvar.

    Exemplo:
        tab = LoggingTab()
        tab.criar()
    """

    def __init__(self):
        self._criado = False
        self._log_texto = ""

    # ------------------------------------------------------------------
    # Criação
    # ------------------------------------------------------------------

    def criar(self) -> None:
        """
        Cria a aba dentro do tab_bar atual.

        Deve ser chamado dentro de um contexto de `dpg.tab_bar()`.
        """
        if self._criado:
            log.debug("LoggingTab já foi criado")
            return

        with dpg.tab(label="Logging", tag="logging_tab"):
            dpg.add_text("Mensagens de log:")
            dpg.add_spacer(height=4)

            # Área de texto (readonly, multilinha)
            dpg.add_input_text(
                tag=TAG_LOG_TEXT,
                multiline=True,
                readonly=True,
                width=770,
                height=500,
                default_value="",
            )

            dpg.add_spacer(height=4)

            # Botões
            with dpg.group(horizontal=True):
                dpg.add_button(
                    label="Limpar Log",
                    callback=self._limpar,
                )
                dpg.add_button(
                    label="Salvar Log em Arquivo",
                    callback=self._salvar,
                )

        self._criado = True

        # Registra o callback pra receber mensagens do logger
        registrar_callback(self._on_log)

        log.debug("LoggingTab criado")

    # ------------------------------------------------------------------
    # Callback do logger
    # ------------------------------------------------------------------

    def _on_log(self, nivel: str, mensagem: str) -> None:
        """
        Recebe cada mensagem do logger e adiciona na área de texto.

        Este callback é chamado pelo módulo `cam_tool.log` sempre que
        uma mensagem é emitida.
        """
        try:
            # Adiciona timestamp e nível
            timestamp = datetime.now().strftime("%H:%M:%S")
            linha = f"[{timestamp}] [{nivel}] {mensagem}\n"

            self._log_texto += linha

            # Limita o buffer a ~1000 linhas
            if self._log_texto.count("\n") > 1000:
                linhas = self._log_texto.split("\n")
                self._log_texto = "\n".join(linhas[-500:])

            if dpg.does_item_exist(TAG_LOG_TEXT):
                dpg.set_value(TAG_LOG_TEXT, self._log_texto)

                # Auto-scroll pro final
                # (o Dear PyGui não tem auto-scroll nativo, mas
                # movendo o cursor pro final dá uma sensação parecida)
                try:
                    dpg.set_item_callback(TAG_LOG_TEXT, None)
                except Exception:
                    pass

        except Exception as e:
            # Nunca deixar uma falha do callback derrubar o programa
            print(f"[ERRO no LoggingTab] {e}")

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------

    def _limpar(self) -> None:
        """Limpa a área de log."""
        self._log_texto = ""
        if dpg.does_item_exist(TAG_LOG_TEXT):
            dpg.set_value(TAG_LOG_TEXT, "")
        log.info("Log limpo.")

    def _salvar(self) -> None:
        """Salva o log atual em um arquivo no diretório do projeto."""
        try:
            # Diretório de log
            log_dir = Path.home() / "cam-tool" / "Log"
            log_dir.mkdir(parents=True, exist_ok=True)

            # Nome com timestamp
            timestamp = datetime.now().strftime("[%d-%m-%Y_%H.%M.%S]")
            caminho = log_dir / f"log_{timestamp}.txt"

            # Escreve
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(self._log_texto)

            log.info(f"Log salvo em {caminho}")

        except Exception as e:
            log.error(f"Falha ao salvar log: {e}")