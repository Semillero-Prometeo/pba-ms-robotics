# pba-ms-robotics

PROMETEO Backend Architecture Robotics Microservice

## Voz (TTS) y variables de entorno

- **Modelos en el repo:** coloca `*.onnx` y el `*.onnx.json` correspondiente en `src/core/models/voice/`. Si no defines `PIPER_MODEL_PATH`, se usa el primer `.onnx` de esa carpeta.
- **Ruta en Docker:** el código vive en `/usr/src/app`. Ejemplo:  
  `MS_ROBOTICS_PIPER_MODEL_PATH=/usr/src/app/src/core/models/voice/es_ES-davefx-medium.onnx`  
  (no uses `/src/voice/models/...`: esa ruta no existe en la imagen).
- **Piper (recomendado):** modelos en [rhasspy/piper-voices (Hugging Face)](https://huggingface.co/rhasspy/piper-voices). El `Dockerfile.dev` instala el binario `piper`.
- **Fallback espeak-ng:** si Piper no aplica; `ESPEAK_VOICE=es` por defecto.
- **Bluetooth / PulseAudio en Docker:** dentro del contenedor no hay servidor Pulse → `Connection refused`. Para usar el **PulseAudio del host Linux** (donde aparece el sink Bluetooth `bluez`):
  1. En el `.env` del launcher: `MS_ROBOTICS_PULSE_SERVER=unix:/run/user/TU_UID/pulse/native` (sustituye `TU_UID`, p. ej. `id -u`).
  2. En `docker-compose.yml`, descomenta el volumen que monta `/run/user/TU_UID/pulse` (mismo UID que en la ruta).
  3. Opcional: `PULSE_SINK` con el nombre exacto del sink BT si la heurística no basta.
- **Solo probar TTS sin reproducir:** `MS_ROBOTICS_VOICE_SKIP_PLAYBACK=1`.

Los fallos de reproducción devuelven **503** al gateway cuando el error lleva `statusCode` estructurado.

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