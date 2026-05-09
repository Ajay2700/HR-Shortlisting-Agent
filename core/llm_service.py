"""
LLM Service
=============
Abstraction layer over OpenAI chat models via LangChain.
Handles initialization, structured output, retry logic, and fallback parsing.
"""

import json
import logging
from typing import Type, TypeVar

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel

import config

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMService:
    """Centralized LLM service with structured output and safety controls."""

    def __init__(self):
        self._model = None

    @property
    def model(self) -> ChatOpenAI:
        """Lazy-initialize the LLM to defer API key validation."""
        if self._model is None:
            config.validate_config()
            self._model = ChatOpenAI(
                model=config.LLM_MODEL,
                api_key=config.OPENAI_API_KEY,
                temperature=config.LLM_TEMPERATURE,
                max_retries=config.LLM_MAX_RETRIES,
            )
            logger.info(f"LLM initialized: {config.LLM_MODEL}")
        return self._model

    def invoke(self, system_prompt: str, user_prompt: str) -> str:
        """
        Simple text completion with system + user prompt.
        Returns raw string response.
        """
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = self.model.invoke(messages)
        return response.content

    def invoke_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
    ) -> T:
        """
        Invoke LLM with structured output using Pydantic schema.
        Uses LangChain's with_structured_output for reliable JSON extraction.
        
        Falls back to manual JSON parsing if structured output fails.
        This is a critical reliability pattern for production agents.
        """
        try:
            structured_model = self.model.with_structured_output(output_schema)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            result = structured_model.invoke(messages)
            logger.info(f"Structured output successful: {output_schema.__name__}")
            return result
        except Exception as e:
            logger.warning(f"Structured output failed, attempting manual parse: {e}")
            return self._fallback_parse(system_prompt, user_prompt, output_schema)

    def _fallback_parse(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
    ) -> T:
        """
        Fallback: Ask LLM to produce JSON, then parse manually.
        This handles cases where with_structured_output isn't supported.
        """
        json_instruction = (
            f"\n\nYou MUST respond with ONLY valid JSON matching this exact schema:\n"
            f"{json.dumps(output_schema.model_json_schema(), indent=2)}\n"
            f"No markdown, no code fences, no explanation — ONLY the JSON object."
        )
        raw = self.invoke(system_prompt + json_instruction, user_prompt)

        # Clean any markdown code fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Handle potential 'json' language tag
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

        parsed = json.loads(cleaned)
        return output_schema.model_validate(parsed)


# Singleton instance
llm_service = LLMService()
