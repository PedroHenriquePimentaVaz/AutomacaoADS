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
DRIVE_FILE_ID=seu_file_id_do_google_drive
GOOGLE_APPLICATION_CREDENTIALS=sixth-now-475017-k8-785034518ab7.json
```

### Credenciais do Google Drive

1. Coloque o arquivo `sixth-now-475017-k8-785034518ab7.json` na raiz do projeto
2. Certifique-se de que o service account tem acesso ao arquivo no Google Drive

## 📊 Funcionalidades

### Análise Automática
- Upload inteligente de planilhas
- Detecção automática de colunas
- Cálculo de KPIs em tempo real

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
- Investimento diário da última semana
- Evolução temporal de criativos
- Performance de conversão
- Tabelas detalhadas
- Cards de destaque
- Design responsivo

### Integração Google Drive
- Download automático de planilhas
- Atualização em tempo real
- Exportação inteligente de Google Sheets

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

✓ Upload manual de planilhas Excel/CSV  
✓ Carregamento automático do Google Drive  
✓ Cálculo automático de CPL e CPMQL  
✓ Análise detalhada de criativos  
✓ Visualizações interativas (Chart.js)  
✓ Design responsivo com identidade BeHonest

## 📖 Documentação

- [DOCKER_SETUP.md](DOCKER_SETUP.md) - Guia completo de setup Docker
- [GITHUB_SETUP.md](GITHUB_SETUP.md) - Configuração Git e GitHub

## 🐛 Troubleshooting

### Erro de credenciais do Google Drive
Verifique se o arquivo JSON existe e está no diretório correto.

### Erro ao fazer upload
Verifique o formato da planilha e se as colunas necessárias existem.

### Docker não inicia
```bash
docker compose down -v
docker compose build --no-cache
docker compose up
```

## 📝 Licença

Proprietário - BeHonest
