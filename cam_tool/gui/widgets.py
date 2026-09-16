"""
Widgets customizados para a GUI do cam-tool.

Cada widget é uma função que cria um conjunto de itens no Dear PyGui
e devolve as tags criadas, para o chamador poder manipulá-las depois.

Uso típico:
    from cam_tool.gui.widgets import color_picker_row
    color_picker_row(
        label="Baseline",
        r_tag="baseline_r",
        g_tag="baseline_g",
        b_tag="baseline_b",
        draw_tag="draw_baseline",
        preview_tag="preview_baseline",
        default_color=(255, 0, 0),
        default_draw=True,
        callback=update_color_and_preview,
    )
"""

from __future__ import annotations

from typing import Callable, Optional

import dearpygui.dearpygui as dpg

from cam_tool.log import get_logger

log = get_logger()


# ---------------------------------------------------------------------------
# Color picker row
# ---------------------------------------------------------------------------

def color_picker_row(
    label: str,
    r_tag: str,
    g_tag: str,
    b_tag: str,
    draw_tag: Optional[str],
    preview_tag: str,
    default_color: tuple[int, int, int] = (255, 0, 0),
    default_draw: bool = True,
    callback: Optional[Callable] = None,
) -> dict:
    """
    Cria uma linha de tabela com:
        - Label descritivo
        - 3 inputs de R, G, B
        - Botão de preview (mostra a cor)
        - Botão "Open Colour Palette" (abre color picker)
        - Checkbox "Draw" (opcional)

    Parâmetros:
        label:           texto descritivo (ex: "Baseline")
        r_tag, g_tag, b_tag: tags dos inputs de cor
        draw_tag:        tag do checkbox (None = não cria checkbox)
        preview_tag:     tag do botão de preview
        default_color:   (R, G, B) iniciais
        default_draw:    estado inicial do checkbox
        callback:        função chamada quando uma cor muda

    Retorna:
        Dicionário com as tags criadas.
    """
    r, g, b = default_color

    with dpg.table_row():
        dpg.add_text(label)

        dpg.add_input_int(
            tag=r_tag, width=60,
            default_value=r,
            min_value=0, max_value=255,
            step=0, step_fast=0,
            callback=callback,
            user_data=(r_tag, g_tag, b_tag, preview_tag),
        )
        dpg.add_input_int(
            tag=g_tag, width=60,
            default_value=g,
            min_value=0, max_value=255,
            step=0, step_fast=0,
            callback=callback,
            user_data=(r_tag, g_tag, b_tag, preview_tag),
        )
        dpg.add_input_int(
            tag=b_tag, width=60,
            default_value=b,
            min_value=0, max_value=255,
            step=0, step_fast=0,
            callback=callback,
            user_data=(r_tag, g_tag, b_tag, preview_tag),
        )

        # Botão de preview (cor sólida)
        dpg.add_button(label="", tag=preview_tag, width=40, height=20)

        # Botão de color picker
        dpg.add_button(
            label="Open Colour Palette",
            callback=_open_color_palette_callback,
            user_data=(r_tag, g_tag, b_tag, preview_tag),
        )

        # Checkbox "Draw"
        if draw_tag is not None:
            dpg.add_checkbox(
                label="",
                tag=draw_tag,
                default_value=default_draw,
                callback=callback,
            )
        else:
            dpg.add_text("")  # placeholder

    return {
        "r_tag": r_tag,
        "g_tag": g_tag,
        "b_tag": b_tag,
        "draw_tag": draw_tag,
        "preview_tag": preview_tag,
    }


# ---------------------------------------------------------------------------
# Atualização visual do preview da cor
# ---------------------------------------------------------------------------

def atualizar_preview_cor(
    r_tag: str,
    g_tag: str,
    b_tag: str,
    preview_tag: str,
) -> None:
    """
    Atualiza a cor do botão de preview baseado nos valores R, G, B.

    Cria um tema dinâmico e vincula ao botão.
    """
    try:
        r = int(dpg.get_value(r_tag))
        g = int(dpg.get_value(g_tag))
        b = int(dpg.get_value(b_tag))
    except Exception as e:
        log.warning(f"Falha ao ler cor de {r_tag}/{g_tag}/{b_tag}: {e}")
        return

    theme_tag = f"{preview_tag}_theme_{dpg.generate_uuid()}"

    # Remove tema antigo se existir
    if dpg.does_item_exist(theme_tag):
        dpg.delete_item(theme_tag)

    with dpg.theme(tag=theme_tag):
        with dpg.theme_component(dpg.mvButton):
            color = (r, g, b, 255)
            dpg.add_theme_color(dpg.mvThemeCol_Button, color, category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, color, category=dpg.mvThemeCat_Core)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, color, category=dpg.mvThemeCat_Core)

    if dpg.does_item_exist(preview_tag):
        dpg.bind_item_theme(preview_tag, theme_tag)


# ---------------------------------------------------------------------------
# Color picker popup
# ---------------------------------------------------------------------------

def _open_color_palette_callback(sender, app_data, user_data) -> None:
    """
    Callback do botão "Open Colour Palette".

    Abre um popup modal com um color picker. Ao clicar em OK,
    atualiza os inputs de R, G, B.
    """
    r_tag, g_tag, b_tag, preview_tag = user_data

    popup_tag = f"{preview_tag}_popup"
    picker_tag = f"{preview_tag}_picker"

    # Fecha popup anterior se existir
    if dpg.does_item_exist(popup_tag):
        dpg.delete_item(popup_tag)

    # Valores atuais
    try:
        r = int(dpg.get_value(r_tag)) / 255.0
        g = int(dpg.get_value(g_tag)) / 255.0
        b = int(dpg.get_value(b_tag)) / 255.0
    except Exception:
        r, g, b = 1.0, 0.0, 0.0

    def aplicar_cor() -> None:
        try:
            color = dpg.get_value(picker_tag)
            r_new = round(color[0] * 255)
            g_new = round(color[1] * 255)
            b_new = round(color[2] * 255)
            dpg.set_value(r_tag, r_new)
            dpg.set_value(g_tag, g_new)
            dpg.set_value(b_tag, b_new)
            atualizar_preview_cor(r_tag, g_tag, b_tag, preview_tag)
        except Exception as e:
            log.warning(f"Falha ao aplicar cor: {e}")
        finally:
            if dpg.does_item_exist(popup_tag):
                dpg.delete_item(popup_tag)

    def ao_mudar_cor(sender, app_data, user_data) -> None:
        """Atualiza preview em tempo real enquanto arrasta o picker."""
        try:
            r_temp = round(app_data[0] * 255)
            g_temp = round(app_data[1] * 255)
            b_temp = round(app_data[2] * 255)
            dpg.set_value(r_tag, r_temp)
            dpg.set_value(g_tag, g_temp)
            dpg.set_value(b_tag, b_temp)
            atualizar_preview_cor(r_tag, g_tag, b_tag, preview_tag)
        except Exception:
            pass

    with dpg.window(
        label="Selecione a cor",
        modal=True,
        tag=popup_tag,
        width=350,
        height=400,
        no_move=True,
        no_resize=True,
        on_close=lambda: dpg.delete_item(popup_tag) if dpg.does_item_exist(popup_tag) else None,
    ):
        dpg.add_text("Escolha uma cor:")
        dpg.add_color_picker(
            default_value=[r, g, b, 1.0],
            tag=picker_tag,
            width=260,
            no_alpha=True,
            display_rgb=True,
            display_hsv=False,
            display_hex=False,
            no_side_preview=False,
            no_small_preview=True,
        )
        dpg.add_spacer(height=5)
        dpg.add_button(label="OK", callback=lambda: aplicar_cor())

        dpg.set_item_callback(picker_tag, ao_mudar_cor)


# ---------------------------------------------------------------------------
# Linha de input numérico com clamp
# ---------------------------------------------------------------------------

def input_int_com_clamp(
    label: str,
    tag: str,
    default_value: int,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
    width: int = 100,
    step: int = 1,
    step_fast: int = 10,
    callback: Optional[Callable] = None,
    user_data=None,
) -> None:
    """Cria um input int com min/max."""
    dpg.add_input_int(
        label=label,
        tag=tag,
        width=width,
        default_value=default_value,
        min_value=min_value,
        max_value=max_value,
        step=step,
        step_fast=step_fast,
        callback=callback,
        user_data=user_data,
    )


def input_float_com_clamp(
    label: str,
    tag: str,
    default_value: float,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    width: int = 100,
    step: float = 0.1,
    step_fast: float = 1.0,
    format: str = "%.2f",
    callback: Optional[Callable] = None,
    user_data=None,
) -> None:
    """Cria um input float com min/max."""
    dpg.add_input_float(
        label=label,
        tag=tag,
        width=width,
        default_value=default_value,
        min_value=min_value,
        max_value=max_value,
        step=step,
        step_fast=step_fast,
        format=format,
        callback=callback,
        user_data=user_data,
    )