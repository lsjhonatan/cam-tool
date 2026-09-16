"""
Módulo de configuração do cam-tool.

Responsável por:
- Definir os parâmetros padrão do programa
- Ler e escrever o arquivo Settings.txt
- Validar valores (mín/máx)
- Notificar mudanças

O arquivo Settings.txt usa o formato chave=valor, uma por linha.
Linhas começando com # são comentários e são ignoradas.

Uso típico:
    from cam_tool.config import ConfigManager
    cfg = ConfigManager(Path("Settings.txt"))
    cfg.carregar()
    valor = cfg.obter("roi_x1")
    cfg.definir("roi_x1", 800)
    cfg.salvar()
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from cam_tool.log import get_logger

log = get_logger()


# ---------------------------------------------------------------------------
# Especificação de cada parâmetro
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Parametro:
    """
    Define um parâmetro de configuração.

    Atributos:
        chave:      nome da chave no arquivo (ex: "roi_x1")
        padrao:     valor padrão
        tipo:       tipo Python esperado (int, float, bool, str)
        minimo:     valor mínimo (apenas para int/float)
        maximo:     valor máximo (apenas para int/float)
        descricao:  texto explicativo (usado em documentação)
    """
    chave: str
    padrao: Any
    tipo: type
    minimo: Optional[Union[int, float]] = None
    maximo: Optional[Union[int, float]] = None
    descricao: str = ""


# ---------------------------------------------------------------------------
# Tabela de parâmetros do programa
# ---------------------------------------------------------------------------
# Esta tabela é a ÚNICA fonte de verdade sobre os parâmetros.

PARAMETROS: Dict[str, Parametro] = {
    # --- Arquivo de vídeo ---
    "video_file_path": Parametro(
        chave="video_file_path",
        padrao="",
        tipo=str,
        descricao="Caminho completo do vídeo selecionado",
    ),
    "video_file_name": Parametro(
        chave="video_file_name",
        padrao="",
        tipo=str,
        descricao="Nome do arquivo de vídeo (sem diretório)",
    ),

    # --- Calibração ---
    "escala_nm_por_px": Parametro(
        chave="escala_nm_por_px",
        padrao=1.0, tipo=float, minimo=0.0001, maximo=1e9,
        descricao="Fator de conversão de pixels para nanômetros",
    ),
    "unidade_saida": Parametro(
        chave="unidade_saida",
        padrao="nm", tipo=str,
        descricao="Unidade exibida nos rótulos (nm, µm, mm)",
    ),

    # --- Fontes dos rótulos ---
    "label_font_size": Parametro(
        chave="label_font_size",
        padrao=20, tipo=int, minimo=1, maximo=200,
        descricao="Tamanho da fonte do rótulo de tempo",
    ),
    "label_font_thickness": Parametro(
        chave="label_font_thickness",
        padrao=0, tipo=int, minimo=0, maximo=10,
        descricao="Espessura do contorno do texto de tempo",
    ),
    "label_offset_x": Parametro(
        chave="label_offset_x",
        padrao=0, tipo=int, minimo=-2000, maximo=2000,
        descricao="Deslocamento horizontal do rótulo de tempo",
    ),
    "label_offset_y": Parametro(
        chave="label_offset_y",
        padrao=0, tipo=int, minimo=-2000, maximo=2000,
        descricao="Deslocamento vertical do rótulo de tempo",
    ),

    # --- Fontes das medidas ---
    "measure_font_size": Parametro(
        chave="measure_font_size",
        padrao=22, tipo=int, minimo=1, maximo=200,
        descricao="Tamanho da fonte dos rótulos de medidas",
    ),
    "measure_font_thickness": Parametro(
        chave="measure_font_thickness",
        padrao=1, tipo=int, minimo=0, maximo=10,
        descricao="Espessura do contorno dos rótulos de medidas",
    ),
    "measure_offset_x": Parametro(
        chave="measure_offset_x",
        padrao=0, tipo=int, minimo=-2000, maximo=2000,
        descricao="Deslocamento X do painel de medidas",
    ),
    "measure_offset_y": Parametro(
        chave="measure_offset_y",
        padrao=0, tipo=int, minimo=-2000, maximo=2000,
        descricao="Deslocamento Y do painel de medidas",
    ),

    # --- Cores (RGB) dos elementos do overlay ---
    "label_background_r": Parametro("label_background_r", 255, int, 0, 255, "R do fundo do rótulo"),
    "label_background_g": Parametro("label_background_g", 255, int, 0, 255, "G do fundo do rótulo"),
    "label_background_b": Parametro("label_background_b", 255, int, 0, 255, "B do fundo do rótulo"),
    "draw_label_background": Parametro("draw_label_background", True, bool, None, None, "Desenhar fundo do rótulo"),

    "label_text_r": Parametro("label_text_r", 0, int, 0, 255, "R do texto do rótulo"),
    "label_text_g": Parametro("label_text_g", 0, int, 0, 255, "G do texto do rótulo"),
    "label_text_b": Parametro("label_text_b", 0, int, 0, 255, "B do texto do rótulo"),
    "draw_label_text": Parametro("draw_label_text", True, bool, None, None, "Desenhar texto do rótulo"),

    "region_r": Parametro("region_r", 255, int, 0, 255, "R do retângulo da ROI"),
    "region_g": Parametro("region_g", 125, int, 0, 255, "G do retângulo da ROI"),
    "region_b": Parametro("region_b", 0, int, 0, 255, "B do retângulo da ROI"),
    "draw_region": Parametro("draw_region", True, bool, None, None, "Desenhar retângulo da ROI"),

    "contour_r": Parametro("contour_r", 255, int, 0, 255, "R do contorno completo"),
    "contour_g": Parametro("contour_g", 255, int, 0, 255, "G do contorno completo"),
    "contour_b": Parametro("contour_b", 0, int, 0, 255, "B do contorno completo"),
    "draw_contour": Parametro("draw_contour", True, bool, None, None, "Desenhar contorno completo"),

    "baseline_r": Parametro("baseline_r", 255, int, 0, 255, "R da linha de base"),
    "baseline_g": Parametro("baseline_g", 0, int, 0, 255, "G da linha de base"),
    "baseline_b": Parametro("baseline_b", 0, int, 0, 255, "B da linha de base"),
    "draw_baseline": Parametro("draw_baseline", True, bool, None, None, "Desenhar linha de base"),

    "measure_r": Parametro("measure_r", 0, int, 0, 255, "R dos rótulos de medidas"),
    "measure_g": Parametro("measure_g", 0, int, 0, 255, "G dos rótulos de medidas"),
    "measure_b": Parametro("measure_b", 0, int, 0, 255, "B dos rótulos de medidas"),
    "draw_measure": Parametro("draw_measure", True, bool, None, None, "Desenhar medidas"),

    "dimension_line_r": Parametro("dimension_line_r", 0, int, 0, 255, "R das linhas de dimensão"),
    "dimension_line_g": Parametro("dimension_line_g", 0, int, 0, 255, "G das linhas de dimensão"),
    "dimension_line_b": Parametro("dimension_line_b", 0, int, 0, 255, "B das linhas de dimensão"),
    "draw_dimension_line": Parametro("draw_dimension_line", True, bool, None, None, "Desenhar linhas de dimensão"),

    # --- Coleta de imagens ---
    "num_images": Parametro(
        chave="num_images",
        padrao=10, tipo=int, minimo=1, maximo=10000,
        descricao="Número de imagens a extrair do vídeo",
    ),
    "time_increment": Parametro(
        chave="time_increment",
        padrao=1.0, tipo=float, minimo=0.001, maximo=3600.0,
        descricao="Intervalo de tempo entre imagens (segundos)",
    ),
    "start_time": Parametro(
        chave="start_time",
        padrao=8.0, tipo=float, minimo=0.0, maximo=100000.0,
        descricao="Tempo inicial de coleta (segundos)",
    ),
    "roi_x1": Parametro(
        chave="roi_x1",
        padrao=750, tipo=int, minimo=0, maximo=100000,
        descricao="Coordenada X inicial da região de interesse",
    ),
    "roi_x2": Parametro(
        chave="roi_x2",
        padrao=1700, tipo=int, minimo=1, maximo=100000,
        descricao="Coordenada X final da região de interesse",
    ),

    # --- Thresholds de análise ---
    "baseline_threshold": Parametro(
        chave="baseline_threshold",
        padrao=15, tipo=float, minimo=0.0, maximo=100.0,
        descricao="Porcentagem do contorno usada para ajustar a baseline",
    ),
    "tolerancia_contato_px": Parametro(
        chave="tolerancia_contato_px",
        padrao=3.0, tipo=float, minimo=0.1, maximo=50.0,
        descricao="Distância máxima (px) para considerar contato com a baseline",
    ),

    # --- Zoom ---
    "zoom_x": Parametro(
        chave="zoom_x",
        padrao=352, tipo=int, minimo=0, maximo=100000,
        descricao="Posição X da caixa de zoom",
    ),
    "zoom_y": Parametro(
        chave="zoom_y",
        padrao=120, tipo=int, minimo=0, maximo=100000,
        descricao="Posição Y da caixa de zoom",
    ),
    "zoom_size": Parametro(
        chave="zoom_size",
        padrao=220, tipo=int, minimo=1, maximo=100000,
        descricao="Tamanho (lado) da caixa de zoom",
    ),

    # --- Compilação do slideshow ---
    "img_duration": Parametro(
        chave="img_duration",
        padrao=0.5, tipo=float, minimo=0.1, maximo=5.0,
        descricao="Duração de cada imagem no GIF/MP4 (segundos)",
    ),
    "output_format": Parametro(
        chave="output_format",
        padrao="GIF", tipo=str,
        descricao="Formato de saída do slideshow (GIF ou MP4)",
    ),
    "txt_suffix": Parametro(
        chave="txt_suffix",
        padrao="s", tipo=str,
        descricao="Sufixo de unidade de tempo exibido no rótulo (ex: 's')",
    ),
}


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------

class ConfigManager:
    """
    Gerencia a leitura, escrita e acesso aos parâmetros de configuração.

    Uso:
        cfg = ConfigManager(Path("Settings.txt"))
        cfg.carregar()
        x = cfg.obter("roi_x1")
        cfg.definir("roi_x1", 800)
        cfg.salvar()
    """

    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
        self._valores: Dict[str, Any] = {
            chave: param.padrao for chave, param in PARAMETROS.items()
        }
        self._callbacks: List[Callable[[str, Any], None]] = []

    # ------------------------------------------------------------------
    # Acesso
    # ------------------------------------------------------------------

    def obter(self, chave: str) -> Any:
        """Retorna o valor atual de um parâmetro."""
        if chave not in self._valores:
            raise KeyError(f"Parâmetro desconhecido: {chave}")
        return self._valores[chave]

    def definir(self, chave: str, valor: Any) -> None:
        """
        Define o valor de um parâmetro, com validação.

        Se o valor for inválido, mantém o anterior e registra um aviso.
        """
        if chave not in PARAMETROS:
            log.warning(f"Tentativa de definir parâmetro desconhecido: {chave}")
            return

        param = PARAMETROS[chave]

        # Validação de tipo
        if not self._validar_tipo(valor, param):
            log.warning(
                f"Valor inválido para '{chave}': {valor!r} "
                f"(esperado {param.tipo.__name__})"
            )
            return

        # Validação de faixa
        valor = self._aplicar_limites(valor, param)

        # Só notifica se realmente mudou
        if self._valores[chave] != valor:
            self._valores[chave] = valor
            self._notificar(chave, valor)

    def todos(self) -> Dict[str, Any]:
        """Retorna um dicionário com todos os valores atuais."""
        return dict(self._valores)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def registrar_callback(self, callback: Callable[[str, Any], None]) -> None:
        """
        Registra uma função para ser chamada quando um valor mudar.

        A função recebe (chave, novo_valor).
        """
        self._callbacks.append(callback)

    def _notificar(self, chave: str, valor: Any) -> None:
        for cb in self._callbacks:
            try:
                cb(chave, valor)
            except Exception as e:
                log.warning(f"Callback de config falhou: {e}")

    # ------------------------------------------------------------------
    # Validação
    # ------------------------------------------------------------------

    @staticmethod
    def _validar_tipo(valor: Any, param: Parametro) -> bool:
        """Verifica se o valor é do tipo esperado (com tolerância para int/float)."""
        if param.tipo is bool:
            return isinstance(valor, bool)
        if param.tipo is int:
            return isinstance(valor, int) and not isinstance(valor, bool)
        if param.tipo is float:
            return isinstance(valor, (int, float)) and not isinstance(valor, bool)
        if param.tipo is str:
            return isinstance(valor, str)
        return isinstance(valor, param.tipo)

    @staticmethod
    def _aplicar_limites(valor: Any, param: Parametro) -> Any:
        """Aplica mínimo e máximo, se definidos."""
        if param.minimo is not None:
            valor = max(param.minimo, valor)
        if param.maximo is not None:
            valor = min(param.maximo, valor)
        return valor

    # ------------------------------------------------------------------
    # Arquivo
    # ------------------------------------------------------------------

    def carregar(self) -> None:
        """Lê o arquivo Settings.txt e atualiza os valores."""
        if not self.caminho.is_file():
            log.info(f"Arquivo de configuração não encontrado: {self.caminho}")
            log.info("Usando valores padrão.")
            return

        try:
            with open(self.caminho, "r", encoding="utf-8") as f:
                for numero, linha in enumerate(f, start=1):
                    linha = linha.strip()
                    if not linha or linha.startswith("#"):
                        continue
                    if "=" not in linha:
                        log.warning(f"Linha {numero} inválida (sem '='): {linha!r}")
                        continue

                    chave, valor_str = linha.split("=", 1)
                    chave = chave.strip()
                    valor_str = valor_str.strip()

                    if chave not in PARAMETROS:
                        continue

                    valor = self._converter(valor_str, PARAMETROS[chave])
                    if valor is not None:
                        self.definir(chave, valor)

            log.info(f"Configurações carregadas de {self.caminho}")

        except Exception as e:
            log.error(f"Falha ao carregar configurações: {e}")

    def salvar(self) -> None:
        """Escreve o arquivo Settings.txt com os valores atuais."""
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            with open(self.caminho, "w", encoding="utf-8") as f:
                f.write("# Configurações do cam-tool\n")
                f.write("# Formato: chave=valor\n")
                f.write("# Linhas começando com # são ignoradas\n\n")

                grupos = {
                    "Vídeo": ["video_file_path", "video_file_name"],
                    "Calibração": ["escala_nm_por_px", "unidade_saida"],
                    "Fontes": [k for k in PARAMETROS if "font" in k or "offset" in k],
                    "Cores": [k for k in PARAMETROS if any(p in k for p in ("_r", "_g", "_b", "draw_"))],
                    "Coleta": ["num_images", "time_increment", "start_time", "roi_x1", "roi_x2"],
                    "Análise": ["baseline_threshold", "tolerancia_contato_px"],
                    "Zoom": ["zoom_x", "zoom_y", "zoom_size"],
                    "Compilação": ["img_duration", "output_format", "txt_suffix"],
                }

                vistos = set()
                for nome_grupo, chaves in grupos.items():
                    f.write(f"# --- {nome_grupo} ---\n")
                    for chave in chaves:
                        if chave in vistos or chave not in self._valores:
                            continue
                        vistos.add(chave)
                        f.write(f"{chave}={self._formatar(self._valores[chave])}\n")
                    f.write("\n")

                restantes = [k for k in self._valores if k not in vistos]
                if restantes:
                    f.write("# --- Outros ---\n")
                    for chave in restantes:
                        f.write(f"{chave}={self._formatar(self._valores[chave])}\n")

            log.info(f"Configurações salvas em {self.caminho}")

        except Exception as e:
            log.error(f"Falha ao salvar configurações: {e}")

    def resetar(self) -> None:
        """
        Restaura todos os parâmetros para os valores padrão.

        Notifica todos os callbacks, mesmo os que já estavam no padrão.
        """
        for chave, param in PARAMETROS.items():
            self._valores[chave] = param.padrao
            self._notificar(chave, param.padrao)

        log.info("Configurações restauradas para os padrões.")

    # ------------------------------------------------------------------
    # Conversão
    # ------------------------------------------------------------------

    @staticmethod
    def _converter(valor_str: str, param: Parametro) -> Any:
        """Converte string do arquivo para o tipo do parâmetro."""
        try:
            if param.tipo is bool:
                return valor_str.lower() in ("true", "1", "yes", "sim")
            if param.tipo is int:
                return int(float(valor_str))
            if param.tipo is float:
                return float(valor_str)
            return valor_str
        except (ValueError, TypeError) as e:
            log.warning(f"Falha ao converter '{valor_str}' para {param.tipo.__name__}: {e}")
            return None

    @staticmethod
    def _formatar(valor: Any) -> str:
        """Converte valor para string do arquivo."""
        if isinstance(valor, bool):
            return "1" if valor else "0"
        if isinstance(valor, float):
            if valor.is_integer():
                return str(int(valor))
            return str(valor)
        return str(valor)