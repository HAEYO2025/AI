"""
LangChain LLM 클래스 정의
"""
from typing import AsyncIterator, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langchain.callbacks.base import AsyncCallbackHandler
from langchain.schema.output import LLMResult
import os
from dotenv import load_dotenv

load_dotenv()


class StreamingCallbackHandler(AsyncCallbackHandler):
    """스트리밍을 위한 콜백 핸들러"""

    def __init__(self):
        self.tokens = []

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        """새로운 토큰이 생성될 때 호출"""
        self.tokens.append(token)

    async def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """LLM 응답이 완료되었을 때 호출"""
        pass


class LLMService:
    """LangChain을 사용한 LLM 서비스 클래스"""

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        streaming: bool = True
    ):
        """
        Args:
            model_name: 사용할 모델 이름 (기본값: 환경변수에서 가져옴)
            temperature: 생성 온도 (0.0 ~ 2.0)
            max_tokens: 최대 토큰 수
            streaming: 스트리밍 사용 여부
        """
        self.model_name = model_name or os.getenv("MODEL_NAME", "gpt-4-turbo-preview")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.streaming = streaming

        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            streaming=self.streaming,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

    async def generate_stream(
        self,
        prompt: str,
        system_message: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        스트리밍 방식으로 LLM 응답 생성

        Args:
            prompt: 사용자 프롬프트
            system_message: 시스템 메시지 (선택사항)

        Yields:
            생성된 토큰들
        """
        messages = []

        if system_message:
            messages.append(SystemMessage(content=system_message))

        messages.append(HumanMessage(content=prompt))

        async for chunk in self.llm.astream(messages):
            if chunk.content:
                yield chunk.content

    async def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None
    ) -> str:
        """
        일반 방식으로 LLM 응답 생성

        Args:
            prompt: 사용자 프롬프트
            system_message: 시스템 메시지 (선택사항)

        Returns:
            생성된 전체 응답
        """
        messages = []

        if system_message:
            messages.append(SystemMessage(content=system_message))

        messages.append(HumanMessage(content=prompt))

        response = await self.llm.ainvoke(messages)
        return response.content
