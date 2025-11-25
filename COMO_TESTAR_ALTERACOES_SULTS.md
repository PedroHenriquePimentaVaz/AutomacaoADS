# 🧪 Como Testar se as Alterações Estão Salvando na SULTS

## Método 1: Teste Prático no Dashboard

1. **Abra o dashboard** e carregue os leads
2. **Tente mudar a fase de um lead:**
   - Clique em "Mudar Fase" em um card de lead
   - Selecione uma nova fase
   - Clique em "Salvar"
   - **Verifique:** Se aparecer erro, os endpoints podem estar incorretos

3. **Tente adicionar uma anotação:**
   - Clique em "Adicionar Anotação"
   - Digite uma anotação de teste
   - Clique em "Salvar"
   - **Verifique:** Se aparecer erro, os endpoints podem estar incorretos

4. **Confirme na SULTS:**
   - Abra o SULTS no navegador
   - Verifique se a fase mudou ou se a anotação apareceu
   - Se não aparecer, os endpoints precisam ser corrigidos

## Método 2: Descobrir Endpoints Corretos via DevTools

### Para Mudança de Fase:

1. **Abra o SULTS no navegador** (https://behonestbrasil.sults.com.br)
2. **Abra DevTools** (F12) → Aba "Network"
3. **Mude a fase de um lead no próprio SULTS:**
   - Encontre um lead
   - Mude a fase dele
   - Observe as requisições no Network
4. **Encontre a requisição:**
   - Procure por requisições PUT/PATCH que contenham:
     - `negocio`, `etapa`, `fase`, `stage`
   - Clique na requisição
5. **Copie as informações:**
   - **Request URL:** Ex: `https://api.sults.com.br/api/v1/expansao/negocio/123`
   - **Request Method:** PUT ou PATCH
   - **Request Payload:** Veja o formato do JSON enviado
   - **Headers:** Veja como a autenticação é feita

### Para Adicionar Anotação:

1. **No SULTS, adicione uma anotação a um lead**
2. **Observe as requisições no Network**
3. **Procure por requisições POST que contenham:**
   - `anotacao`, `comentario`, `note`, `comment`
4. **Copie as informações** (mesmo processo acima)

## Método 3: Verificar Logs do Servidor

Quando você tentar mudar uma fase ou adicionar anotação, verifique os logs do servidor:

```bash
# Se estiver rodando localmente, veja os logs no terminal
# Procure por mensagens de erro como:
# "Erro ao atualizar etapa do negócio..."
# "Erro ao adicionar anotação..."
```

## Método 4: Testar Endpoints Diretamente

Você pode testar os endpoints diretamente via curl ou Postman:

```bash
# Testar mudança de fase
curl -X PUT https://api.sults.com.br/api/v1/expansao/negocio/123 \
  -H "Authorization: O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=" \
  -H "Content-Type: application/json" \
  -d '{"etapaId": 5}'

# Testar adicionar anotação
curl -X POST https://api.sults.com.br/api/v1/expansao/negocio/123/anotacao \
  -H "Authorization: O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=" \
  -H "Content-Type: application/json" \
  -d '{"texto": "Teste de anotação"}'
```

## ⚠️ Se os Endpoints Estiverem Incorretos

Se você descobrir que os endpoints estão incorretos, edite o arquivo `sults_api.py`:

### Para Mudança de Fase:
```python
def update_negocio_etapa(self, negocio_id: int, etapa_id: int) -> Dict:
    # Ajuste o endpoint conforme descoberto no DevTools
    endpoint = f"/expansao/negocio/{negocio_id}"  # ou o endpoint correto
    update_data = {
        'etapaId': etapa_id  # ou o nome do campo correto
    }
    # ... resto do código
```

### Para Anotações:
```python
def add_negocio_anotacao(self, negocio_id: int, anotacao: str, usuario_id: Optional[int] = None) -> Dict:
    # Ajuste o endpoint conforme descoberto no DevTools
    endpoint = f"/expansao/negocio/{negocio_id}/anotacao"  # ou o endpoint correto
    anotacao_data = {
        'texto': anotacao  # ou o nome do campo correto
    }
    # ... resto do código
```

## ✅ Checklist de Verificação

- [ ] Testei mudar fase no dashboard
- [ ] Verifiquei se apareceu erro ou sucesso
- [ ] Confirmei na SULTS se a fase mudou
- [ ] Testei adicionar anotação no dashboard
- [ ] Verifiquei se apareceu erro ou sucesso
- [ ] Confirmei na SULTS se a anotação apareceu
- [ ] Se não funcionou, usei DevTools para descobrir endpoints corretos
- [ ] Ajustei o código com os endpoints corretos

