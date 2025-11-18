#!/usr/bin/env python3
"""
Script para testar manualmente a API SULTS
Execute este script e me envie o resultado completo
"""

import requests
import os

# Tentar carregar dotenv se disponível
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TOKEN = os.getenv('SULTS_API_TOKEN', 'O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=')

# URLs para testar (baseado na URL que você está usando: behonestbrasil.sults.com.br)
BASE_URLS = [
    'https://behonestbrasil.sults.com.br/api/v1',
    'https://behonestbrasil.sults.com.br/api',
    'https://behonestbrasil.sults.com.br/v1',
    'https://app.sults.com.br/api/v1',
    'https://developer.sults.com.br/api/v1',
]

ENDPOINTS = ['/leads', '/chamados', '/api/leads', '/api/chamados']

# Formatos de autenticação
AUTH_FORMATS = [
    {'name': 'Bearer', 'header': {'Authorization': f'Bearer {TOKEN}'}},
    {'name': 'Token', 'header': {'Authorization': f'Token {TOKEN}'}},
    {'name': 'API Key', 'header': {'X-API-Key': TOKEN}},
    {'name': 'Auth Token', 'header': {'X-Auth-Token': TOKEN}},
    {'name': 'Token na URL', 'url_param': f'?token={TOKEN}'},
]

print("=" * 80)
print("🔍 TESTE MANUAL DA API SULTS")
print("=" * 80)
print(f"\nToken: {TOKEN[:30]}...")
print(f"\nTestando {len(BASE_URLS)} URLs base e {len(ENDPOINTS)} endpoints...\n")

results = []

for base_url in BASE_URLS:
    for endpoint in ENDPOINTS:
        for auth_format in AUTH_FORMATS:
            url = f"{base_url}{endpoint}"
            if 'url_param' in auth_format:
                url += auth_format['url_param']
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            headers.update(auth_format.get('header', {}))
            
            try:
                # Primeiro teste sem seguir redirecionamentos
                response = requests.get(url, headers=headers, timeout=10, allow_redirects=False)
                content_type = response.headers.get('Content-Type', '')
                is_json = 'application/json' in content_type
                is_html = 'text/html' in content_type or 'text/xml' in content_type
                
                # Se for redirecionamento, tentar seguir
                redirect_url = None
                if response.status_code in [301, 302, 303, 307, 308]:
                    redirect_url = response.headers.get('Location', '')
                    # Tentar seguir o redirecionamento
                    try:
                        response_follow = requests.get(redirect_url, headers=headers, timeout=10, allow_redirects=True)
                        if 'application/json' in response_follow.headers.get('Content-Type', ''):
                            response = response_follow
                            is_json = True
                    except:
                        pass
                
                status = "✅ SUCESSO" if is_json and response.status_code == 200 else "❌ FALHOU"
                
                result = {
                    'status': status,
                    'url': url,
                    'auth_format': auth_format['name'],
                    'status_code': response.status_code,
                    'content_type': content_type,
                    'is_json': is_json,
                    'is_html': is_html,
                    'redirect_url': redirect_url,
                    'response_preview': response.text[:200] if response.text else ''
                }
                
                results.append(result)
                
                redirect_info = f" → {redirect_url[:40]}..." if redirect_url else ""
                print(f"{status} | {auth_format['name']:15} | {response.status_code:3} | {content_type[:30]:30} | {url}{redirect_info}")
                
                if is_json and response.status_code == 200:
                    print(f"   🎉 FUNCIONOU! URL: {url}")
                    print(f"   📋 Formato de Auth: {auth_format['name']}")
                    print(f"   📦 Resposta (primeiros 500 chars):")
                    print(f"   {response.text[:500]}")
                    print()
                    
            except Exception as e:
                print(f"❌ ERRO | {auth_format['name']:15} | {url}")
                print(f"   Erro: {str(e)[:100]}")
                results.append({
                    'status': '❌ ERRO',
                    'url': url,
                    'auth_format': auth_format['name'],
                    'error': str(e)
                })

print("\n" + "=" * 80)
print("📊 RESUMO")
print("=" * 80)

successful = [r for r in results if r.get('status') == '✅ SUCESSO']
if successful:
    print(f"\n✅ {len(successful)} combinação(ões) funcionaram!")
    for r in successful:
        print(f"\n   URL: {r['url']}")
        print(f"   Auth: {r['auth_format']}")
        print(f"   Status: {r['status_code']}")
else:
    print("\n❌ Nenhuma combinação funcionou automaticamente.")
    print("\n📋 PRÓXIMOS PASSOS:")
    print("   1. Abra o DevTools (F12) no navegador")
    print("   2. Vá para a aba Network")
    print("   3. Navegue pelo dashboard SULTS")
    print("   4. Clique em uma requisição de API")
    print("   5. Copie a URL completa e os headers")
    print("   6. Me envie essas informações")

print("\n" + "=" * 80)

