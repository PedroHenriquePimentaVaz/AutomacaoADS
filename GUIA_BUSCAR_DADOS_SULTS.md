# 🔍 Guia Prático: Como Descobrir a API SULTS

## Passo 1: Abrir o DevTools do Navegador

1. No navegador (Chrome/Edge/Firefox), pressione **F12** ou **Ctrl+Shift+I** (Linux) / **Cmd+Option+I** (Mac)
2. Vá para a aba **Network** (Rede)

## Passo 2: Filtrar Requisições da API

1. Na barra de busca do Network, digite: `api` ou `sults`
2. Isso vai filtrar apenas as requisições relacionadas à API

## Passo 3: Navegar no Dashboard SULTS

1. Com o DevTools aberto, navegue pelo dashboard:
   - Clique em **"Chamados"** (card azul com ícone de balão)
   - Clique em **"Leads"** (se houver)
   - Clique em **"Analytics"** (card amarelo com gráfico)
   - Qualquer seção que mostre dados

2. **Observe as requisições aparecendo no Network**

## Passo 4: Inspecionar uma Requisição

Quando uma requisição aparecer:

1. **Clique na requisição** (geralmente começa com `api`, `v1`, ou `sults`)
2. Vá para a aba **Headers** (Cabeçalhos)
3. Procure por:

### Informações Importantes:

#### A) URL Completa
- Copie a **URL completa** da requisição
- Exemplo: `https://behonestbrasil.sults.com.br/api/v1/leads`
- Ou: `https://app.sults.com.br/api/chamados`

#### B) Método HTTP
- Geralmente é **GET** para buscar dados
- Pode ser **POST** para criar/atualizar

#### C) Headers de Autenticação
Procure por um destes headers:
- `Authorization: Bearer TOKEN_AQUI`
- `Authorization: Token TOKEN_AQUI`
- `X-API-Key: TOKEN_AQUI`
- `X-Auth-Token: TOKEN_AQUI`
- `Cookie: session=...` ou `token=...`

#### D) Query Parameters
Na aba **Query String Parameters** ou **Payload**:
- Veja se o token é enviado como `?token=...`
- Ou como parte do body JSON

## Passo 5: Verificar a Resposta

1. Vá para a aba **Response** (Resposta)
2. Veja o formato dos dados retornados (JSON, XML, etc.)
3. Isso confirma se a requisição funcionou

## Passo 6: Copiar as Informações

Copie e me envie:

```json
{
  "url_completa": "https://...",
  "metodo": "GET ou POST",
  "headers": {
    "Authorization": "...",
    "X-API-Key": "...",
    "Outro-Header": "..."
  },
  "query_params": {
    "param1": "valor1"
  },
  "resposta_exemplo": "..."
}
```

## Exemplo Prático

1. Abra o DevTools (F12)
2. Vá para Network
3. Filtre por "api"
4. Clique em "Chamados" no dashboard
5. Clique na requisição que aparecer
6. Copie:
   - A URL completa
   - Os headers (especialmente Authorization)
   - Um exemplo da resposta

## Dica Extra: Usar o Console

1. Vá para a aba **Console** do DevTools
2. Digite: `localStorage.getItem('token')` ou `sessionStorage.getItem('token')`
3. Isso pode mostrar se o token está armazenado localmente

## O que fazer com essas informações?

Envie para mim:
- A URL completa da requisição
- Como o token é enviado (header, URL, cookie)
- Um exemplo da resposta JSON

Com isso, atualizo o código para funcionar corretamente! 🚀

