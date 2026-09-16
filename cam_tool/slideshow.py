"""
Módulo de montagem de slideshow do cam-tool.

Responsável por:
- Receber uma lista de imagens anotadas
- Montar um GIF animado
- Montar um vídeo MP4

Uso típico:
    from cam_tool.slideshow import construir_gif, construir_mp4
    construir_gif(imagens, Path("saida.gif"), duracao_ms=500)
    construir_mp4(imagens, Path("saida.mp4"), fps=2.0)
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import cv2
import numpy as np

from cam_tool.log import get_logger

log = get_logger()


# ---------------------------------------------------------------------------
# GIF
# ---------------------------------------------------------------------------

def construir_gif(
    imagens: List[np.ndarray],
    caminho: Path,
    duracao_ms: int = 500,
    loop: int = 0,
) -> bool:
    """
    Monta um GIF animado a partir de uma lista de imagens BGR (OpenCV).

    Parâmetros:
        imagens:     lista de arrays BGR
        caminho:     caminho do arquivo .gif
        duracao_ms:  duração de cada frame em milissegundos
        loop:        0 = infinito, N = repetir N vezes

    Retorna True se sucesso, False caso contrário.
    """
    caminho = Path(caminho)

    if not imagens:
        log.error("Lista de imagens vazia; GIF não será criado")
        return False

    try:
        from PIL import Image

        caminho.parent.mkdir(parents=True, exist_ok=True)

        # Converte BGR → RGB → PIL
        frames_pil = []
        for img in imagens:
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            frames_pil.append(Image.fromarray(rgb))

        frames_pil[0].save(
            caminho,
            save_all=True,
            append_images=frames_pil[1:],
            duration=duracao_ms,
            loop=loop,
            optimize=False,
        )

        log.info(f"GIF salvo: {caminho} ({len(frames_pil)} frames, {duracao_ms}ms cada)")
        return True

    except Exception as e:
        log.error(f"Falha ao salvar GIF {caminho}: {e}")
        return False


# ---------------------------------------------------------------------------
# MP4
# ---------------------------------------------------------------------------

def construir_mp4(
    imagens: List[np.ndarray],
    caminho: Path,
    fps: float = 2.0,
    codec: str = "mp4v",
) -> bool:
    """
    Monta um vídeo MP4 a partir de uma lista de imagens BGR (OpenCV).

    Parâmetros:
        imagens:  lista de arrays BGR (todas do mesmo tamanho)
        caminho:  caminho do arquivo .mp4
        fps:      frames por segundo do vídeo de saída
        codec:    fourcc do codec (padrão: mp4v)

    Retorna True se sucesso, False caso contrário.
    """
    caminho = Path(caminho)

    if not imagens:
        log.error("Lista de imagens vazia; MP4 não será criado")
        return False

    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)

        # Todas as imagens devem ter o mesmo tamanho
        altura, largura = imagens[0].shape[:2]

        fourcc = cv2.VideoWriter_fourcc(*codec)
        writer = cv2.VideoWriter(
            str(caminho),
            fourcc,
            fps,
            (largura, altura),
        )

        if not writer.isOpened():
            log.error(f"OpenCV não conseguiu abrir o writer MP4 para {caminho}")
            return False

        for img in imagens:
            # Se alguma imagem tiver tamanho diferente, redimensiona
            if img.shape[:2] != (altura, largura):
                img = cv2.resize(img, (largura, altura))
            writer.write(img)

        writer.release()

        log.info(f"MP4 salvo: {caminho} ({len(imagens)} frames, {fps:.2f} fps)")
        return True

    except Exception as e:
        log.error(f"Falha ao salvar MP4 {caminho}: {e}")
        return False


# ---------------------------------------------------------------------------
# Despachante
# ---------------------------------------------------------------------------

def construir_slideshow(
    imagens: List[np.ndarray],
    caminho: Path,
    formato: str,
    duracao_ms: int = 500,
) -> bool:
    """
    Despacha para GIF ou MP4 conforme o formato.

    Parâmetros:
        imagens:     lista de arrays BGR
        caminho:     caminho do arquivo de saída
        formato:     "GIF" ou "MP4" (case-insensitive)
        duracao_ms:  usado para GIF (duração por frame)
                     e para MP4 (fps = 1000/duracao_ms)

    Retorna True se sucesso, False caso contrário.
    """
    formato_upper = formato.upper()

    if formato_upper == "GIF":
        return construir_gif(imagens, caminho, duracao_ms=duracao_ms)

    if formato_upper == "MP4":
        # Converte duração (ms) para fps
        fps = 1000.0 / duracao_ms if duracao_ms > 0 else 2.0
        return construir_mp4(imagens, caminho, fps=fps)

    log.error(f"Formato desconhecido: {formato}. Use 'GIF' ou 'MP4'.")
    return False