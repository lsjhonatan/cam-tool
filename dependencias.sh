#!/usr/bin/env bash
#
# dependencias.sh — Instala todas as dependências do cam-tool
#
# Uso:
#   ./dependencias.sh            # instala/verifica tudo
#   ./dependencias.sh --reset    # apaga venv e reinstala do zero
#   ./dependencias.sh --help     # mostra esta ajuda
#

set -e

# ---------- Configuração ----------
PROJETO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJETO_DIR/.venv"
REQUIREMENTS="$PROJETO_DIR/requirements.txt"
BASHRC="$HOME/.bashrc"
RESET=0

# ---------- Parse de argumentos ----------
for arg in "$@"; do
    case "$arg" in
        --reset)
            RESET=1
            ;;
        -h|--help)
            echo "Uso: $0 [--reset]"
            echo "  --reset   Apaga o venv e reinstala tudo do zero"
            exit 0
            ;;
        *)
            echo "Argumento desconhecido: $arg"
            echo "Use --help para ver as opções."
            exit 1
            ;;
    esac
done

# ---------- Cores ----------
VERDE="\033[0;32m"
AMARELO="\033[1;33m"
VERMELHO="\033[0;31m"
RESET_COR="\033[0m"

info()  { echo -e "${VERDE}[OK]${RESET_COR} $1"; }
aviso() { echo -e "${AMARELO}[AVISO]${RESET_COR} $1"; }
erro()  { echo -e "${VERMELHO}[ERRO]${RESET_COR} $1"; }

echo
echo "=============================================="
echo "  cam-tool — Instalação de dependências"
echo "=============================================="
echo "  Projeto: $PROJETO_DIR"
echo "  Venv:    $VENV_DIR"
[ "$RESET" -eq 1 ] && echo "  Modo:    RESET (apagar venv e reinstalar)"
echo

# ---------- 1. Dependências do sistema ----------
info "Atualizando lista de pacotes (apt)..."
sudo apt update -qq

info "Instalando dependências do sistema..."
sudo apt install -y \
    python3-venv \
    python3-full \
    python3-tk \
    libmediainfo0v5

# ---------- 2. Reset (se pedido) ----------
if [ "$RESET" -eq 1 ] && [ -d "$VENV_DIR" ]; then
    aviso "Modo --reset ativado. Apagando venv antigo..."
    rm -rf "$VENV_DIR"
    info "Venv antigo removido."
fi

# ---------- 3. Criar venv ----------
if [ -d "$VENV_DIR" ]; then
    aviso "Venv já existe em $VENV_DIR — pulando criação."
else
    info "Criando venv..."
    python3 -m venv "$VENV_DIR"
fi

# ---------- 4. Instalar libs Python ----------
info "Ativando venv e instalando bibliotecas Python..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

pip install --upgrade pip
if [ -f "$REQUIREMENTS" ]; then
    pip install -r "$REQUIREMENTS"
else
    erro "requirements.txt não encontrado em $REQUIREMENTS"
    exit 1
fi

info "Bibliotecas instaladas:"
pip list --format=columns | grep -Ei "dearpygui|opencv|numpy|pillow|pymediainfo|pandas|openpyxl" || true

deactivate

# ---------- 5. Aliases no ~/.bashrc ----------
if grep -q "alias cam-tool=" "$BASHRC" 2>/dev/null; then
    aviso "Aliases já existem no $BASHRC — pulando."
else
    info "Adicionando aliases ao $BASHRC..."
    cat >> "$BASHRC" << 'EOF'

# ---------- cam-tool ----------
alias cam-tool='cd ~/cam-tool && source .venv/bin/activate && python3 -m cam_tool'
alias cam-out='xdg-open ~/cam-tool/Output 2>/dev/null || true'
EOF
    info "Aliases adicionados. Rode: source ~/.bashrc"
fi

# ---------- Final ----------
echo
echo "=============================================="
info "Instalação concluída"
echo "=============================================="
echo
echo "Para usar agora, execute:"
echo "    source ~/.bashrc"
echo
echo "Depois:"
echo "    cam-tool    # abre o programa"
echo "    cam-out     # abre a pasta de saída"
echo