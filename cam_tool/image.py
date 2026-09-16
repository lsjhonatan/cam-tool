"""
Módulo de leitura e escrita de imagens do cam-tool.

Responsável por:
- Carregar imagens do disco (via OpenCV)
- Salvar imagens no disco (via OpenCV)
- Converter entre formatos (BGR, RGB, RGBA)
- Validar imagens carregadas

Uso típico:
    from cam_tool.image import ImageLoader, ImageWriter, bgr_para_rgb
    img = ImageLoader.carregar(Path("foto.png"))
    ImageWriter.salvar(img, Path("saida.png"))
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from cam_tool.log import get_logger

log = get_logger()


# ---------------------------------------------------------------------------
# Conversões de cor
# ---------------------------------------------------------------------------

def bgr_para_rgb(img: np.ndarray) -> np.ndarray:
    """Converte imagem BGR (OpenCV) para RGB (PIL/GTK)."""
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def rgb_para_bgr(img: np.ndarray) -> np.ndarray:
    """Converte imagem RGB (PIL/GTK) para BGR (OpenCV)."""
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def bgr_para_rgba(img: np.ndarray) -> np.ndarray:
    """Converte imagem BGR para RGBA (adiciona canal alfa opaco)."""
    rgb = bgr_para_rgb(img)
    alfa = np.full((*rgb.shape[:2], 1), 255, dtype=np.uint8)
    return np.concatenate([rgb, alfa], axis=2)


def rgba_para_bgr(img: np.ndarray) -> np.ndarray:
    """Converte imagem RGBA para BGR (descarta canal alfa)."""
    return cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

class ImageLoader:
    """Carrega imagens do disco."""

    @staticmethod
    def carregar(caminho: Path) -> Optional[np.ndarray]:
        """
        Carrega uma imagem do disco.

        Retorna a imagem como array NumPy no formato BGR (padrão OpenCV),
        ou None se falhar.

        Suporta qualquer formato que o OpenCV suporte (PNG, JPG, BMP, TIFF...).
        """
        caminho = Path(caminho)

        if not caminho.is_file():
            log.error(f"Arquivo de imagem não encontrado: {caminho}")
            return None

        try:
            img = cv2.imread(str(caminho), cv2.IMREAD_COLOR)
            if img is None:
                log.error(f"OpenCV não conseguiu ler: {caminho}")
                return None

            log.info(f"Imagem carregada: {caminho.name} ({img.shape[1]}x{img.shape[0]})")
            return img

        except Exception as e:
            log.error(f"Falha ao carregar imagem {caminho}: {e}")
            return None

    @staticmethod
    def carregar_com_alfa(caminho: Path) -> Optional[np.ndarray]:
        """
        Carrega uma imagem mantendo o canal alfa (se houver).

        Retorna RGBA (não BGR), útil para sobreposição em GUIs.
        """
        caminho = Path(caminho)

        if not caminho.is_file():
            log.error(f"Arquivo de imagem não encontrado: {caminho}")
            return None

        try:
            img = cv2.imread(str(caminho), cv2.IMREAD_UNCHANGED)
            if img is None:
                log.error(f"OpenCV não conseguiu ler: {caminho}")
                return None

            # Se já tem 4 canais, converte BGR→RGBA
            if img.shape[2] == 4:
                return cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)

            # Se tem 3 canais, adiciona alfa opaco
            if img.shape[2] == 3:
                return bgr_para_rgba(img)

            # Se tem 1 canal (grayscale), converte para RGBA
            return cv2.cvtColor(img, cv2.COLOR_GRAY2RGBA)

        except Exception as e:
            log.error(f"Falha ao carregar imagem com alfa {caminho}: {e}")
            return None


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------

class ImageWriter:
    """Salva imagens no disco."""

    @staticmethod
    def salvar(img: np.ndarray, caminho: Path) -> bool:
        """
        Salva uma imagem no disco.

        Cria os diretórios pais se não existirem.
        Retorna True em caso de sucesso, False caso contrário.
        """
        caminho = Path(caminho)

        try:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            sucesso = cv2.imwrite(str(caminho), img)

            if sucesso:
                log.info(f"Imagem salva: {caminho}")
            else:
                log.error(f"OpenCV não conseguiu salvar: {caminho}")

            return sucesso

        except Exception as e:
            log.error(f"Falha ao salvar imagem {caminho}: {e}")
            return False


# ---------------------------------------------------------------------------
# Redimensionamento
# ---------------------------------------------------------------------------

def redimensionar_para_caber(
    img: np.ndarray,
    largura_max: int,
    altura_max: int,
    manter_proporcao: bool = True,
) -> np.ndarray:
    """
    Redimensiona a imagem para caber dentro de (largura_max, altura_max),
    mantendo a proporção.

    Se a imagem já for menor, retorna sem alterar.
    """
    h, w = img.shape[:2]

    if w <= largura_max and h <= altura_max:
        return img

    if manter_proporcao:
        escala = min(largura_max / w, altura_max / h)
        nova_largura = int(w * escala)
        nova_altura = int(h * escala)
    else:
        nova_largura = largura_max
        nova_altura = altura_max

    return cv2.resize(img, (nova_largura, nova_altura), interpolation=cv2.INTER_AREA)