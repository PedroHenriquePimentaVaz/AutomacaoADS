# 🔐 Problema de Autenticação na API SULTS

## Situação Atual

A API SULTS está retornando **HTML ao invés de JSON**, o que indica problema de autenticação.

### Sintomas:
- Status HTTP: 200 (OK)
- Content-Type: `text/html;charset=UTF-8` (deveria ser `application/json`)
- Resposta: Página HTML (provavelmente página de login ou erro)

## Possíveis Causas

### 1. Token Inválido ou Expirado
O token `O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=` pode estar:
- Expirado
- Revogado
- Sem permissões adequadas

### 2. Formato de Autenticação Incorreto
A API pode usar um formato diferente de Bearer Token:
- `Token {token}` ao invés de `Bearer {token}`
- `X-API-Key: {token}`
- `X-Auth-Token: {token}`
- Basic Auth
- Outro formato customizado

### 3. Token Precisa Ser Decodificado
O token parece ser base64. Pode precisar ser:
- Decodificado antes de usar
- Usado de forma diferente

### 4. Cookies/Sessão Necessários
A API pode precisar de:
- Cookies de sessão
- Autenticação em duas etapas
- Login prévio via web

## Soluções Implementadas

O código agora:
1. ✅ Tenta automaticamente diferentes formatos de autenticação
2. ✅ Detecta quando retorna HTML e tenta alternativas
3. ✅ Fornece mensagens de erro mais claras

## Como Resolver

### Opção 1: Verificar Token na Documentação

1. Acesse: https://developers.sults.com.br/
2. Procure por seção de "Autenticação" ou "Authentication"
3. Verifique:
   - Como gerar um novo token
   - Formato correto do token
   - Como usar o token nas requisições

### Opção 2: Gerar Novo Token

1. Acesse a plataforma SULTS
2. Vá para configurações de API/Integrações
3. Gere um novo token de API
4. Atualize no `.env`:
   ```env
   SULTS_API_TOKEN=novo_token_aqui
   ```

### Opção 3: Verificar Formato de Autenticação

O código tenta automaticamente, mas você pode forçar um formato específico:

```python
# No código, você pode especificar o formato:
client = SultsAPIClient(auth_format='token')  # ou 'apikey', 'header'
```

### Opção 4: Contatar Suporte SULTS

Se nada funcionar, entre em contato com o suporte e pergunte:

```
Olá, equipe SULTS!

Estou tentando usar a API REST e recebo HTML ao invés de JSON.

Meu token: O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=
URL: https://developer.sults.com.br/api/v1/leads
Status: 200
Content-Type: text/html (deveria ser application/json)

Perguntas:
1. O token está correto e válido?
2. Qual o formato correto de autenticação?
3. Há algum passo adicional necessário?
4. O token precisa ser gerado de forma diferente?

Agradeço desde já!
```

## Teste Manual

Teste diretamente com curl para ver a resposta completa:

```bash
TOKEN="O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM="

# Testar Bearer Token
curl -H "Authorization: Bearer $TOKEN" \
     -H "User-Agent: Mozilla/5.0" \
     "https://developer.sults.com.br/api/v1/leads"

# Testar Token sem Bearer
curl -H "Authorization: Token $TOKEN" \
     -H "User-Agent: Mozilla/5.0" \
     "https://developer.sults.com.br/api/v1/leads"

# Testar como API Key
curl -H "X-API-Key: $TOKEN" \
     -H "User-Agent: Mozilla/5.0" \
     "https://developer.sults.com.br/api/v1/leads"
```

## Status do Código

✅ **URL correta**: `https://developer.sults.com.br/api/v1`  
✅ **Endpoint correto**: `/leads`  
✅ **Conexão funcionando**: Status 200  
❌ **Autenticação**: Retornando HTML (precisa ajustar token/formato)

## Próximos Passos

1. Verificar documentação de autenticação
2. Gerar novo token se necessário
3. Testar diferentes formatos de autenticação
4. Contatar suporte se persistir

