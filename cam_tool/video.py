"""
Módulo de leitura de vídeo do cam-tool.

Responsável por:
- Abrir vídeos (.mp4, .avi, .mov, etc.)
- Extrair frames em timestamps específicos
- Detectar rotação nos metadados (importante para vídeos de celular)
- Informar duração, FPS, total de frames

Uso típico:
    from cam_tool.video import VideoReader
    with VideoReader(Path("gota.mp4")) as video:
        print(video.duracao, video.fps)
        frame = video.ler_frame_em(2.5)
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Iterator, Optional

import cv2
import numpy as np

from cam_tool.log import get_logger

log = get_logger()


# ---------------------------------------------------------------------------
# Leitura de metadados (rotação)
# ---------------------------------------------------------------------------

def _detectar_rotacao(caminho: Path) -> int:
    """
    Tenta detectar a rotação do vídeo a partir dos metadados.

    Vídeos gravados em celular costumam ter rotação 90, 180 ou 270
    nos metadados, mas o OpenCV não aplica isso automaticamente.

    Retorna 0, 90, 180 ou 270. Retorna 0 se não conseguir detectar.
    """
    try:
        from pymediainfo import MediaInfo

        media = MediaInfo.parse(str(caminho))
        for track in media.tracks:
            if track.track_type == "Video" and track.rotation:
                return int(round(float(track.rotation)))

    except ImportError:
        log.warning("pymediainfo não instalado; rotação não será detectada")
    except Exception as e:
        log.warning(f"Falha ao detectar rotação: {e}")

    return 0


def _aplicar_rotacao(frame: np.ndarray, rotacao: int) -> np.ndarray:
    """Aplica rotação ao frame, conforme o valor dos metadados."""
    if rotacao == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if rotacao == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if rotacao == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return frame


# ---------------------------------------------------------------------------
# VideoReader
# ---------------------------------------------------------------------------

class VideoReader(AbstractContextManager):
    """
    Leitor de vídeo com suporte a:
    - Context manager (with VideoReader(...) as v: ...)
    - Extração por timestamp
    - Iteração por intervalo
    - Rotação automática

    Exemplo:
        with VideoReader(Path("gota.mp4")) as video:
            print(f"Duração: {video.duracao:.2f}s")
            print(f"FPS: {video.fps:.2f}")
            frame = video.ler_frame_em(2.5)
    """

    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)

        if not self.caminho.is_file():
            raise FileNotFoundError(f"Vídeo não encontrado: {self.caminho}")

        self._cap = cv2.VideoCapture(str(self.caminho))
        if not self._cap.isOpened():
            raise IOError(f"OpenCV não conseguiu abrir: {self.caminho}")

        # Metadados
        self.fps: float = self._cap.get(cv2.CAP_PROP_FPS) or 0.0
        self.total_frames: int = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.largura: int = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.altura: int = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.duracao: float = self.total_frames / self.fps if self.fps > 0 else 0.0

        # Rotação detectada nos metadados
        self.rotacao: int = _detectar_rotacao(self.caminho)

        log.info(
            f"Vídeo aberto: {self.caminho.name} "
            f"({self.largura}x{self.altura}, {self.fps:.2f} fps, "
            f"{self.duracao:.2f}s, rotação={self.rotacao}°)"
        )

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "VideoReader":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.fechar()

    # ------------------------------------------------------------------
    # Acesso a frames
    # ------------------------------------------------------------------

    def ler_frame_em(self, tempo_segundos: float) -> Optional[np.ndarray]:
        """
        Lê o frame correspondente ao timestamp informado.

        Aplica correção de rotação automaticamente.
        Retorna None se o timestamp for inválido ou a leitura falhar.
        """
        if self.fps <= 0:
            log.error("FPS inválido, não é possível calcular o frame")
            return None

        if tempo_segundos < 0 or tempo_segundos > self.duracao:
            log.error(
                f"Timestamp fora dos limites: {tempo_segundos:.2f}s "
                f"(duração: {self.duracao:.2f}s)"
            )
            return None

        numero_frame = int(tempo_segundos * self.fps)
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, numero_frame)

        ret, frame = self._cap.read()
        if not ret or frame is None or frame.size == 0:
            log.error(f"Falha ao ler frame em {tempo_segundos:.2f}s")
            return None

        return _aplicar_rotacao(frame, self.rotacao)

    def ler_primeiro_frame(self) -> Optional[np.ndarray]:
        """Lê o primeiro frame do vídeo (útil para preview)."""
        return self.ler_frame_em(0.0)

    def iterar_frames(
        self,
        tempo_inicial: float,
        quantidade: int,
        intervalo: float,
    ) -> Iterator[tuple[float, np.ndarray]]:
        """
        Itera sobre `quantidade` frames, começando em `tempo_inicial`,
        com `intervalo` segundos entre cada um.

        Gera tuplas (tempo_relativo, frame), onde tempo_relativo é
        o tempo decorrido desde o início da coleta (não o timestamp
        absoluto do vídeo).

        Exemplo:
            for t, frame in video.iterar_frames(8.0, 10, 1.0):
                print(f"Frame em t={t:.1f}s")
        """
        for i in range(quantidade):
            tempo_absoluto = tempo_inicial + i * intervalo

            if tempo_absoluto > self.duracao:
                log.warning(
                    f"Iteração interrompida: t={tempo_absoluto:.2f}s "
                    f"excede duração ({self.duracao:.2f}s)"
                )
                break

            frame = self.ler_frame_em(tempo_absoluto)
            if frame is None:
                log.warning(f"Frame em t={tempo_absoluto:.2f}s não pôde ser lido")
                continue

            tempo_relativo = tempo_absoluto - tempo_inicial
            yield (tempo_relativo, frame)

    # ------------------------------------------------------------------
    # Limpeza
    # ------------------------------------------------------------------

    def fechar(self) -> None:
        """Libera o recurso do vídeo."""
        if self._cap is not None and self._cap.isOpened():
            self._cap.release()
            self._cap = None
            log.debug(f"Vídeo fechado: {self.caminho.name}")

    def __del__(self):
        try:
            self.fechar()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Utilitário: formatar tempo como MM:SS
# ---------------------------------------------------------------------------

def formatar_tempo(segundos: float) -> str:
    """
    Converte segundos para string no formato MM:SS.

    Exemplos:
        65.3  → "01:05"
        8.0   → "00:08"
        3661  → "61:01"  (não usa horas, apenas minutos)
    """
    if segundos < 0:
        segundos = 0
    minutos = int(segundos) // 60
    segs = int(segundos) % 60
    return f"{minutos:02d}:{segs:02d}"