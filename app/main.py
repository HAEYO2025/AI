"""
FastAPI 스트리밍 API 애플리케이션
"""
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import json
from typing import AsyncIterator

from app.llm import ScenarioSimulationLLM
from app.models import QueryRequest, QueryResponse, TideRequest, TideResponse, SafetyGuideRequest, SafetyGuideResponse
from app.ocean import KhoaClient


# LLM 서비스 인스턴스
llm_service = None
khoa_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    global llm_service, khoa_client
    # 시작 시
    llm_service = ScenarioSimulationLLM()
    try:
        khoa_client = KhoaClient()
    except ValueError as exc:
        print(f"[WARN] KHOA client not initialized: {exc}")
        khoa_client = None
    yield
    # 종료 시
    llm_service = None
    khoa_client = None


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


def summarize_ocean_data(ocean_data: dict) -> dict:
    """
    KHOA API 조위 데이터를 요약하여 토큰 사용량 절감
    
    Args:
        ocean_data: KHOA API 원본 응답
        
    Returns:
        요약된 데이터 (최고/최저/평균 조위, 추세, 샘플링된 데이터)
    """
    try:
        # result.data에서 조위 데이터 추출
        data_list = []
        if isinstance(ocean_data, dict):
            if "result" in ocean_data and isinstance(ocean_data["result"], dict):
                if "data" in ocean_data["result"]:
                    data_list = ocean_data["result"]["data"]
            elif "data" in ocean_data:
                data_list = ocean_data["data"]
        
        if not data_list or not isinstance(data_list, list):
            return {"summary": "데이터 없음", "raw_response": str(ocean_data)[:500]}
        
        # 조위 값 추출
        tide_levels = []
        records = []
        for item in data_list:
            if isinstance(item, dict):
                tide_level = item.get("tide_level") or item.get("tideLevel")
                record_time = item.get("record_time") or item.get("recordTime")
                if tide_level is not None:
                    try:
                        tide_levels.append(int(tide_level))
                        if record_time:
                            records.append({"time": record_time, "level": int(tide_level)})
                    except (ValueError, TypeError):
                        continue
        
        if not tide_levels:
            return {"summary": "조위 데이터 없음", "total_records": len(data_list)}
        
        # 통계 계산
        max_tide = max(tide_levels)
        min_tide = min(tide_levels)
        avg_tide = sum(tide_levels) / len(tide_levels)
        
        # 현재 조위 (최근 값)
        current_tide = tide_levels[-1] if tide_levels else None
        
        # 조위 변화 추세 (최근 10개 평균과 이전 10개 평균 비교)
        trend = "stable"
        if len(tide_levels) >= 20:
            recent_avg = sum(tide_levels[-10:]) / 10
            prev_avg = sum(tide_levels[-20:-10]) / 10
            if recent_avg > prev_avg + 5:
                trend = "rising"
            elif recent_avg < prev_avg - 5:
                trend = "falling"
        
        # 샘플링 (30분마다 또는 최대 48개)
        sampled_records = []
        if records:
            sample_interval = max(1, len(records) // 48)  # 최대 48개 샘플
            sampled_records = [records[i] for i in range(0, len(records), sample_interval)]
        
        # 만조/간조 시간 찾기
        high_tide_times = []
        low_tide_times = []
        for i in range(1, len(records) - 1):
            # 만조: 앞뒤보다 높은 지점
            if (records[i]["level"] > records[i-1]["level"] and 
                records[i]["level"] > records[i+1]["level"] and
                records[i]["level"] >= avg_tide):
                high_tide_times.append(records[i])
            # 간조: 앞뒤보다 낮은 지점
            elif (records[i]["level"] < records[i-1]["level"] and 
                  records[i]["level"] < records[i+1]["level"] and
                  records[i]["level"] <= avg_tide):
                low_tide_times.append(records[i])
        
        summary = {
            "total_records": len(data_list),
            "statistics": {
                "max_tide_cm": max_tide,
                "min_tide_cm": min_tide,
                "avg_tide_cm": round(avg_tide, 1),
                "current_tide_cm": current_tide,
                "trend": trend  # rising, falling, stable
            },
            "high_tides": high_tide_times[:5],  # 최대 5개
            "low_tides": low_tide_times[:5],    # 최대 5개
            "sampled_data": sampled_records[:24]  # 최대 24개 (1시간마다)
        }
        
        return summary
        
    except Exception as e:
        print(f"[ERROR] Failed to summarize ocean data: {e}")
        return {"error": str(e), "raw_data_preview": str(ocean_data)[:200]}


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
            "tide": "/api/ocean/tide",
            "safety_guide": "/api/ocean/safety-guide",
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


@app.get("/api/ocean/tide", response_model=TideResponse)
async def get_tide_by_location(request: TideRequest = Depends()):
    """
    사용자 위치 기반 조위 조회
    1) 관측소 목록 조회
    2) 가장 가까운 관측소 선택
    3) 조위 데이터 조회
    """
    if not khoa_client:
        raise HTTPException(status_code=503, detail="KHOA client not initialized")

    try:
        station_data_type = request.station_data_type or "ObsServiceObj"
        if station_data_type == request.data_type and request.data_type in {
            "tideObs",
            "obsWaveHight",
            "seafogReal",
        }:
            station_data_type = "ObsServiceObj"
        required_terms_map = {
            "tideObs": ["조위"],
            "obsWaveHight": ["파고"],
            "seafogReal": ["해무"],
        }
        required_terms = required_terms_map.get(request.data_type)
        required_data_types = None
        required_prefixes = None
        if request.data_type == "tideObs":
            required_data_types = ["조위관측소"]
            required_prefixes = ["DT_"]
        station = khoa_client.get_nearest_station(
            data_type=station_data_type,
            latitude=request.latitude,
            longitude=request.longitude,
            required_terms=required_terms,
            required_data_types=required_data_types,
            required_prefixes=required_prefixes,
        )
        tide_data = khoa_client.get_tide_data(
            data_type=request.data_type,
            obs_code=station.obs_code,
            date=request.date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"KHOA API error: {exc}") from exc

    return TideResponse(
        obs_code=station.obs_code,
        obs_name=station.obs_name,
        station_latitude=station.latitude,
        station_longitude=station.longitude,
        distance_km=station.distance_km,
        data=tide_data,
    )


@app.get("/api/ocean/safety-guide", response_model=SafetyGuideResponse)
async def get_safety_guide(request: SafetyGuideRequest = Depends()):
    """
    사용자 위치 기반 해양 안전 가이드 생성
    1) 해양 데이터 조회 (조위 등)
    2) LLM을 통해 안전 가이드 생성
    """
    if not khoa_client:
        raise HTTPException(status_code=503, detail="KHOA client not initialized")
    if not llm_service:
        raise HTTPException(status_code=503, detail="LLM service not initialized")

    try:
        # 1. 관측소 찾기
        station_data_type = request.station_data_type or "ObsServiceObj"
        if station_data_type == request.data_type and request.data_type in {
            "tideObs",
            "obsWaveHight",
            "seafogReal",
        }:
            station_data_type = "ObsServiceObj"
        required_terms_map = {
            "tideObs": ["조위"],
            "obsWaveHight": ["파고"],
            "seafogReal": ["해무"],
        }
        required_terms = required_terms_map.get(request.data_type)
        required_data_types = None
        required_prefixes = None
        if request.data_type == "tideObs":
            required_data_types = ["조위관측소"]
            required_prefixes = ["DT_"]
        
        station = khoa_client.get_nearest_station(
            data_type=station_data_type,
            latitude=request.latitude,
            longitude=request.longitude,
            required_terms=required_terms,
            required_data_types=required_data_types,
            required_prefixes=required_prefixes,
        )
        
        # 2. 해양 데이터 조회
        ocean_data = khoa_client.get_tide_data(
            data_type=request.data_type,
            obs_code=station.obs_code,
            date=request.date,
        )
        
        # 2.5. 해양 데이터 요약 (토큰 절감)
        summarized_data = summarize_ocean_data(ocean_data)
        print(f"[DEBUG] Ocean data summarized: {len(str(ocean_data))} -> {len(str(summarized_data))} chars")
        
        # 3. LLM으로 안전 가이드 생성
        safety_guide = await llm_service.generate_safety_guide(
            latitude=request.latitude,
            longitude=request.longitude,
            ocean_data=summarized_data,  # 요약된 데이터 사용
            date=request.date
        )
        
        # 4. 응답 구성
        return SafetyGuideResponse(
            location=safety_guide["location"],
            date=safety_guide["date"],
            risk_level=safety_guide["risk_level"],
            risk_score=safety_guide["risk_score"],
            summary=safety_guide["summary"],
            warnings=safety_guide["warnings"],
            recommendations=safety_guide["recommendations"],
            emergency_contacts=safety_guide["emergency_contacts"],
            ocean_data=ocean_data,
            station_info={
                "obs_code": station.obs_code,
                "obs_name": station.obs_name,
                "station_latitude": station.latitude,
                "station_longitude": station.longitude,
                "distance_km": station.distance_km
            }
        )
        
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        import traceback
        error_detail = f"Error generating safety guide: {exc}\n{traceback.format_exc()}"
        print(f"[ERROR] {error_detail}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
