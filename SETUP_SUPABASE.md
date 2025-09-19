# 🚀 Configuração do Supabase para Lia AI Service

## 📋 Pré-requisitos

1. **Projeto Supabase ativo**: Lia App (ID: wyjpmzfijtufgxgdivgl)
2. **OpenAI API Key**: Já configurada ✅
3. **Service Role Key**: Precisa ser configurada

## 🔧 Passo a Passo

### 1. Obter a Service Role Key

1. Acesse o [Painel do Supabase](https://supabase.com/dashboard)
2. Selecione o projeto **Lia App**
3. Vá em **Settings** → **API**
4. Copie a **service_role** key (não a anon key!)

### 2. Configurar a Service Role Key

Edite o arquivo `lia-ai-service/.env`:

```bash
# Substitua pela sua service role key real
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sua_service_role_key_aqui
```

### 3. Criar as Tabelas no Supabase

1. Acesse o **SQL Editor** no painel do Supabase
2. Execute o script `database_setup.sql`:

```sql
-- Cole todo o conteúdo do arquivo database_setup.sql aqui
```

### 4. Testar a Conexão

```bash
curl -s http://localhost:8000/test-supabase
```

**Resposta esperada:**
```json
{
  "success": true,
  "message": "Supabase connection successful",
  "configured": true,
  "tables_accessible": true,
  "conversation_count": 0
}
```

## 🎯 Funcionalidades Implementadas

### ✅ **Salvamento Automático**
- Todas as mensagens são salvas automaticamente no Supabase
- Conversas são criadas automaticamente
- Histórico persistente entre sessões

### ✅ **APIs Disponíveis**

#### Chat com IA
```bash
POST /chat
{
  "message": "Sua mensagem",
  "conversation_id": "uuid-da-conversa",
  "user_id": "uuid-do-usuario"
}
```

#### Listar Conversas do Usuário
```bash
GET /conversations/{user_id}
```

#### Obter Mensagens de uma Conversa
```bash
GET /conversation/{conversation_id}/messages
```

#### Health Check Completo
```bash
GET /health
```

#### Testar Supabase
```bash
GET /test-supabase
```

## 🔒 Segurança

- **Row Level Security (RLS)** habilitado
- Usuários só acessam suas próprias conversas
- Service role key para operações do servidor
- Políticas de segurança configuradas

## 📊 Estrutura do Banco

### Tabela: `ai_conversations`
- `id`: UUID da conversa
- `user_id`: UUID do usuário
- `title`: Título da conversa
- `created_at`: Data de criação
- `updated_at`: Última atualização
- `metadata`: Dados adicionais (JSON)

### Tabela: `ai_messages`
- `id`: UUID da mensagem
- `conversation_id`: Referência à conversa
- `user_id`: UUID do usuário
- `role`: 'user' ou 'assistant'
- `content`: Conteúdo da mensagem
- `message_id`: ID único da mensagem
- `created_at`: Data de criação
- `metadata`: Dados adicionais (JSON)

## 🚨 Troubleshooting

### Erro 401 - Invalid API key
- Verifique se a service role key está correta
- Confirme que não está usando a anon key

### Tabelas não encontradas
- Execute o script `database_setup.sql`
- Verifique se as tabelas foram criadas

### Conexão falha
- Verifique se o URL do Supabase está correto
- Teste a conectividade de rede

## 🎉 Status Atual

- ✅ **OpenAI**: Configurado e funcionando
- ✅ **Supabase Client**: Inicializado
- ⚠️ **Service Role Key**: Precisa ser configurada
- ⚠️ **Tabelas**: Precisam ser criadas
- ✅ **Fallback**: Cache local funcionando

Após configurar a service role key e criar as tabelas, todas as conversas serão salvas automaticamente no Supabase! 🚀
