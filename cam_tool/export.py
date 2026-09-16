"""
Módulo de exportação de dados do cam-tool.

Responsável por:
- Representar cada medição como uma estrutura de dados (Medicao)
- Exportar lista de medições para CSV
- Exportar lista de medições para XLSX (com fórmulas de média)

Uso típico:
    from cam_tool.export import Medicao, exportar_csv, exportar_xlsx
    medicoes = [
        Medicao(tempo=0.0, angulo_esquerdo=96.1, angulo_direito=91.7),
    ]
    exportar_csv(medicoes, Path("resultado.csv"))
    exportar_xlsx(medicoes, Path("resultado.xlsx"))
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from cam_tool.log import get_logger

log = get_logger()

# Cabeçalhos da planilha (mantidos em PT-BR para o usuário final)
CABECALHOS = [
    "Tempo (s)",
    "Ângulo Esquerdo (°)",
    "Ângulo Direito (°)",
    "Média (°)",
]


# ---------------------------------------------------------------------------
# Medicao
# ---------------------------------------------------------------------------

@dataclass
class Medicao:
    """
    Representa uma medição de ângulo de contato em um instante.

    Atributos:
        tempo:            tempo decorrido desde o início da coleta (s)
        angulo_esquerdo:  ângulo do lado esquerdo (°) ou None
        angulo_direito:   ângulo do lado direito (°) ou None
    """
    tempo: float
    angulo_esquerdo: Optional[float]
    angulo_direito: Optional[float]

    @property
    def media(self) -> Optional[float]:
        """Média dos dois ângulos, se ambos existirem."""
        if self.angulo_esquerdo is None or self.angulo_direito is None:
            return None
        return (self.angulo_esquerdo + self.angulo_direito) / 2.0

    def para_linha(self) -> List:
        """Retorna a linha formatada para CSV/XLSX."""
        return [
            round(self.tempo, 2),
            round(self.angulo_esquerdo, 1) if self.angulo_esquerdo is not None else None,
            round(self.angulo_direito, 1) if self.angulo_direito is not None else None,
            round(self.media, 1) if self.media is not None else None,
        ]


# ---------------------------------------------------------------------------
# Exportação CSV
# ---------------------------------------------------------------------------

def _formatar_numero_csv(valor, decimal_virgula: bool) -> str:
    """
    Formata um número para o CSV.

    Se decimal_virgula=True, converte "10.5" em "10,5" (padrão BR).
    Se valor for None, retorna string vazia.
    """
    if valor is None:
        return ""
    if isinstance(valor, float):
        texto = f"{valor:.2f}" if valor != int(valor) else str(int(valor))
        # Remove zeros à direita desnecessários
        texto = texto.rstrip("0").rstrip(".") if "." in texto else texto
    else:
        texto = str(valor)

    if decimal_virgula:
        texto = texto.replace(".", ",")

    return texto


def exportar_csv(
    medicoes: Iterable[Medicao],
    caminho: Path,
    incluir_cabecalho: bool = True,
    separador: str = ";",
    decimal_virgula: bool = True,
) -> bool:
    """
    Exporta uma lista de medições para CSV.

    Parâmetros:
        medicoes:         iterável de Medicao
        caminho:          caminho do arquivo .csv
        incluir_cabecalho: se True, escreve a linha de cabeçalho
        separador:        delimitador de colunas (padrão: ";")
        decimal_virgula:  se True, usa vírgula como separador decimal

    Retorna True se sucesso, False caso contrário.
    """
    caminho = Path(caminho)

    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)

        with open(caminho, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=separador)

            if incluir_cabecalho:
                writer.writerow(CABECALHOS)

            for med in medicoes:
                linha = [
                    _formatar_numero_csv(med.tempo, decimal_virgula),
                    _formatar_numero_csv(med.angulo_esquerdo, decimal_virgula),
                    _formatar_numero_csv(med.angulo_direito, decimal_virgula),
                    _formatar_numero_csv(med.media, decimal_virgula),
                ]
                writer.writerow(linha)

        log.info(f"CSV salvo: {caminho}")
        return True

    except Exception as e:
        log.error(f"Falha ao salvar CSV {caminho}: {e}")
        return False


# ---------------------------------------------------------------------------
# Exportação XLSX
# ---------------------------------------------------------------------------

def exportar_xlsx(
    medicoes: Iterable[Medicao],
    caminho: Path,
    nome_aba: str = "Ângulos de Contato",
) -> bool:
    """
    Exporta uma lista de medições para XLSX.

    A coluna "Média" é preenchida com uma FÓRMULA do Excel
    (=AVERAGE(B2:C2)), não com valor calculado.

    Parâmetros:
        medicoes:   iterável de Medicao
        caminho:    caminho do arquivo .xlsx
        nome_aba:   nome da aba da planilha

    Retorna True se sucesso, False caso contrário.
    """
    caminho = Path(caminho)

    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        caminho.parent.mkdir(parents=True, exist_ok=True)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = nome_aba

        # Cabeçalho
        ws.append(CABECALHOS)

        fonte_cabecalho = Font(bold=True, color="FFFFFF")
        fundo_cabecalho = PatternFill(
            start_color="4472C4", end_color="4472C4", fill_type="solid"
        )
        alinhamento_centro = Alignment(horizontal="center", vertical="center")

        for col in range(1, len(CABECALHOS) + 1):
            celula = ws.cell(row=1, column=col)
            celula.font = fonte_cabecalho
            celula.fill = fundo_cabecalho
            celula.alignment = alinhamento_centro

        # Linhas de dados
        for i, med in enumerate(medicoes, start=2):
            linha = med.para_linha()
            ws.cell(row=i, column=1, value=linha[0])  # Tempo
            ws.cell(row=i, column=2, value=linha[1])  # Esquerdo
            ws.cell(row=i, column=3, value=linha[2])  # Direito
            # Média: fórmula do Excel (não valor calculado)
            ws.cell(row=i, column=4, value=f"=AVERAGE(B{i}:C{i})")

        # Ajusta largura das colunas
        for col in range(1, len(CABECALHOS) + 1):
            ws.column_dimensions[get_column_letter(col)].width = 20

        wb.save(caminho)
        log.info(f"XLSX salvo: {caminho}")
        return True

    except ImportError:
        log.error("openpyxl não instalado. Instale com: pip install openpyxl")
        return False
    except Exception as e:
        log.error(f"Falha ao salvar XLSX {caminho}: {e}")
        return False


# ---------------------------------------------------------------------------
# Nome de arquivo com timestamp
# ---------------------------------------------------------------------------

def gerar_nome_planilha(nome_base: str, extensao: str = "xlsx") -> str:
    """
    Gera um nome de arquivo de planilha com timestamp.

    Exemplo:
        gerar_nome_planilha("gota")
        -> "gota_ContactAngles_[16-09-2026_17-55-00].xlsx"
    """
    timestamp = datetime.now().strftime("[%d-%m-%Y_%H.%M.%S]")
    return f"{nome_base}_ContactAngles_{timestamp}.{extensao}"