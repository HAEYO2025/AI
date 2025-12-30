"""
API 요청/응답 모델 정의
"""
from pydantic import BaseModel, Field
from typing import Optional


class QueryRequest(BaseModel):
    """LLM 질의 요청 모델"""

    prompt: str = Field(..., description="사용자 질의 프롬프트")
    system_message: Optional[str] = Field(None, description="시스템 메시지 (선택사항)")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="생성 온도")
    max_tokens: Optional[int] = Field(2048, gt=0, description="최대 토큰 수")

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "파이썬으로 피보나치 수열을 생성하는 함수를 작성해줘",
                "system_message": "당신은 전문 프로그래머입니다.",
                "temperature": 0.7,
                "max_tokens": 2048
            }
        }


class QueryResponse(BaseModel):
    """LLM 질의 응답 모델 (비스트리밍)"""

    response: str = Field(..., description="LLM 생성 응답")
    model: str = Field(..., description="사용된 모델 이름")

    class Config:
        json_schema_extra = {
            "example": {
                "response": "def fibonacci(n):\n    if n <= 1:\n        return n\n    ...",
                "model": "gpt-4-turbo-preview"
            }
        }
