# pba-ms-robotics

PROMETEO Backend Architecture Robotics Microservice

## Voz (TTS) y variables de entorno

- **Piper (recomendado):** modelos en [rhasspy/piper-voices (Hugging Face)](https://huggingface.co/rhasspy/piper-voices). Busca un paquete `es_ES` (por ejemplo `es_ES-lessac-medium`), descarga el `.onnx` y el `.onnx.json`, y apunta `PIPER_MODEL_PATH` al fichero `.onnx`. Necesitas el binario [piper](https://github.com/rhasspy/piper/releases) en el `PATH`.
- **Fallback espeak-ng:** sin Piper, se usa `espeak-ng`; `ESPEAK_VOICE=es` es español (ajusta según `espeak-ng --voices`).
- **`PULSE_SINK`:** nombre del sink de salida (`pactl list short sinks`); vacío = selección automática (Bluetooth antes que USB).
- **Docker sin altavoz:** `paplay`/`aplay` suelen fallar (no hay `/dev/snd` o PulseAudio). Usa `VOICE_SKIP_PLAYBACK=1` para generar audio en fichero sin reproducir, o monta audio (véase comentarios en `docker-compose.yml` para `devices: /dev/snd`) en un host Linux con sonido.

Los errores de reproducción devuelven **503** al gateway cuando el mensaje incluye código estructurado (antes aparecía 400 por defecto).

# Elimina el venv existente

rm -rf .venv

# Crea uno nuevo

python3 -m venv .venv

# Actívalo

source .venv/bin/activate

# Instala las dependencias

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"




usbipd list

usbipd bind --busid <Bus de las camaras>
usbipd bind --busid 3-1

usbipd list // Verificar shared

// Abrir una terminal ubuntu para mantener la wsl activa

usbipd attach --wsl --busid <busid>
usbipd attach --wsl --busid 3-1