"""OpenAI Responses API adapter used by customer-service agents."""

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel

from app.core.exceptions import AIProviderError


class OpenAIResponsesClient:
    """Generate text through the OpenAI Responses API."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def generate(self, *, instructions: str, user_input: str) -> str:
        """Return the aggregated text output from one model response."""
        try:
            response = await self._client.responses.create(
                model=self._model,
                instructions=instructions,
                input=user_input,
                store=False,
            )
            return response.output_text
        except OpenAIError as error:
            raise AIProviderError("The AI provider could not generate a response.") from error

    async def interpret(
        self,
        *,
        instructions: str,
        user_input: str,
        response_format: type[BaseModel],
    ) -> BaseModel:
        """Parse model output into a strict Pydantic contract."""
        try:
            response = await self._client.responses.parse(
                model=self._model,
                instructions=instructions,
                input=user_input,
                text_format=response_format,
                store=False,
            )
            parsed = response.output_parsed
            if parsed is None:
                raise AIProviderError("The AI provider returned no structured result.")
            return parsed
        except OpenAIError as error:
            raise AIProviderError("The AI provider could not interpret the message.") from error
