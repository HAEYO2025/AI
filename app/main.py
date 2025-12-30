"""
FastAPI 스트리밍 API 애플리케이션
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import json
from typing import AsyncIterator

from app.llm import LLMService
from app.models import QueryRequest, QueryResponse


# LLM 서비스 인스턴스
llm_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    global llm_service
    # 시작 시
    llm_service = LLMService()
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


async def generate_stream_response(prompt: str) -> AsyncIterator[str]:
    """
    Server-Sent Events 형식으로 스트리밍 응답 생성

    Args:
        prompt: 사용자 프롬프트

    Yields:
        SSE 형식의 데이터
    """
    try:
        async for chunk in llm_service.generate_stream(prompt):
            # SSE 형식으로 데이터 전송
            data = json.dumps({"content": chunk}, ensure_ascii=False)
            yield f"data: {data}\n\n"

        # 스트림 종료 신호
        yield f"data: {json.dumps({'done': True})}\n\n"

    except Exception as e:
        error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
        yield f"data: {error_data}\n\n"


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
    스트리밍 방식으로 LLM에 질의

    Args:
        request: 질의 요청 데이터

    Returns:
        StreamingResponse: Server-Sent Events 스트림
    """
    if not llm_service:
        raise HTTPException(status_code=503, detail="LLM service not initialized")

    return StreamingResponse(
        generate_stream_response(prompt=request.prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/query", response_model=QueryResponse)
async def query_normal(request: QueryRequest):
    """
    일반 방식으로 LLM에 질의 (비스트리밍)

    Args:
        request: 질의 요청 데이터

    Returns:
        QueryResponse: LLM 응답
    """
    if not llm_service:
        raise HTTPException(status_code=503, detail="LLM service not initialized")

    try:
        response = await llm_service.generate(prompt=request.prompt)

        return QueryResponse(
            response=response,
            model=llm_service.model_name
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
