# Entrypoint para Vercel
# Importa o app Flask do app_web.py
import sys
import traceback

try:
    from app_web import app
except Exception as e:
    # Se houver erro na importação, cria um app mínimo para debug
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def error_handler():
        error_msg = f"Erro ao importar app_web: {str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        return f"<h1>Erro de Importação</h1><pre>{error_msg}</pre>", 500
    
    @app.route('/<path:path>')
    def catch_all(path):
        return f"<h1>Erro</h1><p>App não inicializado corretamente. Verifique os logs.</p>", 500

# Exporta o app para o Vercel
__all__ = ['app']

