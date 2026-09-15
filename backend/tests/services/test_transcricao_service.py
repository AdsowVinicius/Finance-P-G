"""Só testa o decode/resample (rápido, sem rede) — não carrega o modelo
Whisper aqui (é pesado pra baixar/carregar; a transcrição de verdade foi
validada manualmente). Ver transcricao_service.py.
"""

import io

import av
import numpy as np

from app.services.transcricao_service import _decodificar_audio


def _gerar_ogg_tom(frequencia: float = 440.0, duracao_s: float = 1.0, taxa: int = 48000) -> bytes:
    buffer = io.BytesIO()
    container = av.open(buffer, mode="w", format="ogg")
    stream = container.add_stream("libopus", rate=taxa, layout="mono")

    t = np.linspace(0, duracao_s, int(taxa * duracao_s), endpoint=False)
    onda = (np.sin(2 * np.pi * frequencia * t) * 0.3 * 32767).astype(np.int16).reshape(1, -1)
    frame = av.AudioFrame.from_ndarray(onda, format="s16", layout="mono")
    frame.sample_rate = taxa

    for pacote in stream.encode(frame):
        container.mux(pacote)
    for pacote in stream.encode(None):
        container.mux(pacote)
    container.close()
    return buffer.getvalue()


class TestDecodificarAudio:
    def test_decodifica_ogg_opus_para_pcm_float32_16khz_mono(self) -> None:
        conteudo = _gerar_ogg_tom(duracao_s=2.0)
        audio = _decodificar_audio(conteudo)

        assert audio.dtype == np.float32
        # 2s a 16kHz esperado (formato que o Whisper exige) — tolerância
        # pequena por causa de padding/latência de encode/decode do opus.
        assert abs(audio.shape[0] - 32000) < 2000
        assert audio.min() >= -1.0 and audio.max() <= 1.0

    def test_audio_vazio_nao_quebra(self) -> None:
        conteudo = _gerar_ogg_tom(duracao_s=0.05)
        audio = _decodificar_audio(conteudo)
        assert audio.dtype == np.float32
        assert audio.size >= 0

    def test_bytes_invalidos_levantam_erro_claro(self) -> None:
        import av as av_module

        try:
            _decodificar_audio(b"isso nao e audio nenhum")
        except av_module.error.FFmpegError:
            pass  # esperado — bytes não são um container de áudio válido
        else:
            raise AssertionError("esperava av.error.FFmpegError pra bytes inválidos")
