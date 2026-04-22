"""
OmniVoice TTS — Modal GPU endpoint
Deploy: modal deploy modal_app.py
"""
import modal
import base64
import io
import subprocess
import tempfile

app = modal.App("omnivoice-tts")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "omnivoice",
        "torch",
        "soundfile",
        "numpy",
    )
)


@app.cls(image=image, gpu="T4", timeout=120, container_idle_timeout=300)
class VoiceCloner:
    """
    GPU контейнер с OmniVoice.
    - build() — скачивает модель в образ (один раз)
    - enter() — грузит в GPU при старте контейнера
    - generate() — HTTP POST endpoint
    """

    @modal.build()
    def download_model(self):
        from omnivoice import OmniVoice
        # Скачивает веса в HF cache, запекается в образ
        OmniVoice.from_pretrained("k2-fsa/OmniVoice")

    @modal.enter()
    def load_model(self):
        import torch
        from omnivoice import OmniVoice

        self.model = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice",
            device_map="cuda:0",
            dtype=torch.float16,
        )

    @modal.web_endpoint(method="POST")
    def generate(self, data: dict):
        """
        Input:  {"audio_base64": "...", "text": "Текст для озвучки"}
        Output: {"audio_base64": "...", "duration_sec": 3.2}
        """
        import soundfile as sf

        audio_bytes = base64.b64decode(data["audio_base64"])
        text = data["text"]

        # Сохраняем входящее аудио (OGG от Telegram)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(audio_bytes)
            input_path = f.name

        # Конвертируем в WAV 24kHz mono (OmniVoice формат)
        ref_path = input_path.replace(".ogg", ".wav")
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-ar", "24000", "-ac", "1", ref_path],
            capture_output=True,
        )

        # Генерация клонированного голоса
        audio = self.model.generate(
            text=text,
            ref_audio=ref_path,
        )

        # Кодируем результат в WAV base64
        buf = io.BytesIO()
        sf.write(buf, audio[0], 24000, format="WAV")
        buf.seek(0)
        wav_bytes = buf.read()

        return {
            "audio_base64": base64.b64encode(wav_bytes).decode(),
            "duration_sec": round(len(audio[0]) / 24000, 2),
        }
