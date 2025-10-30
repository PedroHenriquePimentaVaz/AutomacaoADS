# 🐳 Setup Docker - ADS Dashboard

## 📋 Pré-requisitos

- Docker instalado: https://docs.docker.com/get-docker/
- Docker Compose instalado: https://docs.docker.com/compose/install/

## 🚀 Como Executar

### 1. Certifique-se de que o arquivo `.env` existe e está configurado:

```bash
cat .env
```

Deve conter:
```
DRIVE_FILE_ID=seu_file_id_aqui
GOOGLE_APPLICATION_CREDENTIALS=sixth-now-475017-k8-785034518ab7.json
```

### 2. Certifique-se de que o arquivo de credenciais existe:

```bash
ls -lh sixth-now-475017-k8-785034518ab7.json
```

### 3. Construa e execute o container:

```bash
docker compose up --build
```

### 4. Acesse o dashboard:

```
http://localhost:5000
```

## 📝 Comandos Úteis

### Parar o container:
```bash
docker compose down
```

### Executar em background:
```bash
docker compose up -d
```

### Ver logs:
```bash
docker compose logs -f
```

### Reconstruir após mudanças:
```bash
docker compose down
docker compose up --build
```

## 🔧 Configuração

### Porta
Para alterar a porta, edite o arquivo `docker-compose.yml`:
```yaml
ports:
  - "8080:5000"  # Acesso externo : Porta interna
```

### Variáveis de Ambiente
As variáveis são carregadas do arquivo `.env` automaticamente.

## 🐛 Troubleshooting

### Erro: "Cannot connect to the Docker daemon"
```bash
sudo systemctl start docker
```

### Erro: "GOOGLE_APPLICATION_CREDENTIALS not found"
Verifique se o arquivo `sixth-now-475017-k8-785034518ab7.json` existe no diretório raiz.

### Limpar tudo e recomeçar:
```bash
docker compose down -v
docker compose build --no-cache
docker compose up
```

