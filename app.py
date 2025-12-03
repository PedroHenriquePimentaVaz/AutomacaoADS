# Entrypoint para Vercel
# Importa o app Flask do app_web.py
from app_web import app

# Exporta o app para o Vercel
__all__ = ['app']

