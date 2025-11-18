# 🔍 Como Descobrir a URL Correta da API SULTS

## Método 1: Verificar a Documentação Oficial (Recomendado)

### Passo a passo:

1. **Acesse a documentação:**
   ```
   https://developers.sults.com.br/
   ```

2. **Procure por seções como:**
   - "Getting Started" ou "Início Rápido"
   - "Base URL" ou "URL Base"
   - "API Endpoint" ou "Endpoint da API"
   - "Authentication" ou "Autenticação"
   - Exemplos de requisições

3. **Procure por exemplos de código:**
   - Exemplos em cURL
   - Exemplos em JavaScript/Node.js
   - Exemplos em Python
   - Qualquer exemplo mostrará a URL base

4. **Procure por variáveis de ambiente:**
   - Algumas documentações mostram: `BASE_URL=https://...`
   - Ou: `API_URL=https://...`

## Método 2: Inspecionar Requisições no Navegador

Se você já usa a plataforma SULTS no navegador:

1. **Abra o SULTS no navegador** (https://app.sults.com.br ou similar)

2. **Abra as Ferramentas de Desenvolvedor:**
   - Pressione `F12` ou `Ctrl+Shift+I` (Linux/Windows)
   - Ou `Cmd+Option+I` (Mac)

3. **Vá para a aba "Network" (Rede):**
   - Clique na aba "Network" ou "Rede"
   - Recarregue a página (`F5`)

4. **Procure por requisições de API:**
   - Filtre por "XHR" ou "Fetch"
   - Procure por requisições que contenham:
     - `api` no nome
     - `chamados`, `leads`, `unidades`, etc.
     - Status 200 (sucesso)

5. **Clique em uma requisição e veja:**
   - **Headers** → **Request URL**: Mostra a URL completa
   - Exemplo: `https://api.sults.com.br/v1/chamados`
   - A parte antes do endpoint é a URL base!

## Método 3: Verificar o Código Fonte (se tiver acesso)

Se você tem acesso ao código que já integra com SULTS:

1. **Procure por arquivos de configuração:**
   ```bash
   # Procure por variáveis de ambiente
   grep -r "SULTS" .env*
   grep -r "sults" *.js *.py *.json
   ```

2. **Procure por URLs hardcoded:**
   ```bash
   grep -r "https://.*sults" .
   grep -r "api.*sults" .
   ```

## Método 4: Usar Ferramentas de Inspeção de Rede

### Usando curl para testar:

```bash
# Testar se a API responde em diferentes portas
curl -I https://app.sults.com.br
curl -I https://api.sults.com.br
curl -I https://sults.com.br

# Verificar headers que podem revelar a API
curl -I https://app.sults.com.br | grep -i "api"
```

### Usando navegador com extensão:

1. **Instale uma extensão como:**
   - "REST Client" (Chrome/Firefox)
   - "Postman Interceptor"
   - "ModHeader"

2. **Intercepte requisições** enquanto usa o SULTS

## Método 5: Contatar o Suporte da SULTS

Se nenhum método acima funcionar:

### Informações para solicitar:

```
Olá, equipe SULTS!

Estou tentando integrar com a API REST da SULTS e preciso das seguintes informações:

1. URL base da API REST (ex: https://api.sults.com.br/v1)
2. Formato de autenticação (Bearer Token, API Key, Basic Auth, etc.)
3. Lista de endpoints disponíveis (ex: /chamados, /leads, /unidades)
4. Exemplo de requisição funcionando (curl ou código)
5. Documentação completa da API (se disponível)

Meu token atual é: O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=

Agradeço desde já!
```

### Canais de contato:

- **Email de suporte** (se disponível no site)
- **Chat de suporte** (se disponível)
- **Portal de ajuda**: https://ajuda.sults.com.br/
- **Comunidade/Forum** (se existir)

## Método 6: Verificar Arquivos de Configuração do SULTS

Se você tem acesso ao sistema SULTS:

1. **Procure por:**
   - Arquivos `.env` ou `.config`
   - Configurações de integração
   - Webhooks configurados
   - Integrações com Make/Zapier (mostram URLs de API)

## Método 7: Testar URLs Comuns de APIs

Algumas APIs seguem padrões comuns. Teste:

```bash
# Padrões comuns
https://api.sults.com.br/v1
https://api.sults.com.br/v2
https://api.sults.com.br/rest
https://app.sults.com.br/api/v1
https://sults.com.br/api/v1
https://api.sults.com.br/graphql  # Se for GraphQL
```

## 🎯 Checklist Rápido

- [ ] Verifiquei a documentação em developers.sults.com.br
- [ ] Inspecionei requisições no navegador (F12 → Network)
- [ ] Procurei no código fonte por URLs
- [ ] Testei URLs comuns de API
- [ ] Contatei o suporte da SULTS
- [ ] Verifiquei arquivos de configuração

## 💡 Dica Final

**A forma mais rápida:** Use as Ferramentas de Desenvolvedor do navegador (F12) enquanto usa o SULTS. As requisições de API aparecerão na aba Network e mostrarão a URL exata!

## 📝 Quando Descobrir

Quando encontrar a URL correta, configure no `.env`:

```env
SULTS_API_BASE_URL=https://url-que-funcionou
SULTS_API_TOKEN=O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=
```

E teste:

```bash
curl http://localhost:5003/api/sults/test
```

