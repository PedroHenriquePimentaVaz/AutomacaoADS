# 🚀 Configuração do GitHub

## 📋 Passos para conectar ao GitHub:

### 1. Criar repositório no GitHub
1. Acesse [GitHub.com](https://github.com)
2. Clique em "New repository"
3. Nome: `dashboard-behonest-ads`
4. Descrição: `Dashboard BeHonest ADS - Análise de Performance de Campanhas`
5. **NÃO** inicialize com README (já temos um)
6. Clique em "Create repository"

### 2. Conectar repositório local ao GitHub
```bash
# Adicionar remote origin
git remote add origin https://github.com/SEU_USUARIO/dashboard-behonest-ads.git

# Verificar conexão
git remote -v

# Fazer push do código
git branch -M main
git push -u origin main
```

### 3. Configuração adicional
```bash
# Configurar usuário (se não configurado)
git config --global user.name "Seu Nome"
git config --global user.email "seu.email@exemplo.com"

# Verificar configurações
git config --list
```

## 🔐 Arquivos Sensíveis

### ⚠️ IMPORTANTE: NÃO commitar estes arquivos:
- `.env` - Variáveis de ambiente
- `sixth-now-475017-k8-785034518ab7.json` - Credenciais Google Drive
- `.encryption_key` - Chave de criptografia

### ✅ Arquivos de exemplo incluídos:
- `env.example` - Template para variáveis de ambiente
- `credentials_template.json` - Template para credenciais

## 📝 Próximos passos após o push:

1. **Configurar GitHub Actions** (opcional):
   - CI/CD para deploy automático
   - Testes automatizados

2. **Configurar GitHub Pages** (opcional):
   - Deploy do frontend estático
   - Documentação online

3. **Configurar Issues e Projects**:
   - Rastreamento de bugs
   - Planejamento de features

## 🌐 Comandos úteis:

```bash
# Ver status
git status

# Adicionar mudanças
git add .

# Commit com mensagem
git commit -m "Descrição da mudança"

# Push para GitHub
git push origin main

# Pull do GitHub
git pull origin main

# Ver histórico
git log --oneline

# Criar branch
git checkout -b nova-feature

# Voltar para main
git checkout main
```

## 📊 Status atual:
- ✅ Repositório Git inicializado
- ✅ Commit inicial realizado
- ✅ .gitignore configurado
- ✅ Arquivos sensíveis protegidos
- ⏳ Aguardando conexão com GitHub
