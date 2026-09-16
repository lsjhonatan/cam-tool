"""
Preview sob demanda para a GUI do cam-tool.

Widget que mostra a imagem com overlay, atualizado quando o usuário
clica em "Atualizar Preview". Não atualiza sozinho (Opção B).

Estratégia: a textura é criada UMA VEZ com tamanho fixo (LARGURA_TEXTURA
x ALTURA_TEXTURA) e nunca é recriada. Para mostrar imagens menores,
usamos uv_min/uv_max para selecionar a região visível.

Uso típico:
    from cam_tool.gui.preview import PreviewWidget
    preview = PreviewWidget()
    preview.criar(parent="preview_group")
    preview.atualizar(imagem_anotada)
"""

from __future__ import annotations

from typing import Optional

import cv2
import dearpygui.dearpygui as dpg
import numpy as np

from cam_tool.log import get_logger

log = get_logger()


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TAG_TEXTURE = "preview_texture"
TAG_IMAGE = "preview_image"

# Tamanho fixo da textura (nunca recriada)
LARGURA_TEXTURA = 1920
ALTURA_TEXTURA = 1080

# Tamanho máximo exibido no preview (redimensiona mantendo proporção)
LARGURA_MAX_EXIBIR = 720
ALTURA_MAX_EXIBIR = 500


# ---------------------------------------------------------------------------
# PreviewWidget
# ---------------------------------------------------------------------------

class PreviewWidget:
    """
    Widget de preview de imagem.

    A textura é criada uma única vez (1920x1080) e preenchida com os
    dados da imagem. Para mostrar uma imagem menor, usa uv_min/uv_max
    para selecionar apenas a região usada.

    Exemplo:
        preview = PreviewWidget()
        preview.criar(parent="meu_grupo")
        preview.atualizar(imagem_bgr)
    """

    def __init__(self):
        self._criado = False

    # ------------------------------------------------------------------
    # Criação
    # ------------------------------------------------------------------

    def criar(self, parent: Optional[str] = None) -> None:
        """
        Cria os itens no Dear PyGui.

        Parâmetros:
            parent: tag do container pai (opcional). Se None, o widget
                    é adicionado ao topo da janela atual.
        """
        if self._criado:
            log.debug("PreviewWidget já foi criado")
            return

        # Cria a textura placeholder com tamanho fixo
        # (1920*1080*4 = 8.294.400 floats — um pouco pesado, mas só uma vez)
        dados_vazios = [0.0] * (LARGURA_TEXTURA * ALTURA_TEXTURA * 4)

        kwargs_textura = {"tag": TAG_TEXTURE, "parent": "texreg"}
        dpg.add_dynamic_texture(
            LARGURA_TEXTURA, ALTURA_TEXTURA, dados_vazios, **kwargs_textura
        )

        # Cria a imagem que usa a textura
        kwargs_imagem = {"tag": TAG_IMAGE, "width": 10, "height": 10}
        if parent is not None:
            kwargs_imagem["parent"] = parent

        dpg.add_image(TAG_TEXTURE, **kwargs_imagem)

        self._criado = True
        log.debug("PreviewWidget criado")

    # ------------------------------------------------------------------
    # Atualização
    # ------------------------------------------------------------------

    def atualizar(self, imagem_bgr: Optional[np.ndarray]) -> bool:
        """
        Atualiza a imagem mostrada no preview.

        Parâmetros:
            imagem_bgr: imagem BGR do OpenCV (ou None para limpar)

        Retorna True se conseguiu atualizar.
        """
        if not self._criado:
            log.warning("PreviewWidget não foi criado ainda")
            return False

        if imagem_bgr is None or imagem_bgr.size == 0:
            log.warning("Imagem vazia recebida pelo preview")
            return False

        try:
            # Redimensiona para caber na textura, mantendo proporção
            redimensionada = self._redimensionar(imagem_bgr)
            altura, largura = redimensionada.shape[:2]

            # Converte BGR → RGBA float [0, 1]
            imagem_rgba = self._para_rgba_float(redimensionada)

            # Preenche o começo da textura com a imagem
            # (o resto continua zerado, mas não é mostrado)
            n_pixels = largura * altura
            n_floats = n_pixels * 4

            if n_floats > len(imagem_rgba):
                log.warning(
                    f"Imagem maior que a textura: "
                    f"{largura}x{altura} (textura {LARGURA_TEXTURA}x{ALTURA_TEXTURA})"
                )
                # Trunca a imagem
                redimensionada = self._redimensionar_forcado(
                    imagem_bgr, LARGURA_TEXTURA, ALTURA_TEXTURA
                )
                altura, largura = redimensionada.shape[:2]
                imagem_rgba = self._para_rgba_float(redimensionada)
                n_floats = largura * altura * 4

            # Atualiza só os primeiros n_floats da textura
            # (não dá pra fazer isso direto; precisa mandar a lista toda)
            # Estratégia: monta uma lista do tamanho total, com a imagem
            # no começo e zeros no resto
            dados_textura = imagem_rgba + [0.0] * (LARGURA_TEXTURA * ALTURA_TEXTURA * 4 - n_floats)

            dpg.set_value(TAG_TEXTURE, dados_textura)

            # Ajusta uv_max para mostrar só a região usada
            u_max = largura / LARGURA_TEXTURA
            v_max = altura / ALTURA_TEXTURA
            dpg.configure_item(
                TAG_IMAGE,
                width=largura,
                height=altura,
                uv_min=(0.0, 0.0),
                uv_max=(u_max, v_max),
            )

            return True

        except Exception as e:
            log.error(f"Falha ao atualizar preview: {e}")
            return False

    def limpar(self) -> None:
        """Limpa o preview."""
        if not self._criado:
            return

        try:
            if dpg.does_item_exist(TAG_IMAGE):
                dpg.configure_item(TAG_IMAGE, width=10, height=10)
        except Exception as e:
            log.warning(f"Falha ao limpar preview: {e}")

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------

    @staticmethod
    def _redimensionar(imagem: np.ndarray) -> np.ndarray:
        """
        Redimensiona mantendo a proporção, para caber em
        (LARGURA_MAX_EXIBIR, ALTURA_MAX_EXIBIR).

        Se a imagem for maior que a textura, também reduz pra caber.
        """
        h, w = imagem.shape[:2]

        # Primeiro, limita ao tamanho máximo de exibição
        escala_exibir = min(
            LARGURA_MAX_EXIBIR / w,
            ALTURA_MAX_EXIBIR / h,
            1.0,
        )

        # Segundo, limita ao tamanho máximo da textura
        escala_textura = min(
            LARGURA_TEXTURA / w,
            ALTURA_TEXTURA / h,
            1.0,
        )

        escala = min(escala_exibir, escala_textura)

        if escala >= 1.0:
            return imagem

        nova_largura = int(w * escala)
        nova_altura = int(h * escala)

        return cv2.resize(imagem, (nova_largura, nova_altura), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _redimensionar_forcado(
        imagem: np.ndarray,
        largura_max: int,
        altura_max: int,
    ) -> np.ndarray:
        """Redimensiona forçando caber em (largura_max, altura_max)."""
        h, w = imagem.shape[:2]
        escala = min(largura_max / w, altura_max / h)
        nova_largura = int(w * escala)
        nova_altura = int(h * escala)
        return cv2.resize(imagem, (nova_largura, nova_altura), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _para_rgba_float(imagem_bgr: np.ndarray) -> list:
        """Converte BGR uint8 → lista float RGBA [0, 1]."""
        rgb = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2RGB)
        altura, largura = rgb.shape[:2]

        alfa = np.full((altura, largura, 1), 255, dtype=np.uint8)
        rgba = np.concatenate([rgb, alfa], axis=2)

        rgba_float = rgba.astype(np.float32) / 255.0
        return rgba_float.flatten().tolist()