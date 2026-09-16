"""
Módulo de medições da gota do cam-tool.

Calcula as dimensões físicas da gota a partir do contorno e da baseline:
    - Largura (diâmetro da base)
    - Altura (do topo até a base)
    - Raio R (esfera que contém a calota)
    - Volume da calota
    - Área de contato
    - Ângulo de contato (fórmula da calota esférica)

Modelo físico assumido: a gota é uma CALOTA ESFÉRICA (sessile drop).
Isso é uma aproximação padrão em ciência de superfície para gotas
pequenas, onde a gravidade é desprezível (número de Bond < 1).

Fórmulas (todas baseadas em calota esférica):
    a = largura / 2
    h = altura
    R = (a² + h²) / (2h)
    V = π h² (3R - h) / 3
    A = π a²
    θ = 2 * atan(h / a)

Uso típico:
    from cam_tool.measurements import MedidorGota
    medidor = MedidorGota()
    medidas = medidor.medir(contorno, baseline, escala_nm_por_px=500.0)
    medidas.largura_nm
    medidas.altura_nm
    medidas.raio_nm
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from cam_tool.baseline import LinhaBase
from cam_tool.contour import ResultadoContorno
from cam_tool.log import get_logger

log = get_logger()


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class MedidasGota:
    """
    Resultado completo das medições de uma gota.

    Todas as medidas em pixels (px) e em nanômetros (nm).
    A conversão usa o fator `escala_nm_por_px` fornecido pelo usuário.

    Atributos em pixels:
        largura_px, altura_px, raio_px
        volume_px3, area_contato_px2

    Atributos em nanômetros:
        largura_nm, altura_nm, raio_nm

    Atributos adimensionais:
        angulo_graus

    Pontos notáveis (em pixels, no sistema de coordenadas da imagem):
        ponto_topo:          topo da gota
        ponto_esq:           contato esquerdo (contorno ∩ baseline)
        ponto_dir:           contato direito
        ponto_centro_base:   centro da base (média dos contatos)
    """
    # --- Dimensões em pixels ---
    largura_px: float
    altura_px: float
    raio_px: float
    volume_px3: float
    area_contato_px2: float

    # --- Dimensões em nanômetros ---
    largura_nm: float
    altura_nm: float
    raio_nm: float

    # --- Adimensional ---
    angulo_graus: float

    # --- Pontos notáveis ---
    ponto_topo: tuple[float, float]
    ponto_esq: tuple[float, float]
    ponto_dir: tuple[float, float]
    ponto_centro_base: tuple[float, float]

    # --- Calibração usada (registro) ---
    escala_nm_por_px: float


# ---------------------------------------------------------------------------
# MedidorGota
# ---------------------------------------------------------------------------

class MedidorGota:
    """
    Mede as dimensões de uma gota a partir do contorno e da baseline.

    Exemplo:
        medidor = MedidorGota(tolerancia_contato_px=2.0)
        medidas = medidor.medir(contorno, baseline, escala_nm_por_px=500.0)
    """

    def __init__(self, tolerancia_contato_px: float = 2.0):
        """
        Parâmetros:
            tolerancia_contato_px: distância máxima (px) entre o contorno
                                   e a baseline para considerar um ponto
                                   de contato
        """
        self.tolerancia_contato_px = tolerancia_contato_px

    def medir(
        self,
        contorno: ResultadoContorno,
        baseline: LinhaBase,
        escala_nm_por_px: float = 1.0,
    ) -> Optional[MedidasGota]:
        """
        Mede as dimensões da gota.

        Parâmetros:
            contorno:          ResultadoContorno com `.pontos` (N, 2)
            baseline:          LinhaBase ajustada
            escala_nm_por_px:  fator de conversão px → nm

        Retorna:
            MedidasGota ou None se não for possível medir.
        """
        if contorno is None or contorno.pontos is None or len(contorno.pontos) < 5:
            log.warning("Contorno inválido ou vazio; não é possível medir")
            return None

        if baseline is None:
            log.warning("Baseline ausente; não é possível medir")
            return None

        if escala_nm_por_px <= 0:
            log.warning(f"Escala inválida: {escala_nm_por_px}. Usando 1.0")
            escala_nm_por_px = 1.0

        pontos = contorno.pontos

        # ------------------------------------------------------------------
        # 1. Pontos de contato (contorno ∩ baseline)
        # ------------------------------------------------------------------
        contatos = self._encontrar_contatos(pontos, baseline)

        if len(contatos) < 2:
            log.warning(
                f"Menos de 2 pontos de contato encontrados: {len(contatos)}"
            )
            return None

        contatos_ordenados = sorted(contatos, key=lambda p: p[0])
        ponto_esq = contatos_ordenados[0]
        ponto_dir = contatos_ordenados[-1]

        # ------------------------------------------------------------------
        # 2. Largura
        # ------------------------------------------------------------------
        largura_px = ponto_dir[0] - ponto_esq[0]

        if largura_px <= 0:
            log.warning(f"Largura inválida: {largura_px}")
            return None

        # ------------------------------------------------------------------
        # 3. Topo da gota (Y mínimo entre os pontos dentro da faixa de X)
        # ------------------------------------------------------------------
        mascara_x = (pontos[:, 0] >= ponto_esq[0]) & (pontos[:, 0] <= ponto_dir[0])
        pontos_dentro = pontos[mascara_x]

        if len(pontos_dentro) < 3:
            log.warning("Poucos pontos dentro da faixa de X")
            return None

        idx_topo = np.argmin(pontos_dentro[:, 1])
        ponto_topo = tuple(pontos_dentro[idx_topo].astype(float))

        # ------------------------------------------------------------------
        # 4. Altura (do topo até a baseline)
        # ------------------------------------------------------------------
        x_topo, y_topo = ponto_topo
        y_base_no_topo = float(baseline.avaliar(x_topo))
        altura_px = y_base_no_topo - y_topo

        if altura_px <= 0:
            log.warning(f"Altura inválida: {altura_px}")
            return None

        # ------------------------------------------------------------------
        # 5. Raio da calota esférica: R = (a² + h²) / (2h)
        # ------------------------------------------------------------------
        a = largura_px / 2.0
        h = altura_px
        raio_px = (a * a + h * h) / (2.0 * h)

        # ------------------------------------------------------------------
        # 6. Volume da calota: V = π h² (3R - h) / 3
        # ------------------------------------------------------------------
        volume_px3 = (np.pi * h * h * (3.0 * raio_px - h)) / 3.0

        # ------------------------------------------------------------------
        # 7. Área de contato: A = π a²
        # ------------------------------------------------------------------
        area_contato_px2 = np.pi * a * a

        # ------------------------------------------------------------------
        # 8. Ângulo de contato (calota esférica): θ = 2 * atan(h / a)
        # ------------------------------------------------------------------
        angulo_rad = 2.0 * np.arctan2(h, a)
        angulo_graus = float(np.degrees(angulo_rad))

        # ------------------------------------------------------------------
        # 9. Conversão para nanômetros
        # ------------------------------------------------------------------
        largura_nm = largura_px * escala_nm_por_px
        altura_nm = altura_px * escala_nm_por_px
        raio_nm = raio_px * escala_nm_por_px

        # ------------------------------------------------------------------
        # 10. Centro da base
        # ------------------------------------------------------------------
        centro_base = (
            (ponto_esq[0] + ponto_dir[0]) / 2.0,
            (ponto_esq[1] + ponto_dir[1]) / 2.0,
        )

        medidas = MedidasGota(
            largura_px=float(largura_px),
            altura_px=float(altura_px),
            raio_px=float(raio_px),
            volume_px3=float(volume_px3),
            area_contato_px2=float(area_contato_px2),
            largura_nm=float(largura_nm),
            altura_nm=float(altura_nm),
            raio_nm=float(raio_nm),
            angulo_graus=float(angulo_graus),
            ponto_topo=ponto_topo,
            ponto_esq=ponto_esq,
            ponto_dir=ponto_dir,
            ponto_centro_base=centro_base,
            escala_nm_por_px=float(escala_nm_por_px),
        )

        log.info(
            f"Medidas: largura={largura_px:.1f}px ({largura_nm:.0f}nm), "
            f"altura={altura_px:.1f}px ({altura_nm:.0f}nm), "
            f"R={raio_px:.1f}px ({raio_nm:.0f}nm), "
            f"ângulo={angulo_graus:.1f}°"
        )

        return medidas

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------

    def _encontrar_contatos(
        self,
        pontos: np.ndarray,
        baseline: LinhaBase,
    ) -> list[tuple[float, float]]:
        """
        Encontra pontos do contorno próximos da baseline.

        Retorna lista de (x, y) que estão a menos de `tolerancia_contato_px`
        da baseline.

        Para cada X, pega o ponto do contorno com Y mais próximo da baseline.
        Isso evita pegar pontos do topo da gota que por acaso estejam
        dentro da tolerância (o que aconteceria se a gota fosse muito baixa).
        """
        if len(pontos) == 0:
            return []

        # Agrupa pontos por X e, para cada X, escolhe o Y mais próximo da baseline
        contatos_por_x: dict[int, tuple[float, float, float]] = {}

        for x, y in pontos:
            x_int = int(round(x))
            y_base = float(baseline.avaliar(x))
            dist = abs(y - y_base)

            if dist >= self.tolerancia_contato_px:
                continue

            # Se já temos um ponto nesse X, mantém o mais próximo da baseline
            if x_int in contatos_por_x:
                _, _, dist_antiga = contatos_por_x[x_int]
                if dist < dist_antiga:
                    contatos_por_x[x_int] = (float(x), float(y), dist)
            else:
                contatos_por_x[x_int] = (float(x), float(y), dist)

        # Retorna apenas (x, y), ordenado por x
        contatos = [(x, y) for x, y, _ in contatos_por_x.values()]
        contatos.sort(key=lambda p: p[0])

        return contatos


# ---------------------------------------------------------------------------
# Função de conveniência
# ---------------------------------------------------------------------------

def medir_gota(
    contorno: ResultadoContorno,
    baseline: LinhaBase,
    escala_nm_por_px: float = 1.0,
    tolerancia_contato_px: float = 2.0,
) -> Optional[MedidasGota]:
    """Atalho funcional."""
    return MedidorGota(tolerancia_contato_px).medir(
        contorno, baseline, escala_nm_por_px
    )


# ---------------------------------------------------------------------------
# Verificação da fórmula da calota esférica
# ---------------------------------------------------------------------------

def verificar_formula_calota() -> bool:
    """
    Teste de sanidade: cria uma calota esférica sintética, calcula R
    pela fórmula e compara com o R real.

    Serve como auto-teste do módulo.

    Retorna True se a fórmula está correta.
    """
    # Círculo de raio R=100, centrado em (0, 0)
    # Calota de altura h=30: a base fica em y = R - h = 70
    R_real = 100.0
    h_real = 30.0
    a_real = np.sqrt(R_real**2 - (R_real - h_real) ** 2)

    # Fórmula: R = (a² + h²) / (2h)
    R_calc = (a_real**2 + h_real**2) / (2 * h_real)

    return abs(R_calc - R_real) < 1e-6
