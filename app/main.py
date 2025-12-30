"""
FastAPI 스트리밍 API 애플리케이션
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import json
from typing import AsyncIterator

from app.llm import ScenarioSimulationLLM
from app.models import QueryRequest, QueryResponse


# LLM 서비스 인스턴스
llm_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    global llm_service
    # 시작 시
    llm_service = ScenarioSimulationLLM()
    yield
    # 종료 시
    llm_service = None


app = FastAPI(
    title="LangChain LLM Streaming API",
    description="LangChain과 FastAPI를 사용한 LLM 스트리밍 API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_llm_kwargs(request: QueryRequest) -> dict:
    """
    요청 데이터로부터 LLM 호출 인자 생성

    Args:
        request: 시나리오 및 제보 요청 데이터 (히스토리 포함)

    Returns:
        LLM.generate() 또는 LLM.generate_stream()에 전달할 kwargs
    """
    kwargs = {
        "scenario_title": request.scenario.title,
        "scenario_description": request.scenario.description,
        "scenario_start_date": request.scenario.start_date,
        "report_title": request.report.title,
        "report_description": request.report.description,
        "report_latitude": request.report.latitude,
        "report_longitude": request.report.longitude,
        "report_date": request.report.reported_date,
        "history": [turn.dict() for turn in request.history] if request.history else []
    }
    return kwargs


async def generate_stream_response(request: QueryRequest) -> AsyncIterator[str]:
    """
    Server-Sent Events 형식으로 스트리밍 응답 생성
    1. 상황 생성
    2. 선택지 생성

    Args:
        request: 시나리오 및 제보 요청 데이터

    Yields:
        SSE 형식의 데이터
    """
    try:
        print(f"[DEBUG] 요청 받음: scenario={request.scenario.title}, report={request.report.title}")

        llm_kwargs = get_llm_kwargs(request)

        # 1단계: 상황 생성 (스트리밍)
        print(f"[DEBUG] 1단계: 상황 생성 시작...")
        situation_content = ""

        async for chunk in llm_service.generate_situation(**llm_kwargs):
            situation_content += chunk
            # 실시간으로 상황 전송
            chunk_data = {'content': chunk}
            yield f"event: situation\ndata: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"

        print(f"[DEBUG] 상황 생성 완료 (길이: {len(situation_content)})")

        # 2단계: 선택지 3개 생성 (한번에)
        print(f"[DEBUG] 2단계: 선택지 생성 시작...")
        choices = await llm_service.generate_choices(
            situation_content,
            history=llm_kwargs.get("history")
        )

        print(f"[DEBUG] 선택지 생성 완료 (개수: {len(choices)})")

        # 각 선택지를 개별 이벤트로 전송
        for i, choice in enumerate(choices, 1):
            if choice:  # 빈 선택지는 전송하지 않음
                choice_data = {'content': choice}
                yield f"event: choice{i}\ndata: {json.dumps(choice_data, ensure_ascii=False)}\n\n"
                print(f"[DEBUG] choice{i} 전송: {choice[:50]}...")

        # 3단계: 생존률 계산
        print(f"[DEBUG] 3단계: 생존률 계산 시작...")
        survival_data = await llm_service.generate_survival_rate(
            scenario_title=request.scenario.title,
            current_situation=situation_content,
            history=llm_kwargs.get("history")
        )
        yield f"event: survival_rate\ndata: {json.dumps(survival_data, ensure_ascii=False)}\n\n"
        print(f"[DEBUG] 생존률 전송: {survival_data}")

        # 4단계: 피드백 생성 (2턴째부터)
        history = llm_kwargs.get("history", [])
        if history and len(history) > 0:
            print(f"[DEBUG] 4단계: 피드백 생성 시작...")
            last_turn = history[-1]
            
            feedback_data = await llm_service.generate_feedback(
                scenario_title=request.scenario.title,
                chosen_action=last_turn['choice'],
                previous_situation=last_turn['situation'],
                current_situation=situation_content,
                available_choices=choices
            )
            yield f"event: feedback\ndata: {json.dumps(feedback_data, ensure_ascii=False)}\n\n"
            print(f"[DEBUG] 피드백 전송: {feedback_data['evaluation']}")

        # 스트림 종료 신호
        done_data = {'done': True}
        yield f"event: done\ndata: {json.dumps(done_data)}\n\n"

    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        print(f"[ERROR] 예외 발생: {error_msg}")
        error_data = json.dumps({"error": error_msg}, ensure_ascii=False)
        yield f"event: error\ndata: {error_data}\n\n"


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "LangChain LLM Streaming API",
        "endpoints": {
            "stream": "/api/query/stream",
            "normal": "/api/query",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "service": "LLM API",
        "model": llm_service.model_name if llm_service else "not initialized"
    }


@app.post("/api/query/stream")
async def query_stream(request: QueryRequest):
    """
    스트리밍 방식으로 시나리오 생성

    Args:
        request: 시나리오 및 제보 요청 데이터

    Returns:
        StreamingResponse: Server-Sent Events 스트림
    """
    if not llm_service:
        raise HTTPException(status_code=503, detail="LLM service not initialized")

    return StreamingResponse(
        generate_stream_response(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/query")
async def query_normal(request: QueryRequest):
    """
    일반 방식으로 시나리오 생성 (비스트리밍)

    Args:
        request: 시나리오 및 제보 요청 데이터

    Returns:
        구조화된 시나리오 응답 (situation, choices)
    """
    if not llm_service:
        raise HTTPException(status_code=503, detail="LLM service not initialized")

    try:
        llm_kwargs = get_llm_kwargs(request)

        # 1단계: 상황 생성
        situation = ""
        async for chunk in llm_service.generate_situation(**llm_kwargs):
            situation += chunk

        # 2단계: 선택지 생성
        choices = await llm_service.generate_choices(
            situation,
            history=llm_kwargs.get("history")
        )

        # 3단계: 생존률 계산
        survival_data = await llm_service.generate_survival_rate(
            scenario_title=request.scenario.title,
            current_situation=situation,
            history=llm_kwargs.get("history")
        )

        # 4단계: 피드백 생성 (2턴째부터)
        feedback_data = None
        history = llm_kwargs.get("history", [])
        if history and len(history) > 0:
            last_turn = history[-1]
            feedback_data = await llm_service.generate_feedback(
                scenario_title=request.scenario.title,
                chosen_action=last_turn['choice'],
                previous_situation=last_turn['situation'],
                current_situation=situation,
                available_choices=choices
            )

        response = {
            "situation": situation,
            "choice1": choices[0] if len(choices) > 0 else "",
            "choice2": choices[1] if len(choices) > 1 else "",
            "choice3": choices[2] if len(choices) > 2 else "",
            "survival_rate": survival_data["survival_rate"],
            "survival_change": survival_data["change"],
            "model": llm_service.model_name
        }

        # 피드백이 있으면 추가
        if feedback_data:
            response["feedback"] = feedback_data

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
