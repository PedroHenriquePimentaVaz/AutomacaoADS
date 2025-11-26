#!/usr/bin/env python3
"""
Script auxiliar para preparar credenciais do Google para o Vercel.
Lê o arquivo JSON e gera o valor que deve ser colado na variável de ambiente GOOGLE_CREDENTIALS_JSON.
"""

import json
import sys
import os

def main():
    # Tenta encontrar o arquivo de credenciais
    credentials_file = 'sixth-now-475017-k8-785034518ab7.json'
    
    if not os.path.exists(credentials_file):
        print(f"❌ Arquivo não encontrado: {credentials_file}")
        print("💡 Certifique-se de estar na raiz do projeto")
        sys.exit(1)
    
    try:
        # Lê o arquivo JSON
        with open(credentials_file, 'r', encoding='utf-8') as f:
            credentials_data = json.load(f)
        
        # Converte de volta para string JSON (sem espaços extras)
        credentials_json = json.dumps(credentials_data, separators=(',', ':'))
        
        print("=" * 80)
        print("✅ Credenciais preparadas com sucesso!")
        print("=" * 80)
        print("\n📋 Copie o conteúdo abaixo e cole na variável de ambiente GOOGLE_CREDENTIALS_JSON no Vercel:\n")
        print(credentials_json)
        print("\n" + "=" * 80)
        print("💡 Instruções:")
        print("   1. Acesse o painel do Vercel")
        print("   2. Vá em Settings → Environment Variables")
        print("   3. Adicione uma nova variável:")
        print("      - Nome: GOOGLE_CREDENTIALS_JSON")
        print("      - Valor: Cole o JSON acima (tudo em uma linha)")
        print("   4. Selecione os ambientes (Production, Preview, Development)")
        print("   5. Clique em Save")
        print("=" * 80)
        
    except json.JSONDecodeError as e:
        print(f"❌ Erro ao fazer parse do JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erro: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

