from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool

from src.memory.database import Database
from src.utils.config import AppConfig

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all agents with LangChain LLM access, tools, and memory."""

    def __init__(
        self,
        llm: BaseChatModel,
        db: Database,
        config: AppConfig,
        system_prompt: str = "",
    ) -> None:
        self.llm = llm
        self.db = db
        self.config = config
        self.system_prompt = system_prompt
        self._tools: List[BaseTool] = []

    def register_tool(self, tool: BaseTool) -> None:
        self._tools.append(tool)

    def _build_prompt(self, user_template: str) -> ChatPromptTemplate:
        messages: list = []
        if self.system_prompt:
            messages.append(("system", self.system_prompt))
        messages.append(("human", user_template))
        return ChatPromptTemplate.from_messages(messages)

    async def think(self, prompt_template: str, **kwargs: Any) -> str:
        """Run a simple LLM call via LCEL chain and return the text response."""
        prompt = self._build_prompt(prompt_template)
        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke(kwargs)

    async def think_json(self, prompt_template: str, **kwargs: Any) -> Dict:
        """Run an LLM call with JSON output mode via LCEL chain."""
        prompt = self._build_prompt(prompt_template)
        json_llm = self.llm.bind(response_format={"type": "json_object"})
        chain = prompt | json_llm | JsonOutputParser()
        try:
            return await chain.ainvoke(kwargs)
        except Exception as exc:
            logger.error("Failed to get/parse JSON from LLM: %s", exc)
            return {}

    async def think_with_tools(
        self, prompt_template: str, *, max_rounds: int = 5, **kwargs: Any
    ) -> str:
        """Run a tool-calling loop: invoke LLM, execute tools, feed results back."""
        if not self._tools:
            return await self.think(prompt_template, **kwargs)

        prompt = self._build_prompt(prompt_template)
        llm_with_tools = self.llm.bind_tools(self._tools)

        messages = await prompt.aformat_messages(**kwargs)

        for _ in range(max_rounds):
            response = await llm_with_tools.ainvoke(messages)
            messages.append(response)

            if not response.tool_calls:
                return response.content or ""

            tool_map = {t.name: t for t in self._tools}
            for tc in response.tool_calls:
                tool = tool_map.get(tc["name"])
                if tool:
                    result = await tool.ainvoke(tc["args"])
                else:
                    result = f"Unknown tool: {tc['name']}"
                messages.append(
                    ToolMessage(content=str(result), tool_call_id=tc["id"])
                )

        last = messages[-1]
        return last.content if hasattr(last, "content") else ""

    @abstractmethod
    async def run(self, session_id: str, **kwargs: Any) -> Any:
        """Execute the agent's main task."""
        ...
