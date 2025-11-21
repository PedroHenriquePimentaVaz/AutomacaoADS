# 🔍 Como Inspecionar Requisições Reais do SULTS

## Objetivo
Descobrir como o SULTS faz requisições para buscar dados (chamados, leads, etc.)

## Passo a Passo

### 1. Abrir DevTools
- Pressione **F12** no navegador
- Ou: Botão direito → "Inspecionar"

### 2. Ir para aba Network
- Clique na aba **"Network"** ou **"Rede"**
- Na barra de busca/filtro, digite: `api` ou `xhr`

### 3. Navegar para uma página com dados
1. No menu lateral do SULTS, clique em **"Chamados"**
2. Ou clique em **"Home"** e depois em algum card que mostre dados
3. **IMPORTANTE:** Deixe o DevTools aberto enquanto navega!

### 4. Observar requisições
- Quando a página carregar, você verá requisições aparecendo no Network
- Procure por requisições que contenham:
  - `api` no nome
  - `chamados`, `leads`, `unidades` no nome
  - Status 200 (verde)

### 5. Inspecionar uma requisição
1. **Clique em uma requisição** que pareça buscar dados
2. Vá para a aba **"Headers"**
3. Procure por:
   - **Request URL** (URL completa)
   - **Request Headers** → **Authorization** (se existir)
   - **Request Headers** → **Cookie** (se existir)
   - **Query String Parameters** (se existir)

### 6. Ver a resposta
1. Vá para a aba **"Response"**
2. Veja o formato dos dados (deve ser JSON)
3. Copie um pequeno exemplo

## O que copiar e me enviar

Quando encontrar uma requisição que busca dados, copie:

```
URL: https://behonestbrasil.sults.com.br/api/v1/chamados
Headers:
  Authorization: Bearer O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=
  Cookie: JSESSIONID=...
Response: { "dados": [...] }
```

## Dica
Se não aparecer requisições:
- Recarregue a página (F5) com o Network aberto
- Tente clicar em diferentes seções (Chamados, Leads, Unidades)
- Verifique se o filtro está correto (api ou xhr)

