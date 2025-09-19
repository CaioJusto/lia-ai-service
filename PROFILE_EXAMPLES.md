# 👤 Sistema de Perfis de Usuário - Lia AI

## 🎯 Visão Geral

O sistema de perfis permite que a Lia conheça cada usuário individualmente, personalizando as respostas baseadas em:
- Nome e informações pessoais
- Nível educacional
- Matérias favoritas
- Estilo de aprendizagem
- Objetivos de estudo
- Tópicos com dificuldade
- Preferências de explicação

## 📋 Estrutura do Perfil

```json
{
  "user_id": "1fc97b40-7833-4761-a5a0-52fa8fa8a0f1",
  "name": "João Silva",
  "age": 17,
  "education_level": "ensino_medio",
  "favorite_subjects": ["Física", "Matemática", "Química"],
  "learning_style": "visual",
  "study_goals": ["ENEM", "Vestibular USP", "Melhorar em Física"],
  "difficulty_topics": ["Química Orgânica", "Geometria Analítica"],
  "preferred_explanation_style": "friendly",
  "timezone": "America/Sao_Paulo",
  "study_schedule": {
    "morning": true,
    "afternoon": false,
    "evening": true
  }
}
```

## 🚀 Como Usar

### 1. Criar Perfil (Setup Wizard)

```bash
curl -X POST http://localhost:8000/profile/setup-wizard \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "1fc97b40-7833-4761-a5a0-52fa8fa8a0f1",
    "profile_data": {
      "name": "João Silva",
      "age": 17,
      "education_level": "ensino_medio",
      "favorite_subjects": ["Física", "Matemática"],
      "learning_style": "visual",
      "study_goals": ["ENEM", "Vestibular USP"],
      "difficulty_topics": ["Química Orgânica"]
    }
  }'
```

### 2. Obter Perfil

```bash
curl http://localhost:8000/profile/1fc97b40-7833-4761-a5a0-52fa8fa8a0f1
```

### 3. Atualizar Perfil

```bash
curl -X POST http://localhost:8000/profile/update \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "1fc97b40-7833-4761-a5a0-52fa8fa8a0f1",
    "profile_data": {
      "favorite_subjects": ["Física", "Matemática", "História"],
      "study_goals": ["ENEM", "Vestibular USP", "Melhorar notas"]
    }
  }'
```

## 🎭 Exemplos de Personalização

### Sem Perfil
**Pergunta**: "Me explique sobre força centrípeta"
**Resposta**: "Oi! A força centrípeta é uma força que atua em direção ao centro de uma trajetória circular..."

### Com Perfil (João, 17 anos, ensino médio, estilo visual)
**Pergunta**: "Me explique sobre força centrípeta"
**Resposta**: "Oi João! 😊 Vou te explicar força centrípeta de um jeito visual que vai facilitar para o ENEM!

Imagine você girando uma pedra amarrada numa corda - a força que você faz puxando a corda para o centro é a força centrípeta! 🌀

Como você gosta de física, vou dar um exemplo prático: quando um carro faz uma curva, os pneus fazem força centrípeta para manter o carro na trajetória circular.

**Fórmula**: Fc = m × v² / r

Quer que eu desenhe um diagrama mental para você visualizar melhor? 📊"

### Com Perfil (Maria, superior, estilo formal)
**Pergunta**: "Me explique sobre força centrípeta"
**Resposta**: "Olá Maria! A força centrípeta é definida como a componente da força resultante que atua perpendicularmente à velocidade, direcionada para o centro da trajetória curvilínea.

Matematicamente, expressa-se como Fc = mv²/r, onde m representa a massa, v a velocidade tangencial e r o raio de curvatura.

Esta força é fundamental na análise de movimentos circulares uniformes e tem aplicações diretas em mecânica clássica e dinâmica rotacional."

## 🎨 Estilos de Aprendizagem

### Visual
- Usa mais diagramas, gráficos, mapas mentais
- Sugere desenhos e esquemas
- Exemplos visuais e analogias gráficas

### Auditivo
- Explica como se fosse uma conversa
- Sugere repetir em voz alta
- Usa ritmos e músicas para memorização

### Cinestésico
- Exemplos práticos e experimentos
- Atividades hands-on
- Analogias com movimento e toque

### Leitura/Escrita
- Resumos estruturados
- Listas e tópicos organizados
- Sugestões de anotações

## 📚 Níveis Educacionais

### Ensino Médio
- Linguagem mais simples
- Foco em vestibular/ENEM
- Exemplos do cotidiano
- Motivação extra

### Superior
- Linguagem técnica apropriada
- Conceitos mais avançados
- Referências acadêmicas
- Conexões interdisciplinares

### Pós-graduação
- Abordagem acadêmica
- Discussões teóricas
- Referências científicas
- Análise crítica

## 🎯 Objetivos de Estudo

A Lia adapta as respostas baseada nos objetivos:
- **ENEM**: Foca em questões típicas, dicas de prova
- **Vestibular específico**: Adapta ao estilo da universidade
- **Concurso**: Enfatiza aspectos práticos e aplicações
- **Melhoria de notas**: Reforço e exercícios extras

## 🚨 Tópicos Difíceis

Quando o usuário pergunta sobre tópicos marcados como difíceis:
- Explicação mais detalhada e paciente
- Quebra em passos menores
- Mais exemplos e analogias
- Encorajamento extra
- Sugestão de exercícios graduais

## 🔄 Integração com Chat

O perfil é automaticamente carregado a cada conversa, tornando todas as respostas personalizadas sem necessidade de configuração adicional pelo usuário.
