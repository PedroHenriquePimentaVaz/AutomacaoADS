#!/usr/bin/env python3
"""
Script de diagnóstico para encontrar a URL correta da API SULTS
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('SULTS_API_TOKEN', 'O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=')

# Possíveis URLs base para testar
BASE_URLS = [
    "https://api.sults.com.br",
    "https://app.sults.com.br/api",
    "https://sults.com.br/api",
    "https://api.sults.com.br/v1",
    "https://app.sults.com.br",
    "https://sults.com.br",
    "https://api.sults.com.br/api",
]

# Possíveis endpoints para testar
ENDPOINTS = [
    "/chamados",
    "/api/chamados",
    "/v1/chamados",
    "/leads",
    "/api/leads",
    "/v1/leads",
    "/tickets",
    "/api/tickets",
    "/unidades",
    "/api/unidades",
]

# Possíveis formatos de autenticação
AUTH_FORMATS = [
    {'Authorization': f'Bearer {TOKEN}'},
    {'Authorization': f'Token {TOKEN}'},
    {'X-API-Key': TOKEN},
    {'X-Auth-Token': TOKEN},
    {'api-key': TOKEN},
]

def test_endpoint(base_url, endpoint, auth_header):
    """Testa um endpoint específico"""
    url = f"{base_url}{endpoint}"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        **auth_header
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return {
            'status_code': response.status_code,
            'url': url,
            'success': response.status_code < 400,
            'response_preview': response.text[:200] if response.text else ''
        }
    except requests.exceptions.RequestException as e:
        return {
            'status_code': None,
            'url': url,
            'success': False,
            'error': str(e)
        }

def main():
    print("=" * 80)
    print("DIAGNÓSTICO DA API SULTS")
    print("=" * 80)
    print(f"Token: {TOKEN[:30]}...")
    print()
    
    results = []
    
    print("Testando diferentes combinações de URL base, endpoint e autenticação...")
    print("Isso pode levar alguns minutos...")
    print()
    
    for base_url in BASE_URLS:
        for endpoint in ENDPOINTS:
            for auth_format in AUTH_FORMATS:
                result = test_endpoint(base_url, endpoint, auth_format)
                results.append(result)
                
                if result['success']:
                    print(f"✓ SUCESSO encontrado!")
                    print(f"  URL: {result['url']}")
                    print(f"  Status: {result['status_code']}")
                    print(f"  Auth: {list(auth_format.keys())[0]}")
                    print()
                    return result
    
    # Se não encontrou sucesso, mostrar os melhores resultados
    print("=" * 80)
    print("Nenhuma combinação funcionou. Mostrando resultados mais promissores:")
    print("=" * 80)
    print()
    
    # Filtrar apenas erros HTTP (não erros de conexão)
    http_errors = [r for r in results if r['status_code'] is not None]
    
    if http_errors:
        # Agrupar por status code
        by_status = {}
        for r in http_errors:
            status = r['status_code']
            if status not in by_status:
                by_status[status] = []
            by_status[status].append(r)
        
        # Mostrar por ordem de status code
        for status in sorted(by_status.keys()):
            print(f"\nStatus {status} ({len(by_status[status])} tentativas):")
            for r in by_status[status][:3]:  # Mostrar apenas os 3 primeiros
                print(f"  - {r['url']}")
                if r.get('response_preview'):
                    print(f"    Resposta: {r['response_preview'][:100]}")
    
    print()
    print("=" * 80)
    print("RECOMENDAÇÕES:")
    print("=" * 80)
    print("1. Verifique a documentação em: https://developers.sults.com.br/")
    print("2. Procure por exemplos de requisições na documentação")
    print("3. Entre em contato com o suporte da SULTS para obter:")
    print("   - URL base correta da API")
    print("   - Formato de autenticação")
    print("   - Lista de endpoints disponíveis")
    print("=" * 80)

if __name__ == '__main__':
    main()

