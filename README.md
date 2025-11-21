# 📊 ADS Dashboard - BeHonest

Dashboard web para análise de campanhas publicitárias com integração automática ao Google Drive.

## 🚀 Início Rápido

### Opção 1: Docker (Recomendado)

```bash
docker compose up --build
```

Acesse: http://localhost:5000

### Opção 2: Local

```bash
# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Executar aplicação
python app_web.py
```

## 📋 Pré-requisitos

- Python 3.11+
- Docker e Docker Compose (para execução via Docker)
- Credenciais do Google Drive (arquivo JSON)
- Arquivo `.env` configurado

## ⚙️ Configuração

### Arquivo `.env`

Crie um arquivo `.env` na raiz do projeto:

```env
DRIVE_FILE_ID=1JIFkoM-GkxDKCu0AuF84jPqkqURgr8H3E0eKcrUkkrY
LEADS_FILE_ID=1f-dvv2zLKbey__rug-T5gJn-NkNmf7EWcQv3Tb9IvM8
GOOGLE_ADS_FILE_ID=1JIFkoM-GkxDKCu0AuF84jPqkqURgr8H3E0eKcrUkkrY
GOOGLE_APPLICATION_CREDENTIALS=sixth-now-475017-k8-785034518ab7.json
LEADS_SHEETS_PRIORITY=Leads Be Honest 2
SULTS_API_TOKEN=O2JlaG9uZXN0YnJhc2lsOzE3NTQ0MDAwMTgwOTM=
```

### Credenciais do Google Drive

1. Coloque o arquivo `sixth-now-475017-k8-785034518ab7.json` na raiz do projeto
2. Certifique-se de que o service account tem acesso aos arquivos no Google Drive

## 📊 Funcionalidades

### Análise Automática
- Carregamento de múltiplas planilhas (ADS Geral e Google Ads)
- Upload inteligente de planilhas
- Detecção automática de colunas
- Cálculo de KPIs em tempo real
- Processamento inteligente de dados mistos (texto e números)

### Métricas Calculadas
- Total de Leads e MQLs
- Taxa de conversão Lead → MQL
- Custo por Lead (CPL)
- Custo por MQL (CPMQL)
- Leads/MQLs por aparição
- Ranking de criativos
- Investimento da última semana

### Visualizações
- Gráficos interativos (Chart.js)
- Investimento diário da última semana (formato DD/MM/YYYY)
- Evolução temporal de criativos
- Distribuição de leads por data
- Performance de conversão
- Tabelas detalhadas
- Cards de destaque
- Design responsivo

### Dashboard de Leads
- Upload dedicado via botão **Carregar Leads** (CSV/XLSX)
- Combinação automática de todas as abas com dados (suporta milhares de registros)
- KPIs automáticos (entradas recentes, conversões, perdas, responsáveis)
- Distribuição dos principais status, origens e atendentes
- Gráficos de timeline, status e fontes com Chart.js
- Tabelas com últimos leads atualizados e base completa com busca e paginação
- Metadados exibindo resumo da planilha (quantidade de abas e registros)
- Prioridade configurável de abas via `LEADS_SHEETS_PRIORITY` (lista separada por vírgula)

### Integração Google Drive
- Download automático de planilhas
- Atualização em tempo real
- Exportação inteligente de Google Sheets
- Suporte para múltiplas planilhas
- Leitura de abas específicas (ex: "Controle Google ADS")

### Integração SULTS API
- Sincronização de leads com a plataforma SULTS
- Foco exclusivo em negócios abertos (status Andamento/Adiado) para garantir a análise apenas de oportunidades ativas
- Detecção automática de MQLs diretamente das etiquetas retornadas pelo endpoint `/expansao/negocio`
- Busca de chamados e status de leads
- Consulta de unidades e projetos
- Endpoints disponíveis:
  - `GET /api/sults/verificar-leads` - Verifica leads abertos/perdidos (recomendado)
  - `GET /api/sults/test` - Testa conexão com a API
  - `GET /api/sults/diagnose` - Diagnóstico detalhado de autenticação
  - `GET /api/sults/leads-status` - Busca leads por status (aberto, perdido, ganho)
  - `GET /api/sults/chamados` - Busca chamados (parâmetros: `date_from`, `date_to`)
  - `POST /api/sults/sync-lead` - Sincroniza um lead com a SULTS
- Token configurável via variável de ambiente `SULTS_API_TOKEN`
- Documentação da API: https://developers.sults.com.br/

#### Como Verificar se a Integração SULTS Está Funcionando

1. **Teste rápido:**
   ```bash
   curl http://localhost:5003/api/sults/verificar-leads
   ```
   Ou acesse no navegador: `http://localhost:5003/api/sults/verificar-leads`

2. **Se não funcionar, execute o diagnóstico:**
   ```bash
   curl http://localhost:5003/api/sults/diagnose
   ```

3. **Teste manual com script:**
   ```bash
   python testar_sults_manual.py
   ```

4. **Siga o guia completo:**
   - Leia `GUIA_BUSCAR_DADOS_SULTS.md` para descobrir a URL correta da API
   - Use o DevTools do navegador (F12) para inspecionar requisições

## 🎨 Design System

Baseado no Brandbook BeHonest:
- **Cores**: Navy Blue (#003366), Mustard (#EDB125), Blue (#0066CC)
- **Fonte**: Poppins
- **Componentes**: Cards, botões, gráficos personalizados

## 📁 Estrutura do Projeto

```
ADS/
├── app_web.py              # Aplicação Flask principal
├── requirements.txt        # Dependências Python
├── Dockerfile             # Configuração Docker
├── docker-compose.yml     # Orquestração Docker
├── .dockerignore          # Arquivos ignorados pelo Docker
├── .env                   # Variáveis de ambiente (não versionado)
├── static/
│   ├── css/
│   │   └── style.css      # Estilos BeHonest
│   ├── js/
│   │   └── app.js         # JavaScript do dashboard
│   └── images/
│       ├── behonest-logo.png
│       └── favicon.png
└── templates/
    └── index.html         # Template principal
```

## 🔧 Desenvolvimento

### Executar em modo desenvolvimento
```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
python app_web.py
```

### Docker
```bash
# Construir imagem
docker compose build

# Executar
docker compose up

# Executar em background
docker compose up -d

# Ver logs
docker compose logs -f

# Parar
docker compose down
```

## 🐳 Docker

O dashboard está totalmente containerizado para facilitar o deploy e manter consistência entre ambientes.

### Como Usar

1. **Certifique-se de ter os arquivos configurados:**
   - Arquivo de credenciais: `sixth-now-475017-k8-785034518ab7.json`
   - Arquivo `.env` com as variáveis de ambiente

2. **Construa e execute:**
   ```bash
   docker compose up --build
   ```

3. **Acesse o dashboard:**
   ```
   http://localhost:5000
   ```

### Comandos Úteis

- **Ver logs em tempo real**: `docker compose logs -f`
- **Parar o container**: `docker compose down`
- **Executar em background**: `docker compose up -d`
- **Reconstruir após mudanças**: `docker compose down && docker compose up --build`

### Funcionalidades no Docker

✓ Carregamento automático de múltiplas planilhas do Google Drive  
✓ Separação entre ADS Geral e Google Ads  
✓ Processamento inteligente de dados (texto e números)  
✓ Cálculo automático de CPL e CPMQL  
✓ Análise detalhada de criativos  
✓ Visualizações interativas (Chart.js)  
✓ Formatos de data brasileiros (DD/MM/YYYY)  
✓ Design responsivo com identidade BeHonest  
✓ Botão de voltar ao início  
✓ Leitura de abas específicas do Google Sheets

## 📖 Documentação

- [DOCKER_SETUP.md](DOCKER_SETUP.md) - Guia completo de setup Docker
- [GITHUB_SETUP.md](GITHUB_SETUP.md) - Configuração Git e GitHub

## 🐛 Troubleshooting

### Erro de credenciais do Google Drive
Verifique se o arquivo JSON existe e está no diretório correto.

### Erro ao processar arquivo
O sistema foi configurado para detectar automaticamente se uma coluna é texto ou número. Se ainda ocorrer erro:
- Verifique se a planilha não tem células mescladas
- Certifique-se de que as colunas estão formatadas corretamente
- Verifique os logs com `docker compose logs -f`

### Docker não inicia
```bash
docker compose down -v
docker compose build --no-cache
docker compose up
```

### Erro ao carregar Google Ads
- Verifique se o ID da planilha no `.env` está correto
- Certifique-se de que a aba "Controle Google ADS" existe
- Verifique os logs para detalhes específicos

## 📝 Licença

Proprietário - BeHonest
