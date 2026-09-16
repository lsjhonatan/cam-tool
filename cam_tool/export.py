"""
Módulo de exportação de dados do cam-tool.

Responsável por:
- Representar cada medição como uma estrutura de dados (Medicao)
- Exportar lista de medições para CSV
- Exportar lista de medições para XLSX (com fórmulas de média)

Uso típico:
    from cam_tool.export import Medicao, exportar_csv, exportar_xlsx
    medicoes = [
        Medicao(tempo=0.0, largura_nm=69500, altura_nm=14067, raio_nm=49955),
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


# ---------------------------------------------------------------------------
# Cabeçalhos da planilha
# ---------------------------------------------------------------------------

CABECALHOS = [
    "Tempo (s)",
    "Largura (nm)",
    "Altura (nm)",
    "Raio R (nm)",
    "Volume (nm³)",
    "Área de Contato (nm²)",
    "Ângulo (°)",
]


# ---------------------------------------------------------------------------
# Medicao
# ---------------------------------------------------------------------------

@dataclass
class Medicao:
    """
    Representa uma medição de uma gota em um instante.

    Todas as medidas em nanômetros (nm) ou nm² / nm³ para área/volume.

    Atributos:
        tempo:             tempo decorrido desde o início da coleta (s)
        largura_nm:        diâmetro da base da gota (nm)
        altura_nm:         altura da gota (nm)
        raio_nm:           raio da esfera que contém a calota (nm)
        volume_nm3:        volume da calota (nm³)
        area_contato_nm2:  área da base (nm²)
        angulo_graus:      ângulo de contato (°)
        escala_nm_por_px:  calibração usada (nm/px) — registro
    """
    tempo: float
    largura_nm: Optional[float] = None
    altura_nm: Optional[float] = None
    raio_nm: Optional[float] = None
    volume_nm3: Optional[float] = None
    area_contato_nm2: Optional[float] = None
    angulo_graus: Optional[float] = None
    escala_nm_por_px: float = 1.0

    def para_linha(self) -> List:
        """
        Retorna a linha formatada para CSV/XLSX.

        Valores arredondados:
            - Tempo: 2 casas
            - Medidas em nm: 1 casa
            - Volume: 0 casas (é grande)
            - Área: 0 casas
            - Ângulo: 1 casa
        """
        return [
            round(self.tempo, 2),
            round(self.largura_nm, 1) if self.largura_nm is not None else None,
            round(self.altura_nm, 1) if self.altura_nm is not None else None,
            round(self.raio_nm, 1) if self.raio_nm is not None else None,
            round(self.volume_nm3, 0) if self.volume_nm3 is not None else None,
            round(self.area_contato_nm2, 0) if self.area_contato_nm2 is not None else None,
            round(self.angulo_graus, 1) if self.angulo_graus is not None else None,
        ]

    @classmethod
    def de_resultado(cls, resultado, tempo: float) -> "Medicao":
        """
        Cria uma Medicao a partir de um ResultadoAnalise do pipeline.

        Parâmetros:
            resultado:  ResultadoAnalise (com .medidas preenchido)
            tempo:      tempo decorrido (s)

        Se resultado.medidas for None, retorna uma Medicao vazia.
        """
        if resultado is None or resultado.medidas is None:
            return cls(tempo=tempo)

        m = resultado.medidas
        escala = m.escala_nm_por_px

        return cls(
            tempo=tempo,
            largura_nm=m.largura_nm,
            altura_nm=m.altura_nm,
            raio_nm=m.raio_nm,
            # Volume em px³ → nm³ = px³ × escala³
            volume_nm3=m.volume_px3 * (escala ** 3),
            # Área em px² → nm² = px² × escala²
            area_contato_nm2=m.area_contato_px2 * (escala ** 2),
            angulo_graus=m.angulo_graus,
            escala_nm_por_px=escala,
        )


# ---------------------------------------------------------------------------
# Formatação de números para CSV
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
        # Volume e área: sem decimais
        if abs(valor) >= 1000:
            texto = f"{valor:.0f}"
        else:
            texto = f"{valor:.2f}"
            texto = texto.rstrip("0").rstrip(".")
    else:
        texto = str(valor)

    if decimal_virgula:
        texto = texto.replace(".", ",")

    return texto


# ---------------------------------------------------------------------------
# Exportação CSV
# ---------------------------------------------------------------------------

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
        medicoes:          iterável de Medicao
        caminho:           caminho do arquivo .csv
        incluir_cabecalho: se True, escreve a linha de cabeçalho
        separador:         delimitador de colunas (padrão: ";")
        decimal_virgula:   se True, usa vírgula como separador decimal

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
                    _formatar_numero_csv(v, decimal_virgula)
                    for v in med.para_linha()
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
    nome_aba: str = "Medidas da Gota",
) -> bool:
    """
    Exporta uma lista de medições para XLSX.

    A coluna "Ângulo" é preenchida com uma FÓRMULA do Excel
    (=DEGREES(2*ATAN(C2/(B2/2)))), calculada a partir da largura (B)
    e altura (C). Isso permite que o usuário edite largura/altura
    na planilha e veja o ângulo recalcular.

    Parâmetros:
        medicoes:  iterável de Medicao
        caminho:   caminho do arquivo .xlsx
        nome_aba:  nome da aba da planilha

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
            ws.cell(row=i, column=2, value=linha[1])  # Largura
            ws.cell(row=i, column=3, value=linha[2])  # Altura
            ws.cell(row=i, column=4, value=linha[3])  # Raio R
            ws.cell(row=i, column=5, value=linha[4])  # Volume
            ws.cell(row=i, column=6, value=linha[5])  # Área
            # Ângulo: fórmula do Excel
            # θ = 2 * atan(altura / (largura/2)) em graus
            ws.cell(row=i, column=7, value=f"=DEGREES(2*ATAN(C{i}/(B{i}/2)))")

        # Ajusta largura das colunas
        larguras = [12, 16, 16, 16, 18, 18, 14]
        for col, larg in enumerate(larguras, start=1):
            ws.column_dimensions[get_column_letter(col)].width = larg

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
        -> "gota_Medidas_[16-09-2026_18-25-00].xlsx"
    """
    timestamp = datetime.now().strftime("[%d-%m-%Y_%H.%M.%S]")
    return f"{nome_base}_Medidas_{timestamp}.{extensao}"