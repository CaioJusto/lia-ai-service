# 🎓 Lia AI Service

Sistema de IA para o App de Estudos construído em cima de **LangGraph + FastAPI**.

## 🚀 Visão Geral

Um backend Python assíncrono que orquestra agentes educacionais, geração de conteúdo
personalizado (flashcards, quizzes, planos de estudo) e integrações com OpenAI e Supabase.

## 🧠 Principais Tecnologias
- **FastAPI** para APIs assíncronas e escaláveis
- **LangGraph** para orquestração de agentes e fluxos multi-etapa
- **OpenAI (GPT-4.x / GPT-5-nano)** via clientes assíncronos com controle de concorrência
- **Supabase/PostgreSQL** para persistência (conversas, perfis, memórias)
- **AsyncIO** + limitadores de taxa para suportar centenas de requisições simultâneas

## ⚙️ Funcionalidades

### 🤖 Chat com Lia
- Assistente de estudos personalizada com memória de conversação
- Perfil do usuário influencia tom, nível de detalhe e exemplos
- Fallback seguro quando integrações externas estão indisponíveis

### 📚 Geração de Conteúdo
- **Flashcards multi-agente** com monitoramento em tempo real (SSE)
- **Quizzes** e **notas estruturadas** usando ferramentas LangGraph
- **Planos de estudo** personalizados e conversas guiadas

### 🔒 Confiabilidade e Escalabilidade
- Clientes OpenAI centralizados (`openai_utils`) com semáforo (`OPENAI_CONCURRENCY_LIMIT`)
- Geração paralela via `asyncio.gather`, sem `ThreadPoolExecutor`
- Progressos armazenados em cache e expurgados após conclusão
- Logs estruturados (`logger`) para todas as etapas críticas

## 📦 Instalação

### Pré-requisitos
- Python 3.10+
- OpenAI API Key
- Supabase Service Role Key (para persistência opcional)

### Setup rápido
```bash
cd lia-ai-service
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # configure suas credenciais
```

### Variáveis de ambiente essenciais
```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_DEFAULT_MODEL=gpt-5-nano
OPENAI_CONCURRENCY_LIMIT=8  # chamadas simultâneas ao OpenAI

# Supabase (p/ persistência)
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...

# FastAPI
HOST=0.0.0.0
PORT=8000
DEBUG=true
```

## 🏃‍♂️ Executando

### Desenvolvimento
```bash
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Produção
```bash
# Uvicorn standalone
uvicorn main:app --host 0.0.0.0 --port 8000

# Gunicorn + workers assíncronos
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV HOST=0.0.0.0 PORT=8000
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 📖 Endpoints principais

| Método | Rota                              | Descrição                                  |
|--------|-----------------------------------|---------------------------------------------|
| GET    | `/`                               | Status básico                               |
| GET    | `/health`                         | Health-check detalhado                      |
| POST   | `/chat`                           | Chat simples com a Lia                      |
| POST   | `/chat/advanced`                  | Chat com fluxo LangGraph                    |
| POST   | `/generate-flashcards`            | Flashcards multi-agente (SSE em `/progress`) |
| POST   | `/generate-flashcards/from-text`  | Flashcards a partir de texto livre          |
| POST   | `/generate-quiz`                 | Quizzes personalizados                      |
| POST   | `/generate-notes`                | Notas/resumos estruturados                  |
| POST   | `/study-plan/create`             | Plano de estudo personalizado               |

### Exemplo de requisição (`POST /chat`)
```json
{
  "message": "Oi Lia! Pode me explicar fotossíntese?",
  "conversation_id": "conv_123",
  "user_id": "user_456"
}
```

### Monitoramento de progresso SSE
- `GET /progress/{operation_id}` retorna eventos `queued`, `processing`, `completed` com percentuais.

## 🧱 Arquitetura em alto nível

```
src/
├── agents/
│   ├── lia_agent.py                 # Agente LangGraph principal (memórias, ferramentas)
│   └── multi_agent_flashcards.py    # Geração paralela de flashcards (asyncio)
├── models/
│   ├── requests.py
│   └── responses.py
├── routers/
│   ├── chat.py
│   ├── content_generation.py
│   └── health.py
└── services/
    ├── ai_service.py                # Orquestra lógica de IA e progress tracking
    ├── database_service.py          # Supabase (conversas, perfis)
    └── openai_utils.py              # Wrapper assíncrono + semáforo OpenAI
```

- `openai_utils.py`: centraliza clientes `AsyncOpenAI` e impõe limite de concorrência (`OPENAI_CONCURRENCY_LIMIT`).
- `ai_service.py`: expõe endpoints + controla SSE, caching de conversas e fallbacks.
- `multi_agent_flashcards.py`: usa `asyncio.gather` para dividir lotes e reportar progresso.

## 🔗 Integração com o app Expo/React Native

- Requisições locais passam por `/api/lia/*` (proxy do Metro/Expo) ou proxy Express (`LIA_PROXY_PORT`).
- Ajuste as variáveis `EXPO_PUBLIC_LIA_SERVICE_DEV_URL`, `LIA_AI_SERVICE_DEV_URL` e `OPENAI_CONCURRENCY_LIMIT` no `.env` compartilhado.
- SSE (Server-Sent Events) são consumidos com `EventSource` para exibir andamento de gerações longas.

## 🤝 Contribuição e testes

1. Crie um fork / branch
2. Rode lint/testes (ex.: `pytest`, `ruff`, `mypy` se configurado)
3. Descreva na PR alterações e cenários testados

### Testes sugeridos
- `pytest` (unit e integrações futuras)
- Exercícios manuais: `POST /generate-flashcards` e `GET /progress/{id}` para validar SSE
- Monitorar logs (`uvicorn --reload`) verificando concorrência e limites OpenAI

## 📊 Monitoramento e Operação

- **Health-check** automático via `/health`
- Logs estruturados (níveis: info, warning, error)
- Métricas de progresso em `progress_store` e Supabase (quando disponível)
- Ajuste `OPENAI_CONCURRENCY_LIMIT` conforme limites do plano OpenAI para evitar erros 429
