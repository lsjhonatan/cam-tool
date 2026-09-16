"""
Ponto de entrada do cam-tool.

Uso:
    python3 -m cam_tool

Ou, se o venv estiver ativo:
    cam-tool   (alias criado pelo dependencias.sh)
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    """Ponto de entrada."""
    try:
        from cam_tool.gui.app import App
    except ImportError as e:
        print(f"Erro ao importar o App: {e}", file=sys.stderr)
        print("Certifique-se de que todas as dependências estão instaladas.", file=sys.stderr)
        return 1

    try:
        app = App()
        app.run()
        return 0
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Erro fatal: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())