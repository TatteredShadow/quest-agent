from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.models.character import Character
from src.models.quest import Quest, Goal
from src.models.world import WorldState
from src.models.story import Chapter, PlotPoint

_DB_DIR = Path(__file__).resolve().parents[2] / "data" / "vectordb"


class Database:
    """Persistent storage backed by ChromaDB vector database.

    Each data domain maps to a ChromaDB collection.  Text-heavy collections
    (chapters, key_facts, quests) are embedded for semantic similarity search;
    structured-data collections store JSON in metadata and use filter queries.
    """

    def __init__(
        self,
        config: Any = None,
        db_path: Optional[Union[Path, str]] = None,
    ) -> None:
        path = Path(db_path) if db_path else _DB_DIR
        path.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=str(path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        self._ef = self._create_embedding_function(config)
        self._init_collections()

    # ── internal helpers ──

    def _create_embedding_function(self, config: Any) -> Any:
        if config is None:
            return None
        llm_cfg = getattr(config, "llm", None)
        if llm_cfg is None:
            return None
        api_key = getattr(llm_cfg, "api_key", None)
        if not api_key:
            return None
        try:
            from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

            kwargs: Dict[str, Any] = {
                "api_key": api_key,
                "model_name": getattr(llm_cfg, "embedding_model", "text-embedding-3-small"),
            }
            base_url = getattr(llm_cfg, "base_url", "")
            if base_url:
                kwargs["api_base"] = base_url
            return OpenAIEmbeddingFunction(**kwargs)
        except Exception:
            return None

    def _init_collections(self) -> None:
        kw: Dict[str, Any] = {}
        if self._ef is not None:
            kw["embedding_function"] = self._ef

        self._sessions = self._client.get_or_create_collection("sessions", **kw)
        self._characters = self._client.get_or_create_collection("characters", **kw)
        self._goals = self._client.get_or_create_collection("goals", **kw)
        self._quests = self._client.get_or_create_collection("quests", **kw)
        self._chapters = self._client.get_or_create_collection("chapters", **kw)
        self._world_states = self._client.get_or_create_collection("world_states", **kw)
        self._key_facts = self._client.get_or_create_collection("key_facts", **kw)

    async def initialize(self) -> None:
        """No-op — ChromaDB collections are created in __init__."""

    # ── Session ──

    async def create_session(self) -> str:
        session_id = uuid.uuid4().hex[:12]
        self._sessions.add(
            ids=[session_id],
            documents=[f"session:{session_id}"],
            metadatas=[{"created_at": datetime.now().isoformat(), "active": 1}],
        )
        return session_id

    async def get_active_session(self) -> Optional[str]:
        results = self._sessions.get(
            where={"active": 1},
            include=["metadatas"],
        )
        if not results["ids"]:
            return None
        pairs = list(zip(results["ids"], results["metadatas"]))
        pairs.sort(key=lambda p: p[1].get("created_at", ""), reverse=True)
        return pairs[0][0]

    # ── Character ──

    async def save_character(self, session_id: str, character: Character) -> None:
        if not character.id:
            character.id = uuid.uuid4().hex[:12]
        doc_id = f"{session_id}_char"
        summary = (
            f"{character.name} Lv.{character.level} "
            f"{character.character_class.display_name} "
            f"HP:{character.hp}/{character.max_hp}"
        )
        self._characters.upsert(
            ids=[doc_id],
            documents=[summary],
            metadatas=[{
                "session_id": session_id,
                "data_json": character.model_dump_json(),
            }],
        )

    async def load_character(self, session_id: str) -> Optional[Character]:
        doc_id = f"{session_id}_char"
        results = self._characters.get(ids=[doc_id], include=["metadatas"])
        if not results["ids"]:
            return None
        return Character.model_validate_json(results["metadatas"][0]["data_json"])

    # ── Goal ──

    async def save_goal(self, session_id: str, goal: Goal) -> None:
        if not goal.id:
            goal.id = uuid.uuid4().hex[:12]
        doc_id = f"{session_id}_goal"
        self._goals.upsert(
            ids=[doc_id],
            documents=[goal.description],
            metadatas=[{
                "session_id": session_id,
                "data_json": goal.model_dump_json(),
            }],
        )

    async def load_goal(self, session_id: str) -> Optional[Goal]:
        doc_id = f"{session_id}_goal"
        results = self._goals.get(ids=[doc_id], include=["metadatas"])
        if not results["ids"]:
            return None
        return Goal.model_validate_json(results["metadatas"][0]["data_json"])

    # ── Quests ──

    async def save_quest(self, session_id: str, quest: Quest) -> None:
        if not quest.id:
            quest.id = uuid.uuid4().hex[:12]
        doc_text = f"{quest.title} - {quest.real_task}"
        self._quests.upsert(
            ids=[quest.id],
            documents=[doc_text],
            metadatas=[{
                "session_id": session_id,
                "quest_type": quest.quest_type.value,
                "status": quest.status.value,
                "data_json": quest.model_dump_json(),
                "created_at": quest.created_at.isoformat(),
                "created_date": quest.created_at.date().isoformat(),
            }],
        )

    async def load_active_quests(self, session_id: str) -> List[Quest]:
        results = self._quests.get(
            where={"$and": [{"session_id": session_id}, {"status": "active"}]},
            include=["metadatas"],
        )
        return [Quest.model_validate_json(m["data_json"]) for m in results["metadatas"]]

    async def load_daily_quests_today(self, session_id: str, date_str: str) -> List[Quest]:
        results = self._quests.get(
            where={
                "$and": [
                    {"session_id": session_id},
                    {"quest_type": "daily"},
                    {"created_date": date_str},
                ]
            },
            include=["metadatas"],
        )
        return [Quest.model_validate_json(m["data_json"]) for m in results["metadatas"]]

    async def get_completion_history(self, session_id: str, days: int = 7) -> List[float]:
        results = self._quests.get(
            where={
                "$and": [
                    {"session_id": session_id},
                    {"quest_type": "daily"},
                    {"status": {"$ne": "active"}},
                ]
            },
            include=["metadatas"],
        )
        if not results["ids"]:
            return []
        quests = [Quest.model_validate_json(m["data_json"]) for m in results["metadatas"]]
        quests.sort(key=lambda q: q.created_at, reverse=True)
        quests = quests[: days * 4]
        return [q.completion_pct for q in quests]

    # ── Chapters ──

    async def save_chapter(self, session_id: str, chapter: Chapter) -> None:
        doc_id = f"{session_id}_ch{chapter.chapter_number}"
        plot_json = json.dumps(
            [pp.model_dump() for pp in chapter.plot_points], ensure_ascii=False
        )
        self._chapters.upsert(
            ids=[doc_id],
            documents=[chapter.content],
            metadatas=[{
                "session_id": session_id,
                "chapter_number": chapter.chapter_number,
                "title": chapter.title,
                "summary": chapter.summary or "",
                "outcome_type": chapter.outcome_type.value,
                "plot_points_json": plot_json,
                "created_at": chapter.created_at.isoformat(),
            }],
        )

    async def load_chapters(
        self, session_id: str, limit: Optional[int] = None
    ) -> List[Chapter]:
        results = self._chapters.get(
            where={"session_id": session_id},
            include=["documents", "metadatas"],
        )
        if not results["ids"]:
            return []
        chapters = self._parse_chapters(results["metadatas"], results["documents"])
        chapters.sort(key=lambda c: c.chapter_number)
        if limit:
            chapters = chapters[-limit:]
        return chapters

    async def get_latest_chapter_number(self, session_id: str) -> int:
        results = self._chapters.get(
            where={"session_id": session_id},
            include=["metadatas"],
        )
        if not results["metadatas"]:
            return 0
        return max(m["chapter_number"] for m in results["metadatas"])

    async def search_similar_chapters(
        self, session_id: str, query: str, limit: int = 3
    ) -> List[Chapter]:
        """Semantic similarity search over chapter content."""
        try:
            count = self._chapters.count()
            if count == 0:
                return []
            n = min(limit, count)
            results = self._chapters.query(
                query_texts=[query],
                n_results=n,
                where={"session_id": session_id},
                include=["documents", "metadatas"],
            )
            if not results["ids"] or not results["ids"][0]:
                return []
            chapters = self._parse_chapters(
                results["metadatas"][0], results["documents"][0]
            )
            chapters.sort(key=lambda c: c.chapter_number)
            return chapters
        except Exception:
            return await self.load_chapters(session_id, limit=limit)

    def _parse_chapters(
        self, metadatas: List[Dict], documents: List[str]
    ) -> List[Chapter]:
        chapters: List[Chapter] = []
        for meta, content in zip(metadatas, documents):
            pps = (
                [PlotPoint(**pp) for pp in json.loads(meta["plot_points_json"])]
                if meta.get("plot_points_json")
                else []
            )
            chapters.append(
                Chapter(
                    chapter_number=meta["chapter_number"],
                    title=meta["title"],
                    content=content,
                    summary=meta.get("summary", ""),
                    outcome_type=meta["outcome_type"],
                    plot_points=pps,
                    created_at=datetime.fromisoformat(meta["created_at"]),
                )
            )
        return chapters

    # ── World State ──

    async def save_world_state(self, session_id: str, world: WorldState) -> None:
        ts = datetime.now()
        doc_id = f"{session_id}_ws_{ts.strftime('%Y%m%d%H%M%S%f')}"
        locs = ", ".join(loc.name for loc in world.discovered_locations)
        npcs = ", ".join(n.name for n in world.npcs)
        threats = ", ".join(t.name for t in world.active_threats)
        doc_text = (
            f"位置:{world.current_location} 地点:{locs} "
            f"NPC:{npcs} 威胁:{threats} {world.world_seed}"
        )
        self._world_states.add(
            ids=[doc_id],
            documents=[doc_text],
            metadatas=[{
                "session_id": session_id,
                "data_json": world.model_dump_json(),
                "updated_at": ts.isoformat(),
            }],
        )

    async def load_world_state(self, session_id: str) -> Optional[WorldState]:
        results = self._world_states.get(
            where={"session_id": session_id},
            include=["metadatas"],
        )
        if not results["ids"]:
            return None
        pairs = list(zip(results["metadatas"], results["ids"]))
        pairs.sort(key=lambda p: p[0]["updated_at"], reverse=True)
        return WorldState.model_validate_json(pairs[0][0]["data_json"])

    # ── Key Facts ──

    async def save_key_fact(
        self,
        session_id: str,
        fact_type: str,
        content: str,
        chapter_ref: Optional[int] = None,
    ) -> None:
        fact_id = uuid.uuid4().hex[:12]
        self._key_facts.add(
            ids=[fact_id],
            documents=[content],
            metadatas=[{
                "session_id": session_id,
                "fact_type": fact_type,
                "chapter_ref": chapter_ref if chapter_ref is not None else -1,
                "resolved": 0,
            }],
        )

    async def load_unresolved_facts(self, session_id: str) -> List[Dict]:
        results = self._key_facts.get(
            where={"$and": [{"session_id": session_id}, {"resolved": 0}]},
            include=["documents", "metadatas"],
        )
        return self._parse_facts(results)

    async def search_relevant_facts(
        self, session_id: str, query: str, limit: int = 5
    ) -> List[Dict]:
        """Semantic similarity search over key facts."""
        try:
            count = self._key_facts.count()
            if count == 0:
                return []
            n = min(limit, count)
            results = self._key_facts.query(
                query_texts=[query],
                n_results=n,
                where={"$and": [{"session_id": session_id}, {"resolved": 0}]},
                include=["documents", "metadatas"],
            )
            if not results["ids"] or not results["ids"][0]:
                return []
            return self._parse_facts_from_query(results)
        except Exception:
            return await self.load_unresolved_facts(session_id)

    @staticmethod
    def _parse_facts(results: Dict) -> List[Dict]:
        facts: List[Dict] = []
        for meta, content in zip(results.get("metadatas", []), results.get("documents", [])):
            facts.append({
                "type": meta["fact_type"],
                "content": content,
                "chapter": meta["chapter_ref"] if meta["chapter_ref"] != -1 else None,
            })
        return facts

    @staticmethod
    def _parse_facts_from_query(results: Dict) -> List[Dict]:
        facts: List[Dict] = []
        for meta, content in zip(results["metadatas"][0], results["documents"][0]):
            facts.append({
                "type": meta["fact_type"],
                "content": content,
                "chapter": meta["chapter_ref"] if meta["chapter_ref"] != -1 else None,
            })
        return facts
