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
