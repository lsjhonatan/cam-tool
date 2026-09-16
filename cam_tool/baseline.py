"""
Módulo de ajuste da linha de base (baseline) do cam-tool.

A baseline é a reta que representa a superfície onde a gota está apoiada.
É ajustada com RANSAC (Random Sample Consensus), que é robusto a outliers
(reflexos, imperfeições da superfície, ruído).

Uso típico:
    from cam_tool.baseline import BaselineFitter
    fitter = BaselineFitter()
    linha = fitter.ajustar(pontos_do_contorno, percentual_baixos=15.0)
    # linha.coeficiente_angular, linha.intercepto
    y = linha.avaliar(x)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from sklearn.linear_model import RANSACRegressor

from cam_tool.log import get_logger

log = get_logger()


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class LinhaBase:
    """
    Representa a linha de base: y = m*x + b.

    Atributos:
        coeficiente_angular: m (inclinação)
        intercepto:          b (onde cruza o eixo Y)
    """
    coeficiente_angular: float
    intercepto: float

    def avaliar(self, x: float | np.ndarray) -> float | np.ndarray:
        """Retorna o valor de y para um dado x (ou array de x)."""
        return self.coeficiente_angular * x + self.intercepto

    def avaliar_vetor(self, xs: np.ndarray) -> np.ndarray:
        """Versão otimizada para arrays NumPy."""
        return self.coeficiente_angular * xs + self.intercepto


# ---------------------------------------------------------------------------
# BaselineFitter
# ---------------------------------------------------------------------------

class BaselineFitter:
    """
    Ajusta a linha de base a partir dos pontos do contorno.

    O algoritmo:
        1. Ordena os pontos por Y (maior primeiro, pois Y cresce pra baixo)
        2. Seleciona os N% mais baixos (onde a gota toca a superfície)
        3. Ajusta uma reta com RANSAC
    """

    def __init__(self, seed: int = 42):
        """
        Parâmetros:
            seed: semente do RANSAC (para reprodutibilidade)
        """
        self.seed = seed

    def ajustar(
        self,
        pontos: np.ndarray,
        percentual_baixos: float = 15.0,
    ) -> Optional[LinhaBase]:
        """
        Ajusta a baseline aos pontos do contorno.

        Parâmetros:
            pontos:             array (N, 2) com coordenadas (x, y)
            percentual_baixos:  % dos pontos mais baixos usados no ajuste

        Retorna:
            LinhaBase ou None se não for possível ajustar.
        """
        if pontos is None or len(pontos) < 5:
            log.warning(f"Pontos insuficientes para ajustar baseline: {len(pontos) if pontos is not None else 0}")
            return None

        percentual_baixos = max(0.0, min(100.0, percentual_baixos))

        # Ordena por Y decrescente (maiores Y = mais baixos na imagem)
        indices_ordenados = np.argsort(-pontos[:, 1])
        pontos_ordenados = pontos[indices_ordenados]

        # Seleciona N% mais baixos
        n_baixos = max(5, int(len(pontos_ordenados) * percentual_baixos / 100.0))
        pontos_baixos = pontos_ordenados[:n_baixos]

        if len(pontos_baixos) < 5:
            log.warning(f"Poucos pontos baixos: {len(pontos_baixos)}")
            return None

        # Ajusta RANSAC
        try:
            X = pontos_baixos[:, 0].reshape(-1, 1)
            y = pontos_baixos[:, 1]

            modelo = RANSACRegressor(random_state=self.seed)
            modelo.fit(X, y)

            m = float(modelo.estimator_.coef_[0])
            b = float(modelo.estimator_.intercept_)

            log.debug(f"Baseline ajustada: y = {m:.4f}*x + {b:.2f} ({n_baixos} pontos)")
            return LinhaBase(coeficiente_angular=m, intercepto=b)

        except Exception as e:
            log.error(f"Falha ao ajustar baseline: {e}")
            return None


# ---------------------------------------------------------------------------
# Função de conveniência
# ---------------------------------------------------------------------------

def ajustar_baseline(
    pontos: np.ndarray,
    percentual_baixos: float = 15.0,
    seed: int = 42,
) -> Optional[LinhaBase]:
    """Atalho funcional para ajustar baseline sem instanciar BaselineFitter."""
    return BaselineFitter(seed=seed).ajustar(pontos, percentual_baixos)