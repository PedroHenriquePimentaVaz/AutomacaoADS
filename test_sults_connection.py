#!/usr/bin/env python3
"""
Script para testar a conexão com a API da SULTS e exibir leads por status
"""
import os
import sys
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

try:
    from sults_api import SultsAPIClient
except ImportError:
    print("Erro: Módulo sults_api não encontrado. Certifique-se de que o arquivo existe.")
    sys.exit(1)

def main():
    print("=" * 60)
    print("TESTE DE CONEXÃO COM API SULTS")
    print("=" * 60)
    print()
    
    # Criar cliente
    token = os.getenv('SULTS_API_TOKEN', 'O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=')
    client = SultsAPIClient(token=token)
    
    print(f"Token configurado: {token[:20]}...")
    print(f"URL Base: {client.BASE_URL}")
    print()
    
    # Testar conexão
    print("1. Testando conexão básica...")
    try:
        # Tentar buscar unidades como teste
        unidades = client.get_unidades()
        print(f"   ✓ Conexão estabelecida com sucesso!")
        print(f"   ✓ Unidades encontradas: {len(unidades) if isinstance(unidades, list) else 'N/A'}")
    except Exception as e:
        print(f"   ✗ Erro na conexão: {str(e)}")
        print(f"   Verifique a URL base e o formato de autenticação na documentação.")
        return
    print()
    
    # Buscar leads por status
    print("2. Buscando leads organizados por status...")
    try:
        leads_data = client.get_leads_by_status()
        
        print(f"   Total geral de leads: {leads_data.get('total_geral', 0)}")
        print()
        print(f"   📊 RESUMO POR STATUS:")
        print(f"   - Abertos: {leads_data.get('abertos', {}).get('total', 0)}")
        print(f"   - Perdidos: {leads_data.get('perdidos', {}).get('total', 0)}")
        print(f"   - Ganhos: {leads_data.get('ganhos', {}).get('total', 0)}")
        print(f"   - Outros: {leads_data.get('outros', {}).get('total', 0)}")
        print()
        
        # Mostrar alguns exemplos de leads abertos
        leads_abertos = leads_data.get('abertos', {}).get('leads', [])
        if leads_abertos:
            print(f"   📋 EXEMPLOS DE LEADS ABERTOS (primeiros 5):")
            for i, lead in enumerate(leads_abertos[:5], 1):
                nome = lead.get('nome', 'N/A')
                status = lead.get('status', 'N/A')
                email = lead.get('email', 'N/A')
                print(f"   {i}. {nome} - Status: {status} - Email: {email}")
        print()
        
        # Mostrar alguns exemplos de leads perdidos
        leads_perdidos = leads_data.get('perdidos', {}).get('leads', [])
        if leads_perdidos:
            print(f"   📋 EXEMPLOS DE LEADS PERDIDOS (primeiros 5):")
            for i, lead in enumerate(leads_perdidos[:5], 1):
                nome = lead.get('nome', 'N/A')
                status = lead.get('status', 'N/A')
                email = lead.get('email', 'N/A')
                print(f"   {i}. {nome} - Status: {status} - Email: {email}")
        print()
        
    except Exception as e:
        print(f"   ✗ Erro ao buscar leads: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    print("=" * 60)
    print("TESTE CONCLUÍDO")
    print("=" * 60)

if __name__ == '__main__':
    main()

