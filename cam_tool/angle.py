"""
Módulo de cálculo de ângulos de contato do cam-tool.

O ângulo de contato é o ângulo entre:
- A tangente à gota no ponto de contato
- A linha de base (superfície)

O algoritmo:
    1. Varre a elipse de 0° a 360° em passos pequenos
    2. Encontra pontos da elipse que estão próximos da baseline
       (dentro de uma tolerância em pixels)
    3. Esses são os pontos de contato (esquerdo e direito)
    4. Calcula a tangente nesses pontos
    5. Calcula o ângulo entre a tangente e a baseline

Uso típico:
    from cam_tool.angle import AngleCalculator
    calc = AngleCalculator()
    resultado = calc.calcular(elipse, baseline, x_centro_elipse)
    # resultado.esquerdo, resultado.direito
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from cam_tool.baseline import LinhaBase
from cam_tool.ellipse import Elipse, normalizar_vetor, ponto_elipse, tangente_elipse
from cam_tool.log import get_logger

log = get_logger()


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class AngulosContato:
    """
    Resultado do cálculo de ângulos.

    Atributos:
        esquerdo:        ângulo do lado esquerdo (graus) ou None
        direito:         ângulo do lado direito (graus) ou None
        ponto_esquerdo:  (x, y) do contato esquerdo ou None
        ponto_direito:   (x, y) do contato direito ou None
        tangente_esq:    vetor tangente esquerdo ou None
        tangente_dir:    vetor tangente direito ou None
    """
    esquerdo: Optional[float]
    direito: Optional[float]
    ponto_esquerdo: Optional[tuple[float, float]]
    ponto_direito: Optional[tuple[float, float]]
    tangente_esq: Optional[tuple[float, float]]
    tangente_dir: Optional[tuple[float, float]]

    @property
    def media(self) -> Optional[float]:
        """Média dos ângulos esquerdo e direito, se ambos existirem."""
        if self.esquerdo is None or self.direito is None:
            return None
        return (self.esquerdo + self.direito) / 2.0


# ---------------------------------------------------------------------------
# AngleCalculator
# ---------------------------------------------------------------------------

class AngleCalculator:
    """
    Calcula os ângulos de contato esquerdo e direito.

    Exemplo:
        calc = AngleCalculator(tolerancia_px=2.0, passo_graus=1.0)
        resultado = calc.calcular(elipse, baseline)
        print(resultado.esquerdo, resultado.direito)
    """

    def __init__(self, tolerancia_px: float = 2.0, passo_graus: float = 1.0):
        """
        Parâmetros:
            tolerancia_px:  distância máxima (px) entre elipse e baseline
                            para considerar um ponto de contato
            passo_graus:    incremento do theta ao varrer a elipse
        """
        self.tolerancia_px = tolerancia_px
        self.passo_graus = passo_graus

    def calcular(
        self,
        elipse: Elipse,
        baseline: LinhaBase,
    ) -> AngulosContato:
        """
        Calcula os ângulos de contato.

        Retorna AngulosContato com valores None se não conseguir calcular.
        """
        vazio = AngulosContato(None, None, None, None, None, None)

        if elipse is None or baseline is None:
            log.warning("Elipse ou baseline ausente; não é possível calcular ângulos")
            return vazio

        # 1. Encontra candidatos a ponto de contato
        candidatos = self._encontrar_pontos_contato(elipse, baseline)

        if len(candidatos) < 2:
            log.warning(f"Menos de 2 pontos de contato encontrados: {len(candidatos)}")
            return vazio

        # 2. Ordena por X e pega o mais à esquerda e o mais à direita
        candidatos.sort(key=lambda c: c[0])
        esquerdo = candidatos[0]
        direito = candidatos[-1]

        # 3. Calcula tangentes e ângulos
        x_centro = elipse.centro[0]

        ang_esq, tan_esq = self._calcular_angulo_lado(esquerdo, elipse, baseline, x_centro)
        ang_dir, tan_dir = self._calcular_angulo_lado(direito, elipse, baseline, x_centro)

        log.info(f"Ângulos calculados: esquerdo={ang_esq:.1f}°, direito={ang_dir:.1f}°")

        return AngulosContato(
            esquerdo=ang_esq,
            direito=ang_dir,
            ponto_esquerdo=(esquerdo[0], esquerdo[1]),
            ponto_direito=(direito[0], direito[1]),
            tangente_esq=tan_esq,
            tangente_dir=tan_dir,
        )

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------

    def _encontrar_pontos_contato(
        self,
        elipse: Elipse,
        baseline: LinhaBase,
    ) -> list[tuple[float, float, float]]:
        """
        Varre a elipse e retorna candidatos (x, y, theta) próximos da baseline.
        """
        candidatos: list[tuple[float, float, float]] = []

        thetas = np.arange(0.0, 360.0, self.passo_graus)
        for theta in thetas:
            x, y = ponto_elipse(elipse.centro, elipse.eixos, elipse.angulo, theta)
            y_base = baseline.avaliar(x)

            if abs(y - y_base) < self.tolerancia_px:
                candidatos.append((float(x), float(y), float(theta)))

        return candidatos

    def _calcular_angulo_lado(
        self,
        ponto: tuple[float, float, float],
        elipse: Elipse,
        baseline: LinhaBase,
        x_centro: float,
    ) -> tuple[float, tuple[float, float]]:
        """
        Calcula o ângulo e a tangente para um ponto de contato.

        Retorna (angulo_graus, vetor_tangente).
        """
        x, y, theta = ponto

        # Tangente à elipse nesse ponto
        tx, ty = tangente_elipse(elipse.centro, elipse.eixos, elipse.angulo, theta)
        tx, ty = normalizar_vetor((tx, ty))

        # Garante que a tangente aponta para fora da gota (sentido do lado)
        direcao = 1 if x > x_centro else -1
        if direcao * tx < 0:
            tx, ty = -tx, -ty

        # Vetor da baseline (normalizado)
        m = baseline.coeficiente_angular
        bx, by = normalizar_vetor((1.0, m))

        # Ângulo entre tangente e baseline
        dot = tx * bx + ty * by
        dot = max(-1.0, min(1.0, dot))  # clamp numérico
        angulo_rad = np.arccos(dot)
        angulo_graus = np.degrees(angulo_rad)

        # Para o lado direito, o ângulo é complementar (180 - θ)
        if x > x_centro:
            angulo_graus = 180.0 - angulo_graus

        return angulo_graus, (tx, ty)


# ---------------------------------------------------------------------------
# Função de conveniência
# ---------------------------------------------------------------------------

def calcular_angulos(
    elipse: Elipse,
    baseline: LinhaBase,
    tolerancia_px: float = 2.0,
    passo_graus: float = 1.0,
) -> AngulosContato:
    """Atalho funcional."""
    return AngleCalculator(
        tolerancia_px=tolerancia_px,
        passo_graus=passo_graus,
    ).calcular(elipse, baseline)