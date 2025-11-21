# 🔧 Troubleshooting: Network não mostra requisições

## Problema
Não aparecem requisições de API ou XHR no Network

## Soluções

### 1. Limpar o filtro e ver TODAS as requisições
1. No Network, **remova o filtro** (deixe vazio)
2. **Recarregue a página** (F5) com o Network aberto
3. Veja **todas as requisições** que aparecem
4. Procure por requisições que:
   - Tenham status 200
   - Sejam maiores que alguns KB
   - Tenham nomes estranhos ou números

### 2. Verificar tipos de requisições
No Network, há filtros por tipo:
- Clique em **"All"** para ver tudo
- Ou tente: **"Fetch/XHR"**, **"JS"**, **"Doc"**

### 3. Recarregar com Network aberto
1. **Feche e abra o DevTools novamente** (F12)
2. Vá para Network
3. **Recarregue a página** (F5)
4. Observe as requisições aparecendo em tempo real

### 4. Interagir com a página
1. Com o Network aberto, **clique em botões/filtros** na página
2. Tente:
   - Filtrar chamados por data
   - Mudar de página (pagination)
   - Buscar algo
   - Qualquer ação que recarregue dados

### 5. Verificar se dados já estão carregados
- Se a página já carregou os dados antes de abrir o Network, eles não aparecerão
- **Solução:** Recarregue a página (F5) com o Network já aberto

### 6. Verificar Console para erros
1. Vá para a aba **"Console"**
2. Veja se há erros ou mensagens
3. Pode haver informações sobre requisições falhadas

### 7. Alternativa: Verificar código fonte
1. Vá para a aba **"Sources"** ou **"Fontes"**
2. Procure por arquivos JavaScript
3. Procure por termos como: `api`, `fetch`, `axios`, `chamados`, `leads`
4. Isso pode mostrar como as requisições são feitas

## O que fazer agora

1. **Limpe o filtro** no Network (deixe vazio)
2. **Recarregue a página** (F5) com o Network aberto
3. **Me diga:** Quantas requisições aparecem? Quais são os nomes delas?

Ou me diga:
- A página de Chamados mostra dados? (chamados listados)
- Como os dados aparecem? (tabela, cards, lista)
- Há botões de filtro ou paginação?

Com essas informações, posso ajudar de outra forma!

