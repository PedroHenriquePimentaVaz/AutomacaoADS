# 🔍 Como Descobrir a API SULTS para Buscar Dados da BeHonest

## Objetivo
Buscar os dados da conta **BeHonest** que estão no SULTS e exibir no nosso dashboard:
- Leads abertos
- Leads perdidos  
- Leads ganhos
- Chamados
- Outros dados relevantes

## O que já temos
- ✅ Token da conta BeHonest: `O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=`
- ✅ Código pronto para buscar dados (quando descobrirmos a URL)
- ✅ Endpoints criados no dashboard

## O que precisamos descobrir

### 1. URL Base da API
A URL completa que o SULTS usa para fazer requisições.

### 2. Formato de Autenticação
Como o token é enviado (header, cookie, parâmetro, etc.)

### 3. Endpoints Disponíveis
Quais endpoints retornam os dados que queremos.

## Como descobrir (usando DevTools)

### Passo 1: Abrir o SULTS no navegador
1. Acesse: `https://behonestbrasil.sults.com.br`
2. Faça login na sua conta

### Passo 2: Abrir DevTools
- Pressione **F12**
- Ou: Botão direito → "Inspecionar"

### Passo 3: Ir para aba Network
- Clique na aba **"Network"** ou **"Rede"**
- Na barra de busca, digite: `api` ou `xhr`

### Passo 4: Navegar no SULTS
1. Clique em **"Chamados"** (card azul)
2. Ou clique em qualquer seção que mostre dados de leads/chamados
3. Observe as requisições aparecendo no Network

### Passo 5: Inspecionar uma requisição
1. **Clique na requisição** que aparecer (geralmente contém `api`, `v1`, `chamados`, `leads`)
2. Vá para a aba **"Headers"**

### Passo 6: Copiar informações importantes

#### A) Request URL (URL completa)
```
Exemplo: https://behonestbrasil.sults.com.br/api/v1/chamados
         ou https://app.sults.com.br/api/leads
```

#### B) Request Method
- GET, POST, etc.

#### C) Request Headers
Procure especialmente por:
- `Authorization: Bearer ...` ou `Authorization: Token ...`
- `X-API-Key: ...`
- `Cookie: ...` (pode conter o token de sessão)
- Qualquer header relacionado a autenticação

#### D) Query String Parameters
- Veja se há parâmetros como `?token=...` ou `?api_key=...`

### Passo 7: Ver a resposta
1. Vá para a aba **"Response"**
2. Veja o formato dos dados retornados (JSON)
3. Copie um exemplo pequeno da resposta

## O que me enviar

Quando encontrar uma requisição que busca dados (chamados, leads, etc.), me envie:

```json
{
  "url_completa": "https://behonestbrasil.sults.com.br/api/v1/chamados",
  "metodo": "GET",
  "headers_importantes": {
    "Authorization": "Bearer ...",
    "Cookie": "...",
    "X-API-Key": "..."
  },
  "query_params": {
    "param1": "valor1"
  },
  "resposta_exemplo": {
    "dados": "..."
  }
}
```

## Exemplo do que procurar

Quando você clicar em "Chamados" no dashboard SULTS, deve aparecer uma requisição tipo:

```
GET https://behonestbrasil.sults.com.br/api/v1/chamados
Headers:
  Authorization: Bearer O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=
  Cookie: JSESSIONID=...
```

Ou pode ser:

```
GET https://app.sults.com.br/api/chamados?token=O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=
```

## Depois que descobrir

Com essas informações, eu atualizo o código para:
1. ✅ Usar a URL correta
2. ✅ Autenticar corretamente
3. ✅ Buscar os dados da BeHonest
4. ✅ Exibir no dashboard

## Dica

Se não aparecer requisições de API quando clicar em "Chamados", tente:
- Recarregar a página (F5) com o Network aberto
- Clicar em outras seções (Leads, Unidades, etc.)
- Verificar se há filtros ou botões que fazem requisições

