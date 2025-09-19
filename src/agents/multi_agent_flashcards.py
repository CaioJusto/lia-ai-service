"""
Multi-Agent Flashcard Generation System
Sistema de geração paralela de flashcards usando múltiplos agentes com
controle de concorrência para suportar alto volume de requisições.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from ..services.openai_utils import create_chat_completion, is_openai_configured

logger = logging.getLogger(__name__)


class FlashcardBatch(BaseModel):
    """Lote de flashcards para um agente específico"""

    batch_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str
    subtopic: str
    count: int
    difficulty: str
    agent_id: int
    flashcards: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "pending"  # pending, processing, completed, error
    error_message: Optional[str] = None


class MultiAgentFlashcardState(BaseModel):
    """Estado do sistema multi-agente"""

    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str
    total_count: int
    difficulty: str
    subject: Optional[str] = None
    user_id: str
    batches: List[FlashcardBatch] = Field(default_factory=list)
    completed_flashcards: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "initializing"  # initializing, processing, completed, error
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    agents_count: int = 1


class FlashcardAgent:
    """Agente individual para geração de flashcards"""

    def __init__(self, agent_id: int) -> None:
        self.agent_id = agent_id
        logger.info("🤖 Agente %s inicializado", agent_id)

    async def generate_flashcards_batch(
        self,
        batch: FlashcardBatch,
        total_batches: int,
        progress_callback: Optional[
            Callable[[int, str, str, int, Optional[int]], None]
        ] = None,
    ) -> FlashcardBatch:
        def emit(status: str, progress: int) -> None:
            if progress_callback:
                progress_callback(
                    self.agent_id,
                    status,
                    batch.subtopic,
                    progress,
                    total_batches,
                )

        emit("processing", 5)

        prompt = f"""
        Você é um especialista em educação. Crie EXATAMENTE {batch.count} flashcards
        sobre "{batch.subtopic}" relacionado ao tópico principal "{batch.topic}" com
        nível de dificuldade {batch.difficulty}.

        INSTRUÇÕES IMPORTANTES:
        1. Cada flashcard deve ter uma pergunta clara e uma resposta completa
        2. Varie os tipos de perguntas (conceitual, aplicação, análise)
        3. Use linguagem adequada ao nível de dificuldade
        4. Seja preciso e educativo

        FORMATO DE RESPOSTA (JSON válido):
        {{
            "flashcards": [
                {{
                    "id": 1,
                    "front": "Pergunta clara e específica",
                    "back": "Resposta completa e educativa",
                    "difficulty": "{batch.difficulty}",
                    "topic": "{batch.topic}",
                    "subtopic": "{batch.subtopic}",
                    "tags": ["tag1", "tag2"]
                }}
            ]
        }}

        Gere EXATAMENTE {batch.count} flashcards agora:
        """

        try:
            response = await create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1200,
            )
            content = response.choices[0].message.content.strip()

            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()

            flashcards_data = json.loads(content)
            flashcards = flashcards_data.get("flashcards", [])

            for index, flashcard in enumerate(flashcards):
                flashcard["id"] = f"{batch.batch_id}_{index + 1}"
                flashcard["batch_id"] = batch.batch_id
                flashcard["agent_id"] = self.agent_id
                flashcard["created_at"] = datetime.now().isoformat()

            batch.flashcards = flashcards
            batch.status = "completed"
            emit("completed", 100)
            logger.info(
                "✅ Agente %s completou lote com %s flashcards",
                self.agent_id,
                len(flashcards),
            )

        except json.JSONDecodeError as exc:
            batch.status = "error"
            batch.error_message = f"Erro ao parsear resposta JSON: {exc}"
            emit("error", 100)
            logger.error("❌ Agente %s - Falha ao parsear JSON: %s", self.agent_id, exc)
        except RuntimeError as exc:
            batch.status = "error"
            batch.error_message = str(exc)
            emit("error", 100)
            logger.error("❌ Agente %s - Cliente OpenAI indisponível: %s", self.agent_id, exc)
        except Exception as exc:  # pragma: no cover - resiliência
            batch.status = "error"
            batch.error_message = str(exc)
            emit("error", 100)
            logger.exception("❌ Agente %s - Erro na geração: %s", self.agent_id, exc)

        return batch


class MultiAgentFlashcardGenerator:
    """Sistema coordenador de múltiplos agentes para geração de flashcards"""

    def __init__(self, openai_api_key: str, max_agents: int = 4) -> None:
        # openai_api_key é mantido por compatibilidade, mas o gerenciamento do
        # cliente é centralizado em openai_utils.
        self.openai_api_key = openai_api_key
        self.max_agents = max_agents
        self.agents = [FlashcardAgent(i + 1) for i in range(max_agents)]

    async def _generate_subtopics(self, main_topic: str, count: int) -> List[str]:
        if not is_openai_configured():
            return [f"{main_topic} - Parte {i + 1}" for i in range(count)]

        prompt = (
            f"Divida o tópico \"{main_topic}\" em {count} subtópicos específicos e distintos.\n"
            "Responda apenas com uma lista JSON de strings:\n"
            "[\"Subtópico 1\", \"Subtópico 2\", ...]"
        )

        try:
            response = await create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()

            subtopics = json.loads(content)
        except Exception as exc:  # pragma: no cover - fallback
            logger.warning(
                "⚠️ Erro ao gerar subtópicos via OpenAI (%s). Usando subtópicos genéricos.",
                exc,
            )
            subtopics = []

        while len(subtopics) < count:
            subtopics.append(f"{main_topic} - Parte {len(subtopics) + 1}")
        return subtopics[:count]

    async def _create_batches(self, state: MultiAgentFlashcardState) -> List[FlashcardBatch]:
        agents_to_use = max(1, min(self.max_agents, state.total_count))
        state.agents_count = agents_to_use

        subtopics = await self._generate_subtopics(state.topic, agents_to_use)

        flashcards_per_agent = max(1, state.total_count // agents_to_use)
        remaining = state.total_count % agents_to_use

        batches: List[FlashcardBatch] = []
        for index in range(agents_to_use):
            count_for_agent = flashcards_per_agent + (1 if index < remaining else 0)
            if count_for_agent <= 0:
                continue
            batches.append(
                FlashcardBatch(
                    topic=state.topic,
                    subtopic=subtopics[index],
                    count=count_for_agent,
                    difficulty=state.difficulty,
                    agent_id=index + 1,
                )
            )

        logger.info("📦 Criados %s lotes para processamento paralelo", len(batches))
        return batches

    def estimate_batches(self, requested_count: int) -> int:
        if requested_count <= 0:
            return 1
        return min(self.max_agents, requested_count)

    async def generate_flashcards_parallel(
        self,
        *,
        topic: str,
        count: int,
        difficulty: str = "medium",
        subject: Optional[str] = None,
        user_id: str = "default",
        progress_callback: Optional[
            Callable[[int, str, str, int, Optional[int]], None]
        ] = None,
    ) -> Dict[str, Any]:
        if not is_openai_configured():
            return {
                "success": False,
                "error": "Serviço de IA indisponível no momento",
            }

        if count <= 0:
            return {
                "success": False,
                "error": "Quantidade de flashcards deve ser positiva",
            }

        state = MultiAgentFlashcardState(
            topic=topic,
            total_count=count,
            difficulty=difficulty,
            subject=subject,
            user_id=user_id,
        )

        logger.info(
            "🚀 Iniciando geração paralela: %s flashcards sobre '%s'",
            count,
            topic,
        )

        try:
            state.batches = await self._create_batches(state)

            if not state.batches:
                return {
                    "success": False,
                    "error": "Não foi possível criar lotes de flashcards",
                }

            total_batches = len(state.batches)
            if progress_callback:
                for batch in state.batches:
                    progress_callback(
                        batch.agent_id,
                        "queued",
                        batch.subtopic,
                        0,
                        total_batches,
                    )

            tasks = [
                asyncio.create_task(
                    self.agents[batch.agent_id - 1].generate_flashcards_batch(
                        batch,
                        total_batches,
                        progress_callback,
                    )
                )
                for batch in state.batches
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            completed_batches: List[FlashcardBatch] = []
            for batch, result in zip(state.batches, results):
                if isinstance(result, Exception):
                    batch.status = "error"
                    batch.error_message = str(result)
                    logger.exception(
                        "❌ Erro no processamento do lote %s: %s",
                        batch.batch_id,
                        result,
                    )
                    if progress_callback:
                        progress_callback(
                            batch.agent_id,
                            "error",
                            batch.subtopic,
                            100,
                            total_batches,
                        )
                    completed_batches.append(batch)
                    continue

                completed_batches.append(result)
                if result.status == "completed":
                    state.completed_flashcards.extend(result.flashcards)

            state.batches = completed_batches
            state.end_time = datetime.now()

            successful_batches = [b for b in state.batches if b.status == "completed"]
            failed_batches = [b for b in state.batches if b.status == "error"]

            if state.completed_flashcards:
                state.status = "completed"
                processing_time = (
                    state.end_time - state.start_time
                ).total_seconds() if state.end_time else 0

                logger.info(
                    "✅ Geração concluída: %s flashcards em %.2fs",
                    len(state.completed_flashcards),
                    processing_time,
                )

                if failed_batches:
                    logger.warning(
                        "⚠️ Lotes com erro: %s", len(failed_batches)
                    )

                return {
                    "success": True,
                    "flashcards": state.completed_flashcards,
                    "topic": topic,
                    "count": len(state.completed_flashcards),
                    "difficulty": difficulty,
                    "processing_time": processing_time,
                    "agents_used": len(successful_batches),
                    "batches_completed": len(successful_batches),
                    "batches_failed": len(failed_batches),
                }

            state.status = "error"
            logger.error("❌ Nenhum flashcard foi gerado com sucesso")
            return {
                "success": False,
                "error": "Falha na geração de flashcards",
                "failed_batches": len(failed_batches),
                "details": [
                    b.error_message for b in failed_batches if b.error_message
                ],
            }

        except RuntimeError as exc:
            logger.error("❌ OpenAI não configurado: %s", exc)
            return {
                "success": False,
                "error": "Serviço de IA indisponível no momento",
            }
        except Exception as exc:  # pragma: no cover - proteção
            logger.exception("❌ Erro crítico na geração paralela: %s", exc)
            return {
                "success": False,
                "error": f"Erro crítico: {exc}",
                "topic": topic,
                "count": 0,
            }
