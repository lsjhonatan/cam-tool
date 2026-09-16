"""
Módulo de logging do cam-tool.

Fornece uma interface unificada de logging que:
- Escreve no stderr (para o terminal)
- Escreve em um arquivo de log (opcional)
- Pode notificar callbacks (para a GUI mostrar na aba Logging)

Uso típico:
    from cam_tool.log import get_logger
    log = get_logger()
    log.info("Mensagem informativa")
    log.warning("Algo suspeito")
    log.error("Algo deu errado")
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------

_FORMATO_ARQUIVO = "%(asctime)s [%(levelname)s] %(message)s"
_FORMATO_TERMINAL = "[%(levelname)s] %(message)s"
_FORMATO_DATA = "%Y-%m-%d %H:%M:%S"

# Callbacks externos (ex: GUI) que querem receber cada mensagem.
# Estrutura: lista de funções que recebem (nível: str, mensagem: str)
_callbacks: List[Callable[[str, str], None]] = []


# ---------------------------------------------------------------------------
# Handler customizado: encaminha mensagens para callbacks externos
# ---------------------------------------------------------------------------

class _CallbackHandler(logging.Handler):
    """Handler que envia cada registro de log para callbacks registrados."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            mensagem = self.format(record)
            for callback in _callbacks:
                try:
                    callback(record.levelname, mensagem)
                except Exception:
                    # Nunca deixar uma falha de callback derrubar o logging
                    pass
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

_logger: Optional[logging.Logger] = None


def get_logger(
    nome: str = "cam_tool",
    arquivo: Optional[Path] = None,
    nivel: int = logging.INFO,
) -> logging.Logger:
    """
    Retorna o logger global do cam-tool, configurado uma única vez.

    Parâmetros:
        nome:    nome do logger (padrão: "cam_tool")
        arquivo: caminho opcional para arquivo de log
        nivel:   nível mínimo (padrão: INFO)

    Retorna:
        Instância de logging.Logger configurada.
    """
    global _logger

    if _logger is not None:
        return _logger

    logger = logging.getLogger(nome)
    logger.setLevel(nivel)
    logger.propagate = False  # não deixa o root logger duplicar mensagens

    # Handler 1: terminal (stderr)
    handler_terminal = logging.StreamHandler(sys.stderr)
    handler_terminal.setFormatter(logging.Formatter(_FORMATO_TERMINAL))
    logger.addHandler(handler_terminal)

    # Handler 2: callbacks externos (GUI)
    handler_callback = _CallbackHandler()
    handler_callback.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler_callback)

    # Handler 3: arquivo (opcional)
    if arquivo is not None:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        handler_arquivo = logging.FileHandler(arquivo, encoding="utf-8")
        handler_arquivo.setFormatter(logging.Formatter(_FORMATO_ARQUIVO, _FORMATO_DATA))
        logger.addHandler(handler_arquivo)

    _logger = logger
    return logger


def registrar_callback(callback: Callable[[str, str], None]) -> None:
    """
    Registra uma função para receber cada mensagem de log.

    A função recebe dois argumentos: (nível, mensagem).
    Exemplo de uso na GUI:

        def on_log(nivel, mensagem):
            minha_textview.append(mensagem)

        registrar_callback(on_log)
    """
    _callbacks.append(callback)


def remover_callback(callback: Callable[[str, str], None]) -> None:
    """Remove um callback previamente registrado."""
    if callback in _callbacks:
        _callbacks.remove(callback)


def configurar_arquivo_log(diretorio: Path) -> Path:
    """
    Cria um arquivo de log com timestamp dentro do diretório informado
    e adiciona um handler para ele.

    Retorna o caminho do arquivo criado.
    """
    diretorio.mkdir(parents=True, exist_ok=True)
    nome = datetime.now().strftime("log_%Y-%m-%d_%H-%M-%S.txt")
    caminho = diretorio / nome

    logger = get_logger()
    handler = logging.FileHandler(caminho, encoding="utf-8")
    handler.setFormatter(logging.Formatter(_FORMATO_ARQUIVO, _FORMATO_DATA))
    logger.addHandler(handler)

    return caminho