"""Transcrição de áudio (voice notes do WhatsApp) via Whisper local —
roda inteiramente no servidor, sem API paga externa. O PyAV já embute o
libav, então decodifica o OGG/Opus do WhatsApp sem precisar de ffmpeg
instalado no sistema.
"""

import io
import logging

import av
import numpy as np
from faster_whisper import WhisperModel

from app.config import settings

logger = logging.getLogger(__name__)

_modelo: WhisperModel | None = None


def _obter_modelo() -> WhisperModel:
    global _modelo
    if _modelo is None:
        logger.info("Carregando modelo Whisper (%s) — pode demorar na primeira vez...", settings.whisper_model_size)
        _modelo = WhisperModel(settings.whisper_model_size, device="cpu", compute_type="int8")
    return _modelo


def _decodificar_audio(conteudo: bytes) -> np.ndarray:
    """Decodifica qualquer formato de áudio (ogg/opus do WhatsApp incluso)
    pra um array mono float32 a 16kHz, o formato que o Whisper espera.
    """
    container = av.open(io.BytesIO(conteudo))
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)

    pedacos: list[np.ndarray] = []
    stream = next((s for s in container.streams if s.type == "audio"), None)
    if stream is None:
        container.close()
        return np.array([], dtype=np.float32)

    for frame in container.decode(stream):
        for frame_reamostrado in resampler.resample(frame):
            pedacos.append(frame_reamostrado.to_ndarray())
    for frame_reamostrado in resampler.resample(None):  # flush
        pedacos.append(frame_reamostrado.to_ndarray())
    container.close()

    if not pedacos:
        return np.array([], dtype=np.float32)

    pcm_int16 = np.concatenate(pedacos, axis=1).flatten()
    return (pcm_int16.astype(np.float32) / 32768.0).copy()


def transcrever(conteudo: bytes) -> str:
    """Recebe os bytes crus do áudio (qualquer formato) e devolve o texto
    transcrito em português. String vazia se não conseguir decodificar ou
    não detectar fala.
    """
    audio = _decodificar_audio(conteudo)
    if audio.size == 0:
        logger.warning("Áudio do WhatsApp veio vazio ou em formato não decodificável")
        return ""

    modelo = _obter_modelo()
    segmentos, _info = modelo.transcribe(audio, language="pt", beam_size=1, vad_filter=True)
    return " ".join(segmento.text.strip() for segmento in segmentos).strip()
