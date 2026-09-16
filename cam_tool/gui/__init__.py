"""
Pacote de interface gráfica do cam-tool.

Contém:
    - app.py:            App (janela principal)
    - settings_tab.py:   SettingsTab (aba de configurações + preview)
    - logging_tab.py:    LoggingTab (aba de log)
    - preview.py:        PreviewWidget (preview sob demanda)
    - widgets.py:        Widgets customizados (color picker row, etc.)
"""

from cam_tool.gui.app import App

__all__ = ["App"]
