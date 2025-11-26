# Entrypoint para Vercel
# Importa o app Flask do app_web.py
import sys
import traceback
import os

# Configura logging para debug
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    logger.info("Tentando importar app_web...")
    from app_web import app
    logger.info("app_web importado com sucesso!")
except ImportError as e:
    logger.error(f"Erro de importação: {e}")
    logger.error(traceback.format_exc())
    # Se houver erro na importação, cria um app mínimo para debug
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def error_handler():
        error_msg = f"Erro ao importar app_web: {str(e)}\n\n{traceback.format_exc()}"
        logger.error(error_msg)
        return f"<h1>Erro de Importação</h1><pre>{error_msg}</pre>", 500
    
    @app.route('/<path:path>')
    def catch_all(path):
        return f"<h1>Erro</h1><p>App não inicializado corretamente. Verifique os logs.</p>", 500
except Exception as e:
    logger.error(f"Erro geral: {e}")
    logger.error(traceback.format_exc())
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def error_handler():
        error_msg = f"Erro ao inicializar app: {str(e)}\n\n{traceback.format_exc()}"
        logger.error(error_msg)
        return f"<h1>Erro de Inicialização</h1><pre>{error_msg}</pre>", 500

# Exporta o app para o Vercel
__all__ = ['app']

