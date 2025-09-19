#!/bin/bash

# Lia AI Service Setup Script
echo "🚀 Configurando Lia AI Service..."

# Check if Python 3.8+ is installed
python_version=$(python3 --version 2>&1 | sed 's/Python //' | cut -d. -f1,2)
if [ -z "$python_version" ]; then
    echo "❌ Python 3 não encontrado. Instale Python 3.8+"
    exit 1
fi

echo "✅ Python $python_version encontrado"

# Create virtual environment
echo "📦 Criando ambiente virtual..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Ativando ambiente virtual..."
source venv/bin/activate

# Upgrade pip
echo "⬆️ Atualizando pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Instalando dependências..."
pip install -r requirements.txt

# Copy environment file
if [ ! -f .env ]; then
    echo "📝 Criando arquivo .env..."
    cp .env.example .env
    echo "⚠️  IMPORTANTE: Configure suas variáveis de ambiente no arquivo .env"
else
    echo "✅ Arquivo .env já existe"
fi

echo ""
echo "🎉 Setup concluído!"
echo ""
echo "📋 Próximos passos:"
echo "1. Configure suas variáveis de ambiente no arquivo .env"
echo "2. Execute: source venv/bin/activate"
echo "3. Execute: python main.py"
echo ""
echo "🌐 O serviço estará disponível em: http://localhost:8000"
echo "📖 Documentação da API: http://localhost:8000/docs"
