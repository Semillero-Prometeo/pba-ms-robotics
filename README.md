# pba-ms-robotics

PROMETEO Backend Architecture Robotics Microservice

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
usbipd bind --busid 2-2

usbipd list // Verificar shared

// Abrir una terminal ubuntu para mantener la wsl activa

usbipd attach --wsl --busid <busid>
usbipd attach --wsl --busid 2-2