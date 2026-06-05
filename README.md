# systemcri

Aplicación local para gestión y auditoría Intersoftic.

## Ejecutar localmente

1. python -m venv .venv
2. .\.venv\Scripts\activate
3. pip install -r requirements.txt
4. copy .env.example .env
5. python -m uvicorn server:app --host 0.0.0.0 --port 8010
