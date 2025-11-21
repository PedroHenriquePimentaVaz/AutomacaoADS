# 📋 Passo a Passo: Descobrir API SULTS

## Você está na página: behonestbrasil.sults.com.br/seguranca/api

### Passo 1: Verificar a Documentação
1. **Clique no card "Documentação"**
2. Procure por:
   - URL base da API (ex: `https://behonestbrasil.sults.com.br/api/v1`)
   - Exemplos de endpoints (ex: `/chamados`, `/leads`)
   - Formato de autenticação (Bearer Token, API Key, etc.)
   - Exemplos de requisições (curl, código)

### Passo 2: Verificar Gestão de Tokens
1. **Clique no card "Gestão de Tokens"**
2. Verifique:
   - Se o token `O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=` está listado
   - Como o token deve ser usado (formato de autenticação)
   - Se há permissões configuradas
   - Se o token está ativo

### Passo 3: Inspecionar Requisições Reais
1. **Abra o DevTools** (pressione F12)
2. Vá para a aba **Network** (Rede)
3. Na barra de busca, digite: `api` ou `xhr`
4. **Navegue para uma página que mostra dados:**
   - Clique em "Chamados" no menu lateral
   - Ou clique em "Home" e depois em algum card que mostre dados
5. **Observe as requisições** que aparecem no Network
6. **Clique em uma requisição** que busque dados
7. **Copie:**
   - Request URL (URL completa)
   - Headers → Authorization (se existir)
   - Headers → Cookie (se existir)
   - Response (exemplo da resposta JSON)

## O que me enviar

Depois de fazer os passos acima, me envie:

1. **Da Documentação:**
   - URL base da API
   - Exemplo de endpoint
   - Formato de autenticação

2. **Da Gestão de Tokens:**
   - Status do token
   - Como deve ser usado

3. **Do DevTools (Network):**
   - URL completa de uma requisição real
   - Headers de autenticação
   - Exemplo de resposta

Com essas informações, atualizo o código para funcionar! 🚀

