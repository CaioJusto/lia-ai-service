"""
Lia AI Agent - Advanced Educational AI with LangGraph
Implementa um agente educacional avançado com memória persistente, 
ferramentas especializadas e capacidades de reflexão.
"""

import os
import json
import uuid
import logging
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime

# LangGraph and LangChain imports
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai.embeddings import OpenAIEmbeddings

# Pydantic for data validation
from pydantic import BaseModel, Field

# Supabase for persistence
from supabase import create_client, Client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LiaAgentState(BaseModel):
    """Estado do agente Lia com memória e contexto"""
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    user_id: str = ""
    thread_id: str = ""
    user_profile: Optional[Dict[str, Any]] = None
    short_term_memories: List[str] = Field(default_factory=list)
    long_term_memories: List[str] = Field(default_factory=list)
    current_subject: Optional[str] = None
    learning_context: Dict[str, Any] = Field(default_factory=dict)
    reflection_notes: List[str] = Field(default_factory=list)

class SupabaseCheckpointSaver(BaseCheckpointSaver):
    """Checkpointer personalizado que salva no Supabase"""

    def __init__(self, supabase_client):
        self.supabase = supabase_client
        super().__init__()

    def put(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata) -> RunnableConfig:
        """Salva um checkpoint no Supabase"""
        try:
            thread_id = config["configurable"]["thread_id"]
            user_id = config["configurable"].get("user_id", "")

            # Serialize checkpoint data
            checkpoint_data = {
                "thread_id": thread_id,
                "user_id": user_id,
                "checkpoint_data": json.dumps(checkpoint),
                "metadata": json.dumps(metadata),
                "created_at": datetime.now().isoformat()
            }

            # Upsert checkpoint
            self.supabase.table("agent_checkpoints").upsert(checkpoint_data, on_conflict="thread_id").execute()

            logger.debug(f"💾 Checkpoint salvo para thread {thread_id}")
            return config

        except Exception as e:
            logger.error(f"Erro ao salvar checkpoint: {e}")
            return config

    def get(self, config: RunnableConfig) -> Optional[Checkpoint]:
        """Carrega um checkpoint do Supabase"""
        try:
            thread_id = config["configurable"]["thread_id"]

            response = self.supabase.table("agent_checkpoints")\
                .select("checkpoint_data")\
                .eq("thread_id", thread_id)\
                .execute()

            if response.data:
                checkpoint_json = response.data[0]["checkpoint_data"]
                checkpoint = json.loads(checkpoint_json)
                logger.debug(f"📚 Checkpoint carregado para thread {thread_id}")
                return checkpoint

            return None

        except Exception as e:
            logger.error(f"Erro ao carregar checkpoint: {e}")
            return None

    def list(self, config: RunnableConfig, limit: int = 10, before: Optional[str] = None) -> List[Checkpoint]:
        """Lista checkpoints (não implementado para este caso)"""
        return []

class LiaEducationalAgent:
    """
    Agente educacional avançado da Lia com LangGraph
    
    Características:
    - Memória de longo prazo (cross-thread)
    - Memória de curto prazo (thread-scoped)
    - Ferramentas educacionais especializadas
    - Sistema de reflexão e melhoria contínua
    - Personalização baseada no perfil do usuário
    """
    
    def __init__(self, openai_api_key: str, supabase_url: str, supabase_key: str):
        self.openai_api_key = openai_api_key
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        
        # Initialize OpenAI with GPT-5 nano (latest and most efficient model)
        self.llm = ChatOpenAI(
            model="gpt-5-nano",
            api_key=openai_api_key,
            temperature=0.7
        )
        
        # Initialize Supabase
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
        # Initialize vector store for memories
        self.memory_store = InMemoryVectorStore(OpenAIEmbeddings(api_key=openai_api_key))
        
        # Initialize graph
        self.graph = None
        self.memory_saver = MemorySaver()
        
        self._setup_tools()
        self._build_graph()
        
    def _setup_tools(self):
        """Configura as ferramentas do agente"""
        
        @tool
        def save_long_term_memory(memory: str, config: RunnableConfig) -> str:
            """Salva uma memória de longo prazo que será compartilhada entre conversas"""
            try:
                user_id = config["configurable"].get("user_id")
                if not user_id:
                    return "Erro: user_id não fornecido"
                
                # Save to vector store
                doc = Document(
                    page_content=memory,
                    metadata={
                        "user_id": user_id,
                        "type": "long_term_memory",
                        "created_at": datetime.now().isoformat()
                    }
                )
                self.memory_store.add_documents([doc])
                
                # Also save to Supabase for persistence
                self.supabase.table("agent_memories").insert({
                    "user_id": user_id,
                    "memory_type": "long_term",
                    "content": memory,
                    "created_at": datetime.now().isoformat()
                }).execute()
                
                logger.info(f"💾 Memória de longo prazo salva para usuário {user_id}")
                return f"Memória salva: {memory}"
                
            except Exception as e:
                logger.error(f"Erro ao salvar memória: {e}")
                return f"Erro ao salvar memória: {str(e)}"
        
        @tool
        def search_long_term_memories(query: str, config: RunnableConfig) -> List[str]:
            """Busca memórias de longo prazo relevantes para o contexto atual"""
            try:
                user_id = config["configurable"].get("user_id")
                if not user_id:
                    return ["Erro: user_id não fornecido"]
                
                # Search in vector store
                docs = self.memory_store.similarity_search(
                    query, 
                    k=5,
                    filter=lambda doc: doc.metadata.get("user_id") == user_id
                )
                
                memories = [doc.page_content for doc in docs]
                logger.info(f"🔍 Encontradas {len(memories)} memórias para: {query}")
                return memories
                
            except Exception as e:
                logger.error(f"Erro ao buscar memórias: {e}")
                return [f"Erro ao buscar memórias: {str(e)}"]
        
        @tool
        def get_user_profile(config: RunnableConfig) -> Dict[str, Any]:
            """Obtém o perfil completo do usuário"""
            try:
                user_id = config["configurable"].get("user_id")
                if not user_id:
                    return {"error": "user_id não fornecido"}
                
                # Get from Supabase
                response = self.supabase.table("user_profiles").select("*").eq("user_id", user_id).execute()
                
                if response.data:
                    profile = response.data[0]
                    logger.info(f"👤 Perfil carregado para usuário {user_id}")
                    return profile
                else:
                    return {"error": "Perfil não encontrado"}
                    
            except Exception as e:
                logger.error(f"Erro ao carregar perfil: {e}")
                return {"error": f"Erro ao carregar perfil: {str(e)}"}
        
        @tool
        def create_educational_content(topic: str, user_level: str, learning_style: str) -> str:
            """Cria conteúdo educacional personalizado baseado no tópico e perfil do usuário"""
            try:
                prompt = f"""
                Crie conteúdo educacional sobre: {topic}
                Nível do usuário: {user_level}
                Estilo de aprendizagem: {learning_style}
                
                O conteúdo deve ser:
                - Adequado ao nível educacional
                - Adaptado ao estilo de aprendizagem
                - Didático e envolvente
                - Com exemplos práticos
                - Estruturado de forma clara
                """
                
                response = self.llm.invoke(prompt)
                content = response.content
                
                logger.info(f"📚 Conteúdo educacional criado para: {topic}")
                return content
                
            except Exception as e:
                logger.error(f"Erro ao criar conteúdo: {e}")
                return f"Erro ao criar conteúdo: {str(e)}"
        
        @tool
        def reflect_on_interaction(interaction_summary: str, config: RunnableConfig) -> str:
            """Reflete sobre a interação atual e identifica melhorias"""
            try:
                user_id = config["configurable"].get("user_id")
                
                prompt = f"""
                Analise esta interação educacional e identifique:
                1. O que funcionou bem
                2. O que poderia ser melhorado
                3. Insights sobre o estilo de aprendizagem do usuário
                4. Sugestões para futuras interações
                
                Interação: {interaction_summary}
                
                Forneça uma reflexão construtiva e acionável.
                """
                
                response = self.llm.invoke(prompt)
                reflection = response.content
                
                # Save reflection as memory
                if user_id:
                    self.supabase.table("agent_memories").insert({
                        "user_id": user_id,
                        "memory_type": "reflection",
                        "content": reflection,
                        "created_at": datetime.now().isoformat()
                    }).execute()
                
                logger.info(f"🤔 Reflexão criada para usuário {user_id}")
                return reflection
                
            except Exception as e:
                logger.error(f"Erro na reflexão: {e}")
                return f"Erro na reflexão: {str(e)}"
        
        @tool
        def generate_flashcards(topic: str, count: int = 5, difficulty: str = "medium") -> str:
            """
            Gera flashcards educacionais sobre um tópico específico

            Args:
                topic: Tópico ou assunto para os flashcards
                count: Número de flashcards a gerar (padrão: 5)
                difficulty: Nível de dificuldade (easy, medium, hard)

            Returns:
                JSON com os flashcards gerados
            """
            try:
                prompt = f"""
                Crie {count} flashcards educacionais sobre "{topic}" com nível de dificuldade {difficulty}.

                Formato de resposta (JSON):
                {{
                    "flashcards": [
                        {{
                            "id": 1,
                            "front": "Pergunta ou conceito",
                            "back": "Resposta ou explicação",
                            "difficulty": "{difficulty}",
                            "tags": ["tag1", "tag2"]
                        }}
                    ]
                }}

                Diretrizes:
                - Perguntas claras e objetivas
                - Respostas completas mas concisas
                - Adequado ao nível de dificuldade
                - Tags relevantes para organização
                """

                response = self.llm.invoke([{"role": "user", "content": prompt}])
                content = response.content

                logger.info(f"📚 Flashcards gerados para: {topic}")
                return content

            except Exception as e:
                logger.error(f"Erro ao gerar flashcards: {e}")
                return f"Erro ao gerar flashcards: {str(e)}"

        @tool
        def generate_quiz(topic: str, question_count: int = 5, difficulty: str = "medium") -> str:
            """
            Gera um quiz educacional sobre um tópico específico

            Args:
                topic: Tópico ou assunto para o quiz
                question_count: Número de questões (padrão: 5)
                difficulty: Nível de dificuldade (easy, medium, hard)

            Returns:
                JSON com o quiz gerado
            """
            try:
                prompt = f"""
                Crie um quiz educacional sobre "{topic}" com {question_count} questões de nível {difficulty}.

                Formato de resposta (JSON):
                {{
                    "quiz": {{
                        "title": "Quiz: {topic}",
                        "description": "Descrição do quiz",
                        "difficulty": "{difficulty}",
                        "questions": [
                            {{
                                "id": 1,
                                "type": "multiple_choice",
                                "question": "Pergunta aqui?",
                                "options": ["A) Opção 1", "B) Opção 2", "C) Opção 3", "D) Opção 4"],
                                "correct_answer": 0,
                                "explanation": "Explicação da resposta correta"
                            }}
                        ]
                    }}
                }}

                Diretrizes:
                - Questões variadas (múltipla escolha, verdadeiro/falso)
                - 4 opções para múltipla escolha
                - Explicações claras para as respostas
                - Adequado ao nível de dificuldade
                """

                response = self.llm.invoke([{"role": "user", "content": prompt}])
                content = response.content

                logger.info(f"📝 Quiz gerado para: {topic}")
                return content

            except Exception as e:
                logger.error(f"Erro ao gerar quiz: {e}")
                return f"Erro ao gerar quiz: {str(e)}"

        @tool
        def generate_mind_map(topic: str, node_count: int = 7) -> str:
            """
            Gera um mapa mental sobre um tópico específico

            Args:
                topic: Tópico central do mapa mental
                node_count: Número de nós/conceitos (padrão: 7)

            Returns:
                JSON com a estrutura do mapa mental
            """
            try:
                prompt = f"""
                Crie um mapa mental sobre "{topic}" com {node_count} nós principais.

                Formato de resposta (JSON):
                {{
                    "mindMap": {{
                        "title": "{topic}",
                        "centerNode": {{
                            "id": "center",
                            "label": "{topic}",
                            "x": 0,
                            "y": 0
                        }},
                        "nodes": [
                            {{
                                "id": "node1",
                                "label": "Conceito 1",
                                "x": 100,
                                "y": 50,
                                "color": "#FF6B6B"
                            }}
                        ],
                        "connections": [
                            {{
                                "source": "center",
                                "target": "node1"
                            }}
                        ]
                    }}
                }}

                Diretrizes:
                - Conceitos bem distribuídos e organizados
                - Conexões lógicas entre os nós
                - Posições variadas para visualização
                - Cores diferentes para categorias
                """

                response = self.llm.invoke([{"role": "user", "content": prompt}])
                content = response.content

                logger.info(f"🧠 Mapa mental gerado para: {topic}")
                return content

            except Exception as e:
                logger.error(f"Erro ao gerar mapa mental: {e}")
                return f"Erro ao gerar mapa mental: {str(e)}"

        self.tools = [
            save_long_term_memory,
            search_long_term_memories,
            get_user_profile,
            create_educational_content,
            reflect_on_interaction,
            generate_flashcards,
            generate_quiz,
            generate_mind_map
        ]
        
        # Bind tools to LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)
    
    def _build_graph(self):
        """Constrói o grafo do agente com LangGraph"""
        
        def load_context(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
            """Carrega contexto do usuário e memórias relevantes"""
            try:
                user_id = config["configurable"].get("user_id", "")
                thread_id = config["configurable"].get("thread_id", "")

                # Skip if context already loaded
                if state.get("user_profile") is not None:
                    logger.info("🧠 Contexto já carregado, pulando...")
                    return state

                # Load conversation history from database and merge with current messages
                existing_messages = self.get_conversation_history(user_id, thread_id, limit=20)

                # Convert database messages to graph format
                historical_messages = []
                for msg in existing_messages:
                    historical_messages.append({
                        "role": msg["role"],
                        "content": msg["content"],
                        "timestamp": msg["created_at"]
                    })

                # Merge historical messages with current state messages
                current_messages = state.get("messages", [])
                all_messages = historical_messages + current_messages

                # Remove duplicates based on content and timestamp
                unique_messages = []
                seen = set()
                for msg in all_messages:
                    key = (msg.get("role"), msg.get("content"), msg.get("timestamp", ""))
                    if key not in seen:
                        seen.add(key)
                        unique_messages.append(msg)

                logger.info(f"📚 Carregadas {len(existing_messages)} mensagens históricas, {len(unique_messages)} total")

                # Get user profile - try by email first, then by UUID
                try:
                    # First try to get user by email from users table
                    user_response = self.supabase.table("users").select("id").eq("email", user_id).execute()
                    if user_response.data:
                        actual_user_id = user_response.data[0]["id"]
                        profile_response = self.supabase.table("user_profiles").select("*").eq("user_id", actual_user_id).execute()
                        user_profile = profile_response.data[0] if profile_response.data else None
                    else:
                        # Try direct UUID lookup
                        profile_response = self.supabase.table("user_profiles").select("*").eq("user_id", user_id).execute()
                        user_profile = profile_response.data[0] if profile_response.data else None
                except Exception as e:
                    logger.warning(f"Erro ao carregar perfil: {e}")
                    user_profile = None

                # Get recent conversation context
                last_message = unique_messages[-1] if unique_messages else ""
                query = last_message.get("content", "") if isinstance(last_message, dict) else str(last_message)

                # Search relevant long-term memories
                if query:
                    try:
                        docs = self.memory_store.similarity_search(
                            query,
                            k=3,
                            filter=lambda doc: doc.metadata.get("user_id") == user_id
                        )
                        long_term_memories = [doc.page_content for doc in docs]
                    except Exception as e:
                        logger.warning(f"Erro ao buscar memórias: {e}")
                        long_term_memories = []
                else:
                    long_term_memories = []

                logger.info(f"🧠 Contexto carregado - Perfil: {'✓' if user_profile else '✗'}, Memórias: {len(long_term_memories)}")

                return {
                    **state,
                    "messages": unique_messages,
                    "user_id": user_id,
                    "thread_id": thread_id,
                    "user_profile": user_profile,
                    "long_term_memories": long_term_memories
                }

            except Exception as e:
                logger.error(f"Erro ao carregar contexto: {e}")
                return state
        
        def agent_node(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
            """Nó principal do agente que processa mensagens"""
            try:
                # Build system prompt with context
                system_prompt = self._build_system_prompt(state)

                # Prepare messages
                messages = [SystemMessage(content=system_prompt)]

                # Add conversation history
                for msg in state.get("messages", []):
                    if isinstance(msg, dict):
                        if msg.get("role") == "user":
                            messages.append(HumanMessage(content=msg.get("content", "")))
                        elif msg.get("role") == "assistant":
                            messages.append(AIMessage(content=msg.get("content", "")))

                # Get response from LLM
                response = self.llm_with_tools.invoke(messages)

                # Convert response to proper format
                response_dict = {
                    "role": "assistant",
                    "content": response.content
                }

                # Add tool calls if present
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    response_dict["tool_calls"] = response.tool_calls

                # Update state
                new_messages = state.get("messages", [])
                new_messages.append(response_dict)

                logger.info(f"🤖 Resposta gerada - Tools: {len(getattr(response, 'tool_calls', []))}")

                return {
                    **state,
                    "messages": new_messages
                }

            except Exception as e:
                logger.error(f"Erro no agente: {e}")
                error_msg = {
                    "role": "assistant",
                    "content": f"Desculpe, ocorreu um erro: {str(e)}"
                }
                return {
                    **state,
                    "messages": state.get("messages", []) + [error_msg]
                }
        
        def should_continue(state: Dict[str, Any]) -> Literal["tools", "end"]:
            """Decide se deve usar ferramentas ou finalizar"""
            messages = state.get("messages", [])
            if not messages:
                return "end"

            # Limit tool iterations to prevent infinite loops
            tool_iterations = state.get("tool_iterations", 0)
            if tool_iterations >= 3:
                logger.info("🛑 Limite de iterações de ferramentas atingido")
                return "end"

            last_message = messages[-1]
            tool_calls = last_message.get("tool_calls", [])

            if tool_calls and len(tool_calls) > 0:
                logger.info(f"🔧 Executando {len(tool_calls)} ferramentas (iteração {tool_iterations + 1})")
                return "tools"
            else:
                return "end"
        
        def tools_node(state: Dict[str, Any], config: RunnableConfig) -> Dict[str, Any]:
            """Executa ferramentas quando necessário"""
            try:
                messages = state.get("messages", [])
                if not messages:
                    return state

                last_message = messages[-1]
                tool_calls = last_message.get("tool_calls", [])

                if not tool_calls:
                    return state

                # Execute tools
                tool_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name", "")
                    tool_args = tool_call.get("args", {})

                    # Find and execute tool
                    for tool in self.tools:
                        if tool.name == tool_name:
                            try:
                                result = tool.invoke(tool_args, config)
                                tool_results.append(f"Tool {tool_name}: {result}")
                            except Exception as e:
                                tool_results.append(f"Tool {tool_name} error: {str(e)}")
                            break

                # Add tool results as a new message
                if tool_results:
                    new_messages = messages.copy()
                    new_messages.append({
                        "role": "system",
                        "content": f"Resultados das ferramentas: {'; '.join(tool_results)}"
                    })
                    # Increment tool iterations counter
                    tool_iterations = state.get("tool_iterations", 0) + 1
                    return {**state, "messages": new_messages, "tool_iterations": tool_iterations}

                return state

            except Exception as e:
                logger.error(f"Erro nas ferramentas: {e}")
                return state

        # Build the graph
        workflow = StateGraph(dict)

        # Add nodes
        workflow.add_node("load_context", load_context)
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tools_node)

        # Add edges
        workflow.add_edge(START, "load_context")
        workflow.add_edge("load_context", "agent")
        workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
        workflow.add_edge("tools", "agent")

        # Compile graph with memory saver
        self.graph = workflow.compile(checkpointer=self.memory_saver)
        
        logger.info("🔗 Grafo do agente construído com sucesso")
    
    def _build_system_prompt(self, state: Dict[str, Any]) -> str:
        """Constrói o prompt do sistema baseado no contexto"""
        user_profile = state.get("user_profile", {})
        long_term_memories = state.get("long_term_memories", [])
        
        # Base prompt
        prompt = """Você é Lia, uma assistente de IA educacional avançada e personalizada.

SUAS CARACTERÍSTICAS:
- Especialista em educação personalizada
- Adapta explicações ao nível e estilo do usuário
- Usa memória para personalizar interações
- Cria conteúdo educacional envolvente
- Reflete sobre interações para melhorar

DIRETRIZES:
1. Sempre considere o perfil do usuário ao responder
2. Use memórias anteriores para personalizar respostas
3. Crie conteúdo educacional quando apropriado
4. Salve informações importantes como memórias
5. Seja didática, clara e envolvente
6. Adapte linguagem ao nível educacional
7. Use exemplos práticos e relevantes
8. Encoraje o aprendizado ativo"""

        # Add user profile context
        if user_profile:
            prompt += f"""

PERFIL DO USUÁRIO:
- Nome: {user_profile.get('name', 'Não informado')}
- Nível: {user_profile.get('education_level', 'Não informado')}
- Estilo: {user_profile.get('learning_style', 'Não informado')}
- Matérias favoritas: {', '.join(user_profile.get('favorite_subjects', []))}
- Objetivos: {', '.join(user_profile.get('study_goals', []))}
- Dificuldades: {', '.join(user_profile.get('difficulty_topics', []))}
- Explicações: {user_profile.get('preferred_explanation_style', 'Não informado')}"""

        # Add long-term memories
        if long_term_memories:
            prompt += f"""

MEMÓRIAS RELEVANTES:
{chr(10).join(f"- {memory}" for memory in long_term_memories[:5])}"""

        prompt += """

Responda de forma personalizada, educativa e envolvente!"""

        return prompt

    async def chat(self, message: str, user_id: str, thread_id: str = None) -> Dict[str, Any]:
        """
        Processa uma mensagem do usuário e retorna a resposta da Lia

        Args:
            message: Mensagem do usuário
            user_id: ID do usuário
            thread_id: ID da thread (opcional, será gerado se não fornecido)

        Returns:
            Dict com a resposta e metadados
        """
        try:
            # Generate thread_id if not provided
            if not thread_id:
                thread_id = str(uuid.uuid4())

            logger.info(f"💬 Processando mensagem de {user_id} na thread {thread_id}")

            # Load conversation history from database
            existing_messages = self.get_conversation_history(user_id, thread_id, limit=20)

            # Convert database messages to graph format
            all_messages = []
            for msg in existing_messages:
                all_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                    "timestamp": msg["created_at"]
                })

            # Add the new user message
            all_messages.append({
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat()
            })

            logger.info(f"📚 Carregadas {len(existing_messages)} mensagens anteriores da thread {thread_id}")

            # Prepare config with thread_id for checkpointer
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": user_id
                }
            }

            # Prepare input with all messages
            input_data = {
                "messages": all_messages,
                "user_id": user_id,
                "thread_id": thread_id
            }

            # Run the graph
            result = await self.graph.ainvoke(input_data, config)

            # Extract response
            messages = result.get("messages", [])
            if not messages:
                raise Exception("Nenhuma mensagem retornada pelo agente")

            # Get the last assistant message
            assistant_messages = [msg for msg in messages if msg.get("role") == "assistant"]
            if not assistant_messages:
                # If no assistant message, get the last message
                last_message = messages[-1]
                response_content = last_message.get("content", "Desculpe, não consegui processar sua mensagem.")
            else:
                last_assistant_message = assistant_messages[-1]
                response_content = last_assistant_message.get("content", "Desculpe, não consegui processar sua mensagem.")

            # Save conversation to Supabase
            await self._save_conversation(user_id, thread_id, message, response_content)

            logger.info(f"✅ Resposta gerada com sucesso para {user_id}")

            return {
                "response": response_content,
                "thread_id": thread_id,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
                "success": True
            }

        except Exception as e:
            logger.error(f"Erro no chat: {e}")
            import traceback
            traceback.print_exc()
            return {
                "response": "Desculpe, ocorreu um erro interno. Tente novamente.",
                "error": str(e),
                "success": False
            }

    async def _save_conversation(self, user_id: str, thread_id: str, user_message: str, ai_response: str):
        """Salva a conversa no Supabase"""
        try:
            # Save to conversations table (for LangGraph agent)
            self.supabase.table("conversations").insert({
                "user_id": user_id,
                "thread_id": thread_id,
                "role": "user",
                "content": user_message,
                "created_at": datetime.now().isoformat()
            }).execute()

            self.supabase.table("conversations").insert({
                "user_id": user_id,
                "thread_id": thread_id,
                "role": "assistant",
                "content": ai_response,
                "created_at": datetime.now().isoformat()
            }).execute()

            # Also save to ai_conversations and ai_messages tables (for frontend compatibility)
            try:
                # Check if ai_conversation exists, if not create it
                existing_conv = self.supabase.table("ai_conversations")\
                    .select("id")\
                    .eq("user_id", user_id)\
                    .eq("thread_id", thread_id)\
                    .execute()

                conversation_id = None
                if not existing_conv.data:
                    # Create new ai_conversation
                    new_conv = self.supabase.table("ai_conversations").insert({
                        "id": thread_id,  # Use thread_id as conversation id
                        "user_id": user_id,
                        "thread_id": thread_id,
                        "title": "Nova Conversa",
                        "assistant_id": "asst_XhJJPU4A7l0neFMxnZImtvMk",
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }).execute()
                    conversation_id = thread_id
                else:
                    conversation_id = existing_conv.data[0]["id"]
                    # Update the updated_at timestamp
                    self.supabase.table("ai_conversations")\
                        .update({"updated_at": datetime.now().isoformat()})\
                        .eq("id", conversation_id)\
                        .execute()

                # Save messages to ai_messages table
                self.supabase.table("ai_messages").insert({
                    "conversation_id": conversation_id,
                    "role": "user",
                    "content": user_message,
                    "created_at": datetime.now().isoformat()
                }).execute()

                self.supabase.table("ai_messages").insert({
                    "conversation_id": conversation_id,
                    "role": "assistant",
                    "content": ai_response,
                    "created_at": datetime.now().isoformat()
                }).execute()

            except Exception as frontend_error:
                logger.warning(f"Erro ao salvar para frontend: {frontend_error}")

            logger.info(f"💾 Conversa salva - Thread: {thread_id}")

        except Exception as e:
            logger.error(f"Erro ao salvar conversa: {e}")

    def get_conversation_history(self, user_id: str, thread_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Obtém o histórico de uma conversa"""
        try:
            response = self.supabase.table("conversations")\
                .select("*")\
                .eq("user_id", user_id)\
                .eq("thread_id", thread_id)\
                .order("created_at", desc=False)\
                .limit(limit)\
                .execute()

            return response.data

        except Exception as e:
            logger.error(f"Erro ao obter histórico: {e}")
            return []

    def get_user_threads(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Obtém as threads de conversa de um usuário"""
        try:
            response = self.supabase.table("conversations")\
                .select("thread_id, created_at")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()

            # Group by thread_id and get the latest message for each
            threads = {}
            for msg in response.data:
                thread_id = msg["thread_id"]
                if thread_id not in threads:
                    threads[thread_id] = {
                        "thread_id": thread_id,
                        "last_activity": msg["created_at"],
                        "message_count": 1
                    }
                else:
                    threads[thread_id]["message_count"] += 1

            return list(threads.values())

        except Exception as e:
            logger.error(f"Erro ao obter threads: {e}")
            return []

    def create_educational_plan(self, user_id: str, subject: str, goals: List[str]) -> Dict[str, Any]:
        """Cria um plano de estudos personalizado"""
        try:
            # Get user profile
            profile_response = self.supabase.table("user_profiles").select("*").eq("user_id", user_id).execute()
            user_profile = profile_response.data[0] if profile_response.data else {}

            # Create personalized study plan
            prompt = f"""
            Crie um plano de estudos personalizado para:

            USUÁRIO:
            - Nível: {user_profile.get('education_level', 'Não informado')}
            - Estilo: {user_profile.get('learning_style', 'Não informado')}
            - Matérias favoritas: {', '.join(user_profile.get('favorite_subjects', []))}
            - Dificuldades: {', '.join(user_profile.get('difficulty_topics', []))}

            MATÉRIA: {subject}
            OBJETIVOS: {', '.join(goals)}

            O plano deve incluir:
            1. Cronograma semanal
            2. Tópicos por ordem de prioridade
            3. Recursos recomendados
            4. Estratégias de estudo
            5. Marcos de progresso
            6. Dicas personalizadas

            Formate como JSON estruturado.
            """

            response = self.llm.invoke(prompt)
            plan_content = response.content

            # Save plan to database
            plan_data = {
                "user_id": user_id,
                "subject": subject,
                "goals": goals,
                "content": plan_content,
                "created_at": datetime.now().isoformat()
            }

            self.supabase.table("study_plans").insert(plan_data).execute()

            logger.info(f"📋 Plano de estudos criado para {user_id} - {subject}")

            return {
                "success": True,
                "plan": plan_content,
                "subject": subject,
                "goals": goals
            }

        except Exception as e:
            logger.error(f"Erro ao criar plano: {e}")
            return {
                "success": False,
                "error": str(e)
            }
