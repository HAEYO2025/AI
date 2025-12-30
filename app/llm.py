"""
LLM 베이스 클래스 및 구현체
"""
from typing import AsyncIterator, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult
import os
from dotenv import load_dotenv
from abc import ABC, abstractmethod

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


class LLM(ABC):
    """LLM 베이스 클래스"""

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

    @abstractmethod
    def get_system_message(self) -> str:
        """시스템 메시지를 반환 (서브클래스에서 구현)"""
        pass

    @abstractmethod
    def create_prompt(self, **kwargs) -> str:
        """프롬프트를 생성 (서브클래스에서 구현)"""
        pass

    async def generate_stream(self, **kwargs) -> AsyncIterator[str]:
        """
        스트리밍 방식으로 LLM 응답 생성

        Args:
            **kwargs: create_prompt에 전달될 인자

        Yields:
            생성된 토큰들
        """
        try:
            prompt = self.create_prompt(**kwargs)
            system_message = self.get_system_message()

            print(f"[LLM DEBUG] 프롬프트 생성 완료 (길이: {len(prompt)})")
            print(f"[LLM DEBUG] 시스템 메시지 생성 완료 (길이: {len(system_message)})")

            messages = [
                SystemMessage(content=system_message),
                HumanMessage(content=prompt)
            ]

            print(f"[LLM DEBUG] OpenAI API 호출 시작...")
            chunk_count = 0
            empty_chunks = 0

            async for chunk in self.llm.astream(messages):
                chunk_count += 1

                # 청크 전체 정보 출력
                chunk_info = {
                    'content': chunk.content if hasattr(chunk, 'content') else None,
                    'additional_kwargs': chunk.additional_kwargs if hasattr(chunk, 'additional_kwargs') else None,
                    'response_metadata': chunk.response_metadata if hasattr(chunk, 'response_metadata') else None,
                    'id': chunk.id if hasattr(chunk, 'id') else None,
                }
                print(f"[LLM DEBUG] 청크 #{chunk_count}: {chunk_info}")

                if chunk.content:
                    print(f"[LLM DEBUG] 청크 내용 전송: {len(chunk.content)}자")
                    yield chunk.content
                else:
                    empty_chunks += 1

            print(f"[LLM DEBUG] OpenAI API 응답 완료 (총 청크: {chunk_count}, 비어있는 청크: {empty_chunks})")

        except Exception as e:
            import traceback
            error_msg = f"[LLM ERROR] {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            raise

    async def generate(self, **kwargs) -> str:
        """
        일반 방식으로 LLM 응답 생성

        Args:
            **kwargs: create_prompt에 전달될 인자

        Returns:
            생성된 전체 응답
        """
        prompt = self.create_prompt(**kwargs)
        system_message = self.get_system_message()

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=prompt)
        ]

        response = await self.llm.ainvoke(messages)
        return response.content


class ScenarioSimulationLLM(LLM):
    """재난 시나리오 시뮬레이션 LLM"""

    def get_system_message(self) -> str:
        """시스템 메시지 정의 (사용 안 함 - 각 메서드에서 정의)"""
        return ""

    def create_prompt(self, **kwargs) -> str:
        """프롬프트 생성 (사용 안 함 - 각 메서드에서 정의)"""
        return ""

    async def generate_situation(
        self,
        scenario_title: str,
        scenario_description: str,
        scenario_start_date: str,
        report_title: str,
        report_description: str,
        report_latitude: float,
        report_longitude: float,
        report_date: str,
        history: Optional[list] = None  # list[TurnHistory]
    ) -> AsyncIterator[str]:
        """상황 생성 (스트리밍) - 전체 히스토리를 고려"""

        if not history or len(history) == 0:
            # 초기 상황 - 히스토리가 없을 때
            system_message = "당신은 재난 상황을 1인칭 시점으로 생생하게 전달하는 작가입니다. 사용자가 그 상황 속 당사자가 된 것처럼 느끼도록 묘사하세요."
            prompt = f"""지금 당신은 다음 위치에 있습니다:
- 시각: {report_date}
- 장소: 위도 {report_latitude}, 경도 {report_longitude}

당신이 직접 목격하고 있는 상황:
{report_description}

이것은 '{scenario_title}' 상황입니다. ({scenario_description})

당신이 바로 그 현장에서 겪고 있는 상황을 1인칭 시점으로 간결하게 묘사하세요.

다음을 포함하여 2-4문장으로 작성:
- 당신 주변에서 벌어지고 있는 일
- 당신이 느끼는 즉각적인 위험
- 당신이 지금 해야 할 것 같은 생각"""

        else:
            # 이후 상황 - 전체 히스토리를 고려
            system_message = "당신은 재난 상황 시뮬레이션 작가입니다. 사용자의 모든 선택과 그 결과를 일관되게 유지하면서, 가장 최근 선택의 구체적인 결과를 보여주세요."
            
            # 히스토리를 텍스트로 구성
            history_text = ""
            for i, turn in enumerate(history, 1):
                history_text += f"\n[{i}번째 상황]\n{turn['situation']}\n→ 당신의 선택: {turn['choice']}\n"
            
            prompt = f"""=== 시나리오 정보 ===
재난 유형: {scenario_title}
설명: {scenario_description}
시작 시각: {scenario_start_date}
현재 위치: 위도 {report_latitude}, 경도 {report_longitude}

=== 지금까지의 경과 ===
{history_text}

=== 지침 ===
위 히스토리의 **모든 선택과 결과**를 고려하여, 가장 최근 선택("{history[-1]['choice']}")의 직접적인 결과와 새로운 상황을 묘사하세요.

1인칭 시점으로 2-4문장으로 작성하되, 반드시 다음을 포함:
1. 가장 최근 선택한 행동의 실행 과정과 즉각적인 결과
2. 이전 선택들의 영향이 계속 유지되고 있음을 암시
3. 상황이 어떻게 변했는지 (개선/악화)
4. 새롭게 발생한 문제나 기회

**중요:** 이전에 선택한 행동들(예: 119 신고, 안전한 위치 확보 등)은 여전히 유효하며, 그 영향이 현재 상황에도 반영되어야 합니다."""

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=prompt)
        ]

        async for chunk in self.llm.astream(messages):
            if chunk.content:
                yield chunk.content

    async def generate_choices(
        self,
        current_situation: str,
        history: Optional[list] = None
    ) -> list[str]:
        """선택지 3개 생성 (비스트리밍) - 전체 맥락 고려"""

        system_message = "당신은 재난 상황 전문가입니다. 일반인이 그 상황에서 실제로 취할 수 있는 현실적인 행동 옵션을 제시하세요."
        
        # 히스토리가 있으면 맥락 추가
        history_context = ""
        if history and len(history) > 0:
            history_context = "\n=== 지금까지의 경과 ===\n"
            for i, turn in enumerate(history, 1):
                history_context += f"{i}. {turn['choice']} → {turn['situation'][:50]}...\n"
            history_context += "\n이전 선택들(예: 119 신고, 안전 확보 등)은 여전히 유효하며, 선택지는 이를 고려해야 합니다.\n"

        prompt = f"""{history_context}
=== 현재 상황 ===
{current_situation}

지금 당신이 직접 할 수 있는 구체적이고 현실적인 행동 3가지를 제시하세요.

반드시 다음 형식으로만 작성하세요:
1. [첫 번째 행동]
2. [두 번째 행동]
3. [세 번째 행동]

각 행동은:
- 일반인이 현장에서 직접 할 수 있는 것
- 현재 상황과 이전 행동들을 고려한 것
- 한 줄로 간결하게 작성
예: "119에 상황을 업데이트한다", "높은 곳으로 이동한다", "주변 사람들과 협력한다" 등"""

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=prompt)
        ]

        # 한 번에 생성
        response = await self.llm.ainvoke(messages)
        full_text = response.content

        # 선택지 파싱
        choices = []
        lines = full_text.strip().split('\n')

        for line in lines:
            line = line.strip()
            # "1.", "2.", "3." 또는 "1)", "2)", "3)" 형태의 선택지 찾기
            if line and (line.startswith('1.') or line.startswith('1)')):
                choices.append(line[2:].strip())
            elif line and (line.startswith('2.') or line.startswith('2)')):
                choices.append(line[2:].strip())
            elif line and (line.startswith('3.') or line.startswith('3)')):
                choices.append(line[2:].strip())

        # 정확히 3개가 아니면 원본 텍스트를 3등분
        if len(choices) != 3:
            # fallback: 전체 텍스트를 그냥 하나의 선택지로
            choices = [full_text, "", ""]

        return choices[:3]  # 최대 3개만 반환

    async def generate_survival_rate(
        self,
        scenario_title: str,
        current_situation: str,
        history: Optional[list] = None
    ) -> dict:
        """
        현재 상황을 분석하여 생존률과 변화량을 계산
        
        Returns:
            {
                "survival_rate": 75,  // 현재 생존률 (0-100)
                "change": "+15"       // 이전 대비 변화 (첫 턴은 "0")
            }
        """
        system_message = "당신은 재난 안전 전문가입니다. 재난 상황의 심각성을 과소평가하지 말고, 매우 엄격하고 현실적인 기준으로 생존 확률을 평가하세요. 낙관적 편향을 배제하고 객관적으로 평가하세요."
        
        history_context = ""
        if history and len(history) > 0:
            last_choice = history[-1]['choice']
            history_context = f"\n이전 상황: {history[-1]['situation'][:100]}\n선택한 행동: {last_choice}\n"
        
        prompt = f"""=== 시나리오 ===
재난 유형: {scenario_title}
{history_context}
=== 현재 상황 ===
{current_situation}

위 상황을 분석하여 다음을 JSON 형식으로 답하세요:
{{
  "survival_rate": <0-100 사이의 정수>,
  "change": "<+/- 숫자>"
}}

평가 기준 (매우 엄격하게 평가하세요):
- 90-100: 구조 완료 또는 완전히 안전한 장소 도착 (거의 불가능)
- 75-89: 전문 구조대와 함께 있고, 안전한 대피 경로 확보
- 60-74: 적절한 대응을 했으나 여전히 위험 요소 존재
- 45-59: 위험한 상황, 잘못된 선택 시 생명 위협
- 30-44: 매우 위험, 즉각적 대응 없으면 사망 가능
- 15-29: 극도로 위험, 생존 가능성 낮음
- 0-14: 거의 사망 확정 상황

**중요:** 이것은 재난 상황입니다. 낙관적으로 평가하지 마세요.
- 초기 상황: 대부분 30-50%
- 좋은 선택 후: 50-70%
- 최선의 대응: 70-85%
- 100%는 구조 완료 시에만 가능

예시:
- "물이 차오르는 지하 주차장": 35% (매우 위험)
- "119 신고 완료, 5분 내 도착 예정": 55% (여전히 위험)
- "구조대 도착, 안전한 곳으로 이동 중": 75% (안정적)

change는:
- 첫 턴이면: "0"
- 이후 턴이면: 이전 선택이 생존률에 미친 영향 (+10, -5 등)

**JSON만 출력하세요. 다른 설명은 불필요합니다.**"""

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=prompt)
        ]

        response = await self.llm.ainvoke(messages)
        content = response.content.strip()
        
        # JSON 파싱
        import json
        try:
            # JSON 블록 추출 (```json ... ``` 형태일 수 있음)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            return {
                "survival_rate": result.get("survival_rate", 50),
                "change": result.get("change", "0")
            }
        except:
            # 파싱 실패 시 기본값
            return {"survival_rate": 50, "change": "0"}

    async def generate_feedback(
        self,
        scenario_title: str,
        chosen_action: str,
        previous_situation: str,
        current_situation: str,
        available_choices: list[str]
    ) -> dict:
        """
        이전 선택에 대한 피드백 생성
        
        Returns:
            {
                "chosen_action": "119에 신고한다",
                "evaluation": "excellent",  # excellent/good/neutral/risky/dangerous
                "comment": "적절한 선택입니다...",
                "better_choice": "높은 곳으로 이동한다",  # 또는 None
                "survival_impact": "+15"
            }
        """
        system_message = "당신은 재난 안전 교육 전문가입니다. 사용자의 선택을 평가하고 건설적인 피드백을 제공하세요."
        
        prompt = f"""=== 시나리오 ===
재난 유형: {scenario_title}

=== 이전 상황 ===
{previous_situation}

=== 선택 가능했던 행동들 ===
{', '.join(available_choices)}

=== 사용자가 선택한 행동 ===
{chosen_action}

=== 결과 (현재 상황) ===
{current_situation}

위 선택을 평가하여 다음을 JSON 형식으로 답하세요:
{{
  "chosen_action": "{chosen_action}",
  "evaluation": "<excellent/good/neutral/risky/dangerous>",
  "comment": "<1-2문장의 전문가 코멘트>",
  "better_choice": "<더 나은 선택이 있었다면 그것, 없으면 null>",
  "survival_impact": "<+/- 숫자>"
}}

평가 기준:
- excellent: 최선의 선택, 생존률 크게 향상
- good: 적절한 선택, 생존률 향상
- neutral: 무난한 선택, 큰 변화 없음
- risky: 위험한 선택, 생존률 하락
- dangerous: 매우 위험한 선택, 생존률 크게 하락

comment는 짧고 명확하게, 왜 그런 평가인지 설명하세요.
better_choice는 선택한 것보다 더 나은 선택이 명백히 있었을 때만 제시하세요.

**JSON만 출력하세요. 다른 설명은 불필요합니다.**"""

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=prompt)
        ]

        response = await self.llm.ainvoke(messages)
        content = response.content.strip()
        
        # JSON 파싱
        import json
        try:
            # JSON 블록 추출
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            return {
                "chosen_action": result.get("chosen_action", chosen_action),
                "evaluation": result.get("evaluation", "neutral"),
                "comment": result.get("comment", "선택을 완료했습니다."),
                "better_choice": result.get("better_choice"),
                "survival_impact": result.get("survival_impact", "0")
            }
        except:
            # 파싱 실패 시 기본값
            return {
                "chosen_action": chosen_action,
                "evaluation": "neutral",
                "comment": "선택을 완료했습니다.",
                "better_choice": None,
                "survival_impact": "0"
            }


    async def generate_safety_guide(
        self,
        latitude: float,
        longitude: float,
        ocean_data: dict,
        date: str
    ) -> dict:
        """
        해양 데이터를 기반으로 안전 가이드 생성
        
        Args:
            latitude: 위도
            longitude: 경도
            ocean_data: KHOA API에서 받은 해양 데이터 (조위 등)
            date: 조회 날짜
            
        Returns:
            {
                "location": {"latitude": 37.5, "longitude": 126.9},
                "date": "20240115",
                "risk_level": "medium",  # low/medium/high/critical
                "risk_score": 65,  # 0-100
                "summary": "현재 조위가 상승 중입니다...",
                "warnings": ["높은 파도 주의", "만조 시간대 접근 금지"],
                "recommendations": ["안전 거리 유지", "구명조끼 착용"],
                "emergency_contacts": ["119", "해양경찰 122"]
            }
        """
        system_message = """당신은 해양 안전 전문가입니다. 
해양 데이터를 분석하여 일반인이 이해하기 쉬운 안전 가이드를 제공하세요.
과학적 근거를 바탕으로 하되, 전문 용어는 최소화하고 구체적인 행동 지침을 제시하세요."""
        
        # ocean_data를 문자열로 변환 (요약된 형식)
        import json
        ocean_data_str = json.dumps(ocean_data, ensure_ascii=False, indent=2)
        
        # 통계 정보 추출
        stats = ocean_data.get("statistics", {})
        max_tide = stats.get("max_tide_cm", "N/A")
        min_tide = stats.get("min_tide_cm", "N/A")
        avg_tide = stats.get("avg_tide_cm", "N/A")
        current_tide = stats.get("current_tide_cm", "N/A")
        trend = stats.get("trend", "unknown")
        
        # 만조/간조 정보
        high_tides = ocean_data.get("high_tides", [])
        low_tides = ocean_data.get("low_tides", [])
        
        trend_kr = {"rising": "상승 중", "falling": "하락 중", "stable": "안정적"}.get(trend, "알 수 없음")
        
        prompt = f"""=== 위치 정보 ===
위도: {latitude}
경도: {longitude}
날짜: {date}

=== 조위 데이터 요약 ===
현재 조위: {current_tide}cm
조위 변화 추세: {trend_kr}
최고 조위: {max_tide}cm
최저 조위: {min_tide}cm
평균 조위: {avg_tide}cm

만조 시간대: {json.dumps(high_tides[:3], ensure_ascii=False) if high_tides else "데이터 없음"}
간조 시간대: {json.dumps(low_tides[:3], ensure_ascii=False) if low_tides else "데이터 없음"}

전체 데이터:
{ocean_data_str}

위 해양 데이터를 분석하여 안전 가이드를 생성하세요.

다음 JSON 형식으로 답변하세요:
{{
  "location": {{
    "latitude": {latitude},
    "longitude": {longitude}
  }},
  "date": "{date}",
  "risk_level": "<low/medium/high/critical>",
  "risk_score": <0-100 사이의 정수>,
  "summary": "<해양 상황 요약 (2-3문장)>",
  "warnings": ["<주의사항 1>", "<주의사항 2>", ...],
  "recommendations": ["<권장사항 1>", "<권장사항 2>", ...],
  "emergency_contacts": ["119", "해양경찰 122"]
}}

위험도 평가 기준:
- critical (90-100): 즉시 대피 필요, 생명 위협
- high (70-89): 매우 위험, 해양 활동 금지
- medium (40-69): 주의 필요, 제한적 활동만 가능
- low (0-39): 안전, 일반적인 주의사항 준수

조위 데이터 분석 시 고려사항:
1. 만조/간조 시간과 현재 시각의 관계
2. 조위 높이의 변화 추세 (상승/하락)
3. 이상 조위 여부 (평균 대비)
4. 해양 활동 가능 시간대

warnings는 구체적인 위험 요소를 나열하세요 (예: "만조 시간대 접근 금지", "높은 파도 예상").
recommendations는 실행 가능한 행동 지침을 제시하세요 (예: "안전 거리 유지", "구명조끼 착용").

**JSON만 출력하세요. 다른 설명은 불필요합니다.**"""

        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=prompt)
        ]

        response = await self.llm.ainvoke(messages)
        content = response.content.strip()
        
        # JSON 파싱
        import json
        try:
            # JSON 블록 추출
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            # 기본값 설정
            return {
                "location": result.get("location", {"latitude": latitude, "longitude": longitude}),
                "date": result.get("date", date),
                "risk_level": result.get("risk_level", "medium"),
                "risk_score": result.get("risk_score", 50),
                "summary": result.get("summary", "해양 데이터를 분석했습니다."),
                "warnings": result.get("warnings", []),
                "recommendations": result.get("recommendations", []),
                "emergency_contacts": result.get("emergency_contacts", ["119", "해양경찰 122"])
            }
        except Exception as e:
            # 파싱 실패 시 기본값
            print(f"[ERROR] Safety guide JSON parsing failed: {e}")
            return {
                "location": {"latitude": latitude, "longitude": longitude},
                "date": date,
                "risk_level": "medium",
                "risk_score": 50,
                "summary": "해양 데이터 분석 중 오류가 발생했습니다.",
                "warnings": ["데이터 분석 실패"],
                "recommendations": ["전문가와 상담하세요"],
                "emergency_contacts": ["119", "해양경찰 122"]
            }


# 하위 호환성을 위한 별칭
class LLMService(ScenarioSimulationLLM):
    """하위 호환성을 위한 LLMService 별칭"""
    pass
