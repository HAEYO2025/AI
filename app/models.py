"""
API 요청/응답 모델 정의
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Scenario(BaseModel):
    """시나리오 정보"""
    title: str = Field(..., description="시나리오 제목")
    description: str = Field(..., description="시나리오 설명")
    start_date: str = Field(..., description="시나리오 시작 날짜")


class Report(BaseModel):
    """제보 정보"""
    title: str = Field(..., description="제보 제목")
    longitude: float = Field(..., description="경도")
    latitude: float = Field(..., description="위도")
    description: str = Field(..., description="제보 내용")
    reported_date: str = Field(..., description="제보 날짜")


class TurnHistory(BaseModel):
    """한 턴의 히스토리 (상황 + 선택)"""
    situation: str = Field(..., description="생성된 상황")
    choice: str = Field(..., description="사용자가 선택한 행동")


class QueryRequest(BaseModel):
    """LLM 질의 요청 모델"""

    scenario: Scenario = Field(..., description="시나리오 정보")
    report: Report = Field(..., description="제보 정보")
    history: Optional[list[TurnHistory]] = Field(
        default=[],
        description="이전 턴들의 히스토리 (상황과 선택의 누적)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "scenario": {
                    "title": "태풍 대비 훈련",
                    "description": "여름철 태풍 대비 비상 대응 훈련",
                    "start_date": "2024-07-15"
                },
                "report": {
                    "title": "침수 피해 발생",
                    "longitude": 126.9780,
                    "latitude": 37.5665,
                    "description": "강남역 인근 지하 주차장 침수 발생, 차량 10대 이상 피해",
                    "reported_date": "2024-07-15T14:30:00"
                },
                "history": [
                    {
                        "situation": "물이 빠르게 차오르고 있다. 지하 주차장 출구가 보이지 않는다.",
                        "choice": "119에 신고한다"
                    },
                    {
                        "situation": "119에 연락했다. 5분 내 도착 예정이라고 한다. 하지만 물은 계속 차오르고 있다.",
                        "choice": "차량 위로 올라간다"
                    }
                ]
            }
        }


class ChoiceFeedback(BaseModel):
    """선택에 대한 피드백"""
    chosen_action: str = Field(..., description="사용자가 선택한 행동")
    evaluation: str = Field(..., description="평가 (excellent/good/neutral/risky/dangerous)")
    comment: str = Field(..., description="선택에 대한 전문가 코멘트")
    better_choice: Optional[str] = Field(None, description="더 나은 선택 제안 (있다면)")
    survival_impact: str = Field(..., description="생존률 변화 (+15, -10 등)")


class QueryResponse(BaseModel):
    """LLM 질의 응답 모델 (비스트리밍)"""

    response: str = Field(..., description="LLM 생성 응답")
    model: str = Field(..., description="사용된 모델 이름")

    class Config:
        json_schema_extra = {
            "example": {
                "response": "def fibonacci(n):\\n    if n <= 1:\\n        return n\\n    ...",
                "model": "gpt-4-turbo-preview"
            }
        }

