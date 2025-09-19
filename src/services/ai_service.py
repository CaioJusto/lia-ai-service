from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from openai import OpenAI

from ..agents.lia_agent import LiaEducationalAgent
from ..agents.multi_agent_flashcards import MultiAgentFlashcardGenerator

from ..models.requests import (
    ChatMessage,
    FlashcardRequest,
    FlashcardsFromTextRequest,
    MindMapRequest,
    NoteRequest,
    QuizRequest,
    StudyConversationRequest,
    StudyPlanRequest,
)
from ..models.responses import ChatResponse
from .database_service import (
    conversation_cache,
    ensure_conversation_exists,
    env_requirements,
    get_conversation_history,
    get_supabase_client,
    get_user_profile,
    save_message_to_db,
)
from .openai_utils import (
    create_chat_completion,
    is_openai_configured,
    sync_openai_client,
)

load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-test-key-placeholder")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

lia_agent: Optional[LiaEducationalAgent] = None
multi_agent_generator: Optional[MultiAgentFlashcardGenerator] = None

progress_store: Dict[str, "ProgressTracker"] = {}


def _extract_json_array(raw_text: str) -> Optional[List[Any]]:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("[")
        end = raw_text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw_text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


class ProgressTracker:
    """Acompanhamento de tarefas paralelas de geração."""

    def __init__(self, operation_id: str, total_agents: int):
        self.operation_id = operation_id
        self.total_agents = max(1, total_agents)
        self.start_time = datetime.now()
        self.completed_agents = 0
        self.agents_status: Dict[int, Dict[str, Any]] = {}
        self._ensure_agent_slots(self.total_agents)
        progress_store[operation_id] = self

    def _ensure_agent_slots(self, total_agents: int) -> None:
        for i in range(1, total_agents + 1):
            if i not in self.agents_status:
                self.agents_status[i] = {
                    "status": "waiting",
                    "subtopic": "",
                    "progress": 0,
                    "completed_at": None,
                }

    def set_total_agents(self, total_agents: int) -> None:
        if total_agents <= 0:
            return
        if total_agents != self.total_agents:
            self.total_agents = total_agents
            self._ensure_agent_slots(total_agents)

    def update_agent_status(
        self, agent_id: int, status: str, subtopic: str = "", progress: int = 0
    ) -> None:
        if agent_id not in self.agents_status:
            self._ensure_agent_slots(agent_id)

        previous_status = self.agents_status[agent_id]["status"]

        self.agents_status[agent_id].update(
            {
                "status": status,
                "subtopic": subtopic,
                "progress": progress,
                "completed_at": datetime.now()
                if status in {"completed", "error"}
                else None,
            }
        )
        if (
            status in {"completed", "error"}
            and previous_status not in {"completed", "error"}
        ):
            self.completed_agents = min(self.total_agents, self.completed_agents + 1)

    def get_progress_data(self) -> Dict[str, Any]:
        elapsed_time = (datetime.now() - self.start_time).total_seconds()
        if self.completed_agents:
            avg_time = elapsed_time / self.completed_agents
            remaining_agents = self.total_agents - self.completed_agents
            estimated_remaining = avg_time * remaining_agents
        else:
            estimated_remaining = None
        return {
            "operation_id": self.operation_id,
            "total_agents": self.total_agents,
            "completed_agents": self.completed_agents,
            "progress_percentage": (self.completed_agents / self.total_agents) * 100,
            "agents_status": self.agents_status,
            "elapsed_time": elapsed_time,
            "estimated_remaining": estimated_remaining,
            "status": "completed"
            if self.completed_agents == self.total_agents
            else "in_progress",
        }


def get_openai_client() -> Optional[OpenAI]:
    return sync_openai_client()


def get_lia_agent() -> Optional[LiaEducationalAgent]:
    global lia_agent
    if (
        lia_agent is None
        and OPENAI_API_KEY
        and OPENAI_API_KEY != "sk-test-key-placeholder"
        and SUPABASE_URL
        and SUPABASE_KEY
    ):
        try:
            lia_agent = LiaEducationalAgent(
                openai_api_key=OPENAI_API_KEY,
                supabase_url=SUPABASE_URL,
                supabase_key=SUPABASE_KEY,
            )
            logger.info("🤖 Lia Agent initialized successfully")
        except Exception as exc:
            logger.error("❌ Failed to initialize Lia Agent: %s", exc)
    return lia_agent


def get_multi_agent_generator() -> Optional[MultiAgentFlashcardGenerator]:
    global multi_agent_generator
    if multi_agent_generator is None and OPENAI_API_KEY:
        try:
            multi_agent_generator = MultiAgentFlashcardGenerator(
                openai_api_key=OPENAI_API_KEY, max_agents=4
            )
            logger.info("🚀 Multi-Agent Flashcard Generator initialized successfully")
        except Exception as exc:
            logger.error("❌ Failed to initialize Multi-Agent Generator: %s", exc)
    return multi_agent_generator


def create_personalized_system_prompt(user_profile: Optional[Dict[str, Any]] = None) -> str:
    base_prompt = """
    Você é a Lia, uma assistente de estudos inteligente e amigável! 🎓

    🎯 **Sua personalidade:**
    - Entusiasta e motivadora
    - Paciente e compreensiva
    - Usa emojis naturalmente
    - Linguagem jovem e descontraída
    - Sempre positiva e encorajadora

    📚 **Suas especialidades:**
    - Explicar conceitos de forma simples
    - Criar resumos e mapas mentais
    - Sugerir técnicas de estudo
    - Ajudar com flashcards e quizzes
    - Motivar nos estudos
    - Resolver problemas e dúvidas

    💬 **Seu estilo:**
    - Respostas claras e objetivas
    - Usa exemplos práticos
    - Pergunta se entendeu
    - Oferece ajuda adicional
    - Celebra conquistas

    ⚠️ Regras de chat e concisão:
    - Responda de forma curta e direta (até ~120–180 palavras ou 3–6 frases)
    - Prefira parágrafos curtos e listas com bullets quando fizer sentido
    - Evite "paredes de texto"; se o assunto for amplo, peça esclarecimentos antes de expandir
    - Termine com 1 pergunta curta para continuar a conversa quando apropriado
    - Se o usuário pedir mais detalhes, aí sim aprofunde
    """

    if not user_profile:
        return base_prompt + "\nResponda sempre em português brasileiro de forma amigável e educativa!"

    personalization = "\n\n🎯 **INFORMAÇÕES SOBRE O USUÁRIO:**\n"

    if user_profile.get("name"):
        personalization += f"- Nome: {user_profile['name']} (use o nome nas conversas!)\n"

    if user_profile.get("education_level"):
        level_map = {
            "ensino_medio": "ensino médio",
            "superior": "ensino superior",
            "pos_graduacao": "pós-graduação",
        }
        level = level_map.get(user_profile["education_level"], user_profile["education_level"])
        personalization += f"- Nível de ensino: {level}\n"

    if user_profile.get("favorite_subjects"):
        subjects = ", ".join(user_profile["favorite_subjects"])
        personalization += f"- Matérias favoritas: {subjects}\n"

    if user_profile.get("learning_style"):
        style_map = {
            "visual": "visual (prefere gráficos, diagramas, mapas mentais)",
            "auditivo": "auditivo (prefere explicações faladas, discussões)",
            "cinestesico": "cinestésico (prefere atividades práticas, exemplos concretos)",
            "leitura": "leitura/escrita (prefere textos, resumos, anotações)",
        }
        style = style_map.get(user_profile["learning_style"], user_profile["learning_style"])
        personalization += f"- Estilo de aprendizagem: {style}\n"

    if user_profile.get("study_goals"):
        goals = ", ".join(user_profile["study_goals"])
        personalization += f"- Objetivos de estudo: {goals}\n"

    if user_profile.get("difficulty_topics"):
        topics = ", ".join(user_profile["difficulty_topics"])
        personalization += f"- Tópicos com dificuldade: {topics} (seja extra paciente com estes!)\n"

    if user_profile.get("preferred_explanation_style"):
        style_map = {
            "friendly": "amigável e descontraído",
            "formal": "mais formal e acadêmico",
            "casual": "bem casual e informal",
        }
        style = style_map.get(user_profile.get("preferred_explanation_style"), "amigável")
        personalization += f"- Estilo de explicação preferido: {style}\n"

    personalization += "\n💡 **ADAPTE SUAS RESPOSTAS:**\n"
    personalization += "- Use o nome do usuário quando apropriado\n"
    personalization += "- Adapte o nível de complexidade ao nível de ensino\n"
    personalization += "- Foque nas matérias favoritas quando possível\n"
    personalization += "- Adapte ao estilo de aprendizagem (mais visual, auditivo, etc.)\n"
    personalization += "- Seja especialmente encorajador com tópicos difíceis\n"
    personalization += "- Use o estilo de explicação preferido\n"

    return base_prompt + personalization + "\nResponda sempre em português brasileiro!"


async def chat_with_lia(message: str, conversation_id: str, user_id: str) -> str:
    user_profile = await get_user_profile(user_id)
    system_prompt = create_personalized_system_prompt(user_profile)

    await ensure_conversation_exists(conversation_id, user_id)
    conversation_history = await get_conversation_history(conversation_id, user_id)

    user_message_id = f"user_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
    await save_message_to_db(conversation_id, user_id, "user", message, user_message_id)

    conversation_history.append({"role": "user", "content": message})

    messages = [{"role": "system", "content": system_prompt}]
    recent_history = conversation_history[-10:]
    messages.extend(recent_history)

    try:
        if is_openai_configured():
            response = await create_chat_completion(
                messages,
                temperature=0.6,
                max_tokens=350,
                frequency_penalty=0.2,
            )
            lia_response = response.choices[0].message.content
        else:
            lia_response = (
                "Ola! Sou a Lia, sua assistente de estudos! "
                f"Voce perguntou: '{message}'. Infelizmente, nao tenho acesso a API da OpenAI no momento, "
                "mas estou aqui para ajudar! Configure a OPENAI_API_KEY para ter acesso "
                "completo as minhas funcionalidades de IA."
            )

        lia_message_id = f"lia_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        await save_message_to_db(conversation_id, user_id, "assistant", lia_response, lia_message_id)

        cache_key = f"{user_id}_{conversation_id}"
        if cache_key not in conversation_cache:
            conversation_cache[cache_key] = []
        conversation_cache[cache_key].append({"role": "user", "content": message})
        conversation_cache[cache_key].append({"role": "assistant", "content": lia_response})
        if len(conversation_cache[cache_key]) > 20:
            conversation_cache[cache_key] = conversation_cache[cache_key][-20:]

        return lia_response
    except Exception as exc:  # pragma: no cover - defensive runtime protection
        logger.exception("Error in chat_with_lia: %s", exc)
        return (
            "Desculpe, tive um problema técnico ao responder agora. "
            "Tente novamente em instantes, por favor."
        )


async def generate_completion(
    messages: List[Dict[str, str]], user_id: str = ""
) -> Dict[str, Any]:
    if not messages:
        return {"success": False, "error": "Nenhuma mensagem fornecida"}

    agent = get_lia_agent()
    thread_id = f"completion_{uuid.uuid4().hex[:8]}"
    user_identifier = user_id or "anonymous"

    system_sections = [m.get("content", "") for m in messages if m.get("role") == "system"]
    dialogue_lines: List[str] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if not content:
            continue
        if role == "assistant":
            dialogue_lines.append(f"Assistente: {content}")
        elif role == "user":
            dialogue_lines.append(f"Usuario: {content}")

    combined_prompt_parts: List[str] = []
    if system_sections:
        combined_prompt_parts.append("\n".join(system_sections))
    if dialogue_lines:
        combined_prompt_parts.append("\n".join(dialogue_lines))

    final_prompt = "\n\n".join(part for part in combined_prompt_parts if part).strip()
    if not final_prompt:
        final_prompt = messages[-1].get("content", "")

    try:
        if agent:
            result = await agent.chat(
                final_prompt,
                user_identifier,
                thread_id,
            )
            if result.get("success"):
                return {"success": True, "content": result.get("response", "")}

        if is_openai_configured():
            completion = await create_chat_completion(
                [
                    {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                    for msg in messages
                ],
                temperature=0.6,
                max_tokens=500,
            )
            content = completion.choices[0].message.content
            return {"success": True, "content": content}

        return {
            "success": True,
            "content": "Nao foi possivel acionar o agente inteligente. Verifique as configuracoes de IA.",
        }
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Erro ao gerar completion: %s", exc)
        return {
            "success": False,
            "error": "Não consegui gerar uma resposta agora. Por favor, tente novamente em instantes.",
        }


async def start_flashcard_generation(request: FlashcardRequest) -> Dict[str, Any]:
    generator = get_multi_agent_generator()
    operation_id = f"flashcards_{uuid.uuid4().hex[:8]}"

    estimated_agents = 1
    if generator:
        estimated_agents = generator.estimate_batches(request.count)

    tracker = ProgressTracker(operation_id, estimated_agents)

    def handle_progress(
        agent_id: int,
        status: str,
        subtopic: str,
        progress: int,
        total_agents: Optional[int] = None,
    ) -> None:
        if total_agents is not None:
            tracker.set_total_agents(total_agents)
        tracker.update_agent_status(agent_id, status, subtopic, progress)

    def finalize_agents(status: str, progress: int = 100) -> None:
        for agent_index in range(1, tracker.total_agents + 1):
            tracker.update_agent_status(agent_index, status, request.topic, progress)

    if not generator:
        handle_progress(1, "processing", request.topic, 10, 1)
        result = await generate_flashcards_single_agent(request)
        final_status = "completed" if result.get("success") else "error"
        finalize_agents(final_status)
        result.setdefault("operation_id", operation_id)
        return result

    try:
        result = await generator.generate_flashcards_parallel(
            topic=request.topic,
            count=request.count,
            difficulty=request.difficulty,
            subject=request.subject,
            user_id=request.user_id,
            progress_callback=handle_progress,
        )

        if result.get("success"):
            return {
                "success": True,
                "flashcards": result.get("flashcards", []),
                "topic": request.topic,
                "subject": request.subject,
                "count": len(result.get("flashcards", [])),
                "difficulty": request.difficulty,
                "processing_time": result.get("processing_time", 0),
                "agents_used": result.get("agents_used", 1),
                "operation_id": operation_id,
            }

        logger.error(
            "❌ Multi-agent LangGraph generation failed: %s",
            result.get("error", "Unknown error"),
        )
        logger.info("🔄 Falling back to single LangGraph agent generation...")
        finalize_agents("processing", 10)
        fallback = await generate_flashcards_single_agent(request)
        final_status = "completed" if fallback.get("success") else "error"
        finalize_agents(final_status)
        fallback.setdefault("operation_id", operation_id)
        return fallback
    except Exception as exc:
        logger.error("Erro ao gerar flashcards: %s", exc)
        finalize_agents("error")
        return {
            "success": False,
            "error": "Falha ao gerar flashcards no momento. Tente novamente em instantes.",
            "operation_id": operation_id,
        }


async def generate_flashcards_single_agent(request: FlashcardRequest) -> Dict[str, Any]:
    agent = get_lia_agent()
    if not agent:
        return {"success": False, "error": "LangGraph agent not available"}

    logger.info(
        "🔄 Using single LangGraph agent for %s flashcards about '%s'",
        request.count,
        request.topic,
    )

    user_profile = await get_user_profile(request.user_id)
    profile_context = ""
    if user_profile:
        learning_style = user_profile.get("learning_style", "visual")
        interests = user_profile.get("interests", [])
        academic_level = user_profile.get("academic_level", "intermediário")
        profile_context = f"""
            Contexto do usuário:
            - Estilo de aprendizagem: {learning_style}
            - Nível acadêmico: {academic_level}
            - Interesses: {', '.join(interests) if interests else 'não especificado'}

            Adapte os flashcards ao perfil do usuário, usando exemplos e linguagem apropriados.
        """

    prompt = f"""Gere {request.count} flashcards sobre '{request.topic}' na matéria de {request.subject} com dificuldade {request.difficulty}.

    {profile_context}

    IMPORTANTE: Os flashcards devem ser específicos da matéria {request.subject} e abordar o tópico '{request.topic}' de forma educativa e clara.

    Use a ferramenta generate_flashcards para criar flashcards personalizados e educativos."""

    thread_id = str(uuid.uuid4())
    result = await agent.chat(prompt, request.user_id, thread_id)

    if result.get("success"):
        return {
            "success": True,
            "flashcards": result.get("response"),
            "topic": request.topic,
            "subject": request.subject,
            "count": request.count,
            "difficulty": request.difficulty,
            "generation_method": "single-agent",
        }
    return {"success": False, "error": result.get("error", "Erro desconhecido")}


async def generate_flashcards_from_text(
    request: FlashcardsFromTextRequest,
) -> Dict[str, Any]:
    agent = get_lia_agent()
    if not agent:
        return {"success": False, "error": "LangGraph agent not available"}

    prompt = (
        f"Analise o texto abaixo e gere {request.count} flashcards educativos com dificuldade {request.difficulty}.\n"
        "Cada flashcard deve conter os campos 'question' e 'answer'.\n"
        "Retorne o resultado em formato JSON (array de objetos).\n\n"
        f"Texto base:\n{request.text}"
    )

    try:
        result = await agent.chat(
            prompt,
            request.user_id or "flashcards_text",
            f"flashcards_text_{uuid.uuid4().hex[:8]}",
        )
        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Falha ao gerar flashcards"),
            }

        raw_response = result.get("response", "")
        parsed = _extract_json_array(raw_response)
        if not parsed:
            logger.warning("Nao foi possivel extrair JSON dos flashcards gerados")
            return {
                "success": True,
                "flashcards": [],
                "raw_response": raw_response,
                "subject": request.subject,
            }

        return {
            "success": True,
            "flashcards": parsed,
            "subject": request.subject,
            "count": len(parsed),
            "difficulty": request.difficulty,
            "generation_method": "langgraph-text",
        }
    except Exception as exc:
        logger.exception("Erro ao gerar flashcards a partir de texto: %s", exc)
        return {
            "success": False,
            "error": "Não consegui gerar flashcards a partir do texto agora. Tente novamente em instantes.",
        }


async def generate_conversation_title(conversation_id: str, user_id: str) -> str:
    messages = await get_conversation_history(conversation_id, user_id, limit=10)
    if not messages or len(messages) < 2:
        return "Nova Conversa com Lia"

    conversation_text = ""
    for msg in messages[:6]:
        if msg["role"] == "user":
            conversation_text += f"Usuário: {msg['content']}\n"
        elif msg["role"] == "assistant":
            conversation_text += f"Lia: {msg['content'][:200]}...\n"

    if not is_openai_configured():
        text_lower = conversation_text.lower()
        keyword_map = {
            "Matemática": ["matemática", "cálculo", "equação", "número"],
            "Português": ["português", "redação", "texto", "gramática"],
            "História": ["história", "guerra", "período", "século"],
            "Ciências": ["ciência", "física", "química", "biologia"],
            "Inglês": ["inglês", "english", "tradução"],
            "Ferramentas de Estudo": ["flashcard", "quiz", "mapa mental"],
        }
        for title, keywords in keyword_map.items():
            if any(word in text_lower for word in keywords):
                return title
        return "Conversa com Lia"

    title_prompt = f"""Baseado na seguinte conversa entre um estudante e a assistente de estudos Lia, gere um título curto e descritivo (máximo 4 palavras) que capture o tópico principal:

{conversation_text}

Responda apenas com o título, sem aspas ou explicações."""

    try:
        response = await create_chat_completion(
            [{"role": "user", "content": title_prompt}],
            max_tokens=20,
            temperature=0.3,
        )
        title = response.choices[0].message.content.strip()
        if len(title) > 30:
            title = title[:27] + "..."
        return title or "Conversa com Lia"
    except Exception as exc:
        logger.exception("Error generating conversation title: %s", exc)
        return "Conversa com Lia"


async def generate_quiz(request: QuizRequest) -> Dict[str, Any]:
    agent = get_lia_agent()
    if not agent:
        return {"success": False, "error": "Agent not available"}

    generate_quiz_tool = None
    for tool in getattr(agent, "tools", []):
        if hasattr(tool, "name") and tool.name == "generate_quiz":
            generate_quiz_tool = tool
            break

    if not generate_quiz_tool:
        return {"success": False, "error": "Quiz generation tool not found"}

    try:
        quiz_content = generate_quiz_tool.invoke(
            {
                "topic": request.topic,
                "question_count": request.question_count,
                "difficulty": request.difficulty,
            }
        )
        if quiz_content and not str(quiz_content).startswith("Erro"):
            return {
                "success": True,
                "quiz": quiz_content,
                "topic": request.topic,
                "question_count": request.question_count,
                "difficulty": request.difficulty,
            }
        return {"success": False, "error": quiz_content or "Erro ao gerar quiz"}
    except Exception as exc:
        logger.error("Erro ao gerar quiz: %s", exc)
        return {"success": False, "error": str(exc)}


async def generate_notes(request: NoteRequest) -> Dict[str, Any]:
    agent = get_lia_agent()
    if not agent:
        return {"success": False, "error": "Agent not available"}

    user_profile = await get_user_profile(request.user_id)
    user_level = "intermediário"
    learning_style = "visual"

    if user_profile:
        user_level = user_profile.get("academic_level", "intermediário")
        learning_style = user_profile.get("learning_style", "visual")

    create_content_tool = None
    for tool in getattr(agent, "tools", []):
        if hasattr(tool, "name") and tool.name == "create_educational_content":
            create_content_tool = tool
            break

    if not create_content_tool:
        return {
            "success": False,
            "error": "Educational content creation tool not found",
        }

    try:
        content = create_content_tool.invoke(
            {
                "topic": f"{request.type} sobre {request.topic} - {request.length} - {request.complexity}",
                "user_level": user_level,
                "learning_style": learning_style,
            }
        )
        if content and not str(content).startswith("Erro"):
            return {
                "success": True,
                "text": content,
                "topic": request.topic,
                "type": request.type,
                "length": request.length,
                "complexity": request.complexity,
            }
        return {"success": False, "error": content or "Erro ao gerar anotação"}
    except Exception as exc:
        logger.error("Erro ao gerar anotação: %s", exc)
        return {"success": False, "error": str(exc)}


async def generate_mind_map(request: MindMapRequest) -> Dict[str, Any]:
    agent = get_lia_agent()
    if not agent:
        return {"success": False, "error": "Agent not available"}

    prompt = (
        f"Gere um mapa mental sobre '{request.topic}' com {request.node_count} nós. "
        "Use a ferramenta generate_mind_map."
    )

    try:
        result = await agent.chat(
            prompt,
            request.user_id or "",
            f"mindmap_{int(datetime.now().timestamp())}",
        )
        if result.get("success"):
            return {
                "success": True,
                "mind_map": result.get("response"),
                "topic": request.topic,
                "node_count": request.node_count,
            }
        return {"success": False, "error": result.get("error", "Erro desconhecido")}
    except Exception as exc:
        logger.error("Erro ao gerar mapa mental: %s", exc)
        return {"success": False, "error": str(exc)}


async def create_study_plan(request: StudyPlanRequest) -> Dict[str, Any]:
    agent = get_lia_agent()
    missing = [key for key, present in env_requirements().items() if not present]

    if missing:
        friendly = ", ".join(missing)
        return {
            "success": False,
            "error": f"Configuracao ausente: {friendly}. Ajuste as variaveis de ambiente para gerar planos.",
        }

    if not get_supabase_client():
        return {
            "success": False,
            "error": "Conexao com banco indisponivel. Tente novamente em alguns minutos.",
        }

    if not agent:
        return {
            "success": False,
            "error": "Agente avancado indisponivel no momento. Tente novamente em breve.",
        }

    if not hasattr(agent, "create_educational_plan"):
        return {
            "success": False,
            "error": "Ferramenta de plano de estudos nao configurada.",
        }

    goals = ["Melhorar conhecimento", "Preparar para avaliacoes"]

    try:
        result = agent.create_educational_plan(
            user_id=request.user_id,
            subject=request.subject,
            goals=goals,
        )
        return result
    except Exception as exc:
        logger.error("Error creating study plan: %s", exc)
        return {
            "success": False,
            "error": "Nao foi possivel gerar o plano de estudos agora. Tente novamente mais tarde.",
            "details": str(exc),
        }


async def generate_study_conversation(
    request: StudyConversationRequest,
) -> Dict[str, Any]:
    agent = get_lia_agent()
    if not agent:
        return {"success": False, "error": "LangGraph agent not available"}

    prompt = (
        "Com base no flashcard abaixo, gere uma conversa educativa curta entre um estudante e um tutor.\n"
        "Utilize de 4 a 6 interacoes alternando entre estudante e tutor.\n"
        "Retorne em formato JSON (array de objetos com 'role' e 'content').\n\n"
        f"Pergunta: {request.question}\n"
        f"Resposta: {request.answer}"
    )

    try:
        result = await agent.chat(
            prompt,
            request.user_id or "study_conversation",
            f"study_conv_{uuid.uuid4().hex[:8]}",
        )
        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Falha ao gerar conversa de estudo"),
            }

        raw_response = result.get("response", "")
        parsed = _extract_json_array(raw_response)
        if parsed is None:
            return {
                "success": True,
                "conversation": [],
                "raw_response": raw_response,
            }

        return {"success": True, "conversation": parsed}
    except Exception as exc:
        logger.error("Erro ao gerar conversa de estudo: %s", exc)
        return {"success": False, "error": str(exc)}


async def stream_progress(operation_id: str):
    async def generate_progress_events():
        try:
            yield f"data: {json.dumps({'type': 'connected', 'operation_id': operation_id})}\n\n"

            max_wait = 30
            wait_count = 0
            while operation_id not in progress_store and wait_count < max_wait:
                await asyncio.sleep(1)
                wait_count += 1

            if operation_id not in progress_store:
                yield "data: {\"type\": \"timeout\"}\n\n"
                return

            tracker = progress_store[operation_id]
            while tracker and tracker.completed_agents < tracker.total_agents:
                await asyncio.sleep(1)
                yield f"data: {json.dumps(tracker.get_progress_data())}\n\n"

            final_data = tracker.get_progress_data()
            final_data["type"] = "completed"
            yield f"data: {json.dumps(final_data)}\n\n"
            if operation_id in progress_store:
                del progress_store[operation_id]
        except Exception as exc:
            logger.error("Error in progress stream: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    from fastapi.responses import StreamingResponse  # Local import to avoid dependency issues

    return StreamingResponse(
        generate_progress_events(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


async def handle_chat(request: ChatMessage) -> ChatResponse:
    try:
        response_text = await chat_with_lia(
            request.message, request.conversation_id, request.user_id
        )
        return ChatResponse(
            success=True,
            response=response_text,
            conversation_id=request.conversation_id,
            message_id=f"lia_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}",
        )
    except Exception as exc:
        logger.error("Error in chat endpoint: %s", exc)
        return ChatResponse(
            success=False,
            conversation_id=request.conversation_id,
            message_id=f"error_{int(datetime.now().timestamp())}",
            error=str(exc),
        )


async def handle_advanced_chat(request: ChatMessage) -> Dict[str, Any]:
    try:
        agent = get_lia_agent()
        if not agent:
            response_text = await chat_with_lia(
                request.message, request.conversation_id, request.user_id
            )
            return {
                "success": True,
                "response": response_text,
                "conversation_id": request.conversation_id,
                "thread_id": request.conversation_id,
                "agent_used": False,
                "message_id": f"lia_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}",
            }

        result = await agent.chat(
            message=request.message,
            user_id=request.user_id,
            thread_id=request.conversation_id,
        )
        return {
            "success": result.get("success", True),
            "response": result.get("response", ""),
            "conversation_id": request.conversation_id,
            "thread_id": result.get("thread_id", request.conversation_id),
            "agent_used": True,
            "timestamp": result.get("timestamp"),
            "error": result.get("error"),
        }
    except Exception as exc:
        logger.error("Error in advanced chat endpoint: %s", exc)
        return {
            "success": False,
            "conversation_id": request.conversation_id,
            "error": str(exc),
            "agent_used": False,
        }


async def get_user_threads(user_id: str) -> Dict[str, Any]:
    try:
        agent = get_lia_agent()
        if not agent:
            return {"success": False, "error": "Agent not available"}
        threads = agent.get_user_threads(user_id)
        return {"success": True, "threads": threads}
    except Exception as exc:
        logger.error("Error getting threads: %s", exc)
        return {"success": False, "error": str(exc)}


async def get_thread_history(user_id: str, thread_id: str, limit: int = 50) -> Dict[str, Any]:
    try:
        agent = get_lia_agent()
        if not agent:
            return {"success": False, "error": "Agent not available"}
        history = agent.get_conversation_history(user_id, thread_id, limit)
        return {"success": True, "history": history}
    except Exception as exc:
        logger.error("Error getting history: %s", exc)
        return {"success": False, "error": str(exc)}
