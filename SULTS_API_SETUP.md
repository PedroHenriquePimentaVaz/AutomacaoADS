# 🔧 Configuração da API SULTS

## ⚠️ Erro 404 - Endpoint não encontrado

Se você está recebendo erro 404, significa que a URL base ou os endpoints estão incorretos.

## 📋 Passos para Configurar

### 1. Verificar a Documentação Oficial

Acesse: https://developers.sults.com.br/

Procure por:
- **URL Base da API** (ex: `https://api.sults.com.br`, `https://app.sults.com.br/api`, etc.)
- **Formato de Autenticação** (Bearer Token, Basic Auth, API Key, etc.)
- **Endpoints disponíveis** (ex: `/chamados`, `/leads`, `/tickets`, etc.)

### 2. Configurar no arquivo `.env`

Adicione ou ajuste as variáveis:

```env
# URL base da API SULTS (ajustar conforme documentação)
SULTS_API_BASE_URL=https://app.sults.com.br/api

# Token de autenticação
SULTS_API_TOKEN=O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=
```

### 3. Possíveis URLs Base

Teste estas variações no arquivo `.env`:

```env
# Opção 1
SULTS_API_BASE_URL=https://api.sults.com.br

# Opção 2
SULTS_API_BASE_URL=https://app.sults.com.br/api

# Opção 3
SULTS_API_BASE_URL=https://sults.com.br/api

# Opção 4
SULTS_API_BASE_URL=https://api.sults.com.br/v1
```

### 4. Ajustar Endpoints no Código

Se os endpoints forem diferentes, edite o arquivo `sults_api.py`:

```python
# Exemplo: se o endpoint for /v1/chamados ao invés de /chamados
endpoint = "/v1/chamados"
```

### 5. Verificar Formato de Autenticação

O código atual usa `Bearer Token`. Se a API usar outro formato, edite `sults_api.py`:

```python
# Para Basic Auth:
self.headers = {
    'Authorization': f'Basic {base64.b64encode(f"{username}:{password}".encode()).decode()}',
    ...
}

# Para API Key:
self.headers = {
    'X-API-Key': self.token,
    ...
}
```

### 6. Testar a Conexão

#### Opção A: Via Script Python

Execute o script de diagnóstico completo:

```bash
.venv/bin/python diagnose_sults_api.py
```

Ou o script de teste simples:

```bash
.venv/bin/python test_sults_connection.py
```

#### Opção B: Via API REST (Recomendado)

Teste diferentes URLs diretamente:

```bash
# Teste padrão (usa URL do .env)
curl http://localhost:5003/api/sults/test

# Testar URL específica
curl "http://localhost:5003/api/sults/test?base_url=https://api.sults.com.br&endpoint=/chamados"

# Testar outras URLs comuns
curl "http://localhost:5003/api/sults/test?base_url=https://app.sults.com.br/api&endpoint=/chamados"
curl "http://localhost:5003/api/sults/test?base_url=https://sults.com.br/api&endpoint=/chamados"
curl "http://localhost:5003/api/sults/test?base_url=https://api.sults.com.br/v1&endpoint=/chamados"
```

#### Opção C: Testar Endpoints Diferentes

Se a URL base estiver correta mas o endpoint estiver errado:

```bash
# Testar diferentes endpoints
curl "http://localhost:5003/api/sults/test?base_url=https://app.sults.com.br/api&endpoint=/leads"
curl "http://localhost:5003/api/sults/test?base_url=https://app.sults.com.br/api&endpoint=/tickets"
curl "http://localhost:5003/api/sults/test?base_url=https://app.sults.com.br/api&endpoint=/unidades"
```

## 🔍 Como Encontrar a URL Correta

1. **Acesse a documentação**: https://developers.sults.com.br/
2. **Procure por "Base URL" ou "API Endpoint"**
3. **Verifique exemplos de requisições** na documentação
4. **Teste com curl ou Postman** usando a URL da documentação

## 📞 Suporte

Se não encontrar a informação na documentação, entre em contato com o suporte da SULTS para obter:
- URL base da API
- Formato de autenticação correto
- Lista de endpoints disponíveis

