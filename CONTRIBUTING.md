# Contribuir a Doctor Descheduler

## Antes de empezar

1. Leé [README.md](README.md) y la sección de limitaciones: con `DRY_RUN=false` el proceso **evicta pods de verdad**.
2. No commitees kubeconfig, tokens, `.env` ni capturas que muestren secretos.
3. No subas `.venv/` ni `__pycache__/`.

## Cómo reportar bugs

1. Buscá si ya hay un [issue](https://github.com/ghcetraro/doctor-descheduler/issues) parecido.
2. Abrí uno nuevo con versión o commit, configuración **sin secretos**, y el log de la pasada.

Para vulnerabilidades, seguí [SECURITY.md](SECURITY.md).

## Pull requests

1. Fork y branch desde `master`:
   ```bash
   git checkout -b feature/mi-cambio
   ```
2. Cambios chicos y mensaje de commit claro, en español o inglés.
3. Verificá:
   ```bash
   cd software/backend
   pip install -r requirements.txt pytest
   python -m pytest tests
   cd ../frontend
   pip install -r requirements.txt
   python -m py_compile app/*.py
   ```
4. Actualizá el README si cambia el comportamiento o las variables.

## Estilo

- Python 3.12+.
- No agregues hosts, IPs ni tokens de un laboratorio en ejemplos: usá `cluster-a` y `change-me`.
