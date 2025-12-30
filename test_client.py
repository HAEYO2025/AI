"""
시나리오 시뮬레이션 API 테스트 클라이언트
"""
import httpx
import asyncio
import json


async def test_scenario_streaming():
    """시나리오 스트리밍 테스트"""
    print("=" * 60)
    print("시나리오 시뮬레이션 스트리밍 테스트")
    print("=" * 60)

    url = "http://localhost:8000/api/query/stream"
    payload = {
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
        }
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            print(f"응답 상태: {response.status_code}\n")

            if response.status_code == 200:
                current_event = None

                async for line in response.aiter_lines():
                    # 이벤트 타입 파싱
                    if line.startswith("event: "):
                        current_event = line[7:].strip()
                        continue

                    # 데이터 파싱
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)

                            if current_event == "situation":
                                print("\n📍 [상황]")
                                print("-" * 60)
                                print(data.get("content", ""))
                                print("-" * 60)

                            elif current_event == "choice1":
                                print("\n🎯 [선택지 1]")
                                print("-" * 60)
                                print(data.get("content", ""))
                                print("-" * 60)

                            elif current_event == "choice2":
                                print("\n🎯 [선택지 2]")
                                print("-" * 60)
                                print(data.get("content", ""))
                                print("-" * 60)

                            elif current_event == "choice3":
                                print("\n🎯 [선택지 3]")
                                print("-" * 60)
                                print(data.get("content", ""))
                                print("-" * 60)

                            elif current_event == "raw":
                                print("\n📄 [원본 응답 (태그 없음)]")
                                print("-" * 60)
                                print(data.get("content", ""))
                                print("-" * 60)

                            elif current_event == "debug":
                                print("\n🔍 [디버그 정보]")
                                print("-" * 60)
                                print(f"청크 수: {data.get('chunk_count', 0)}")
                                print(f"SITUATION 태그 있음: {data.get('has_situation', False)}")
                                print(f"CHOICES 태그 있음: {data.get('has_choices', False)}")
                                print(f"\n응답 미리보기 (처음 500자):")
                                print(data.get("full_response", ""))
                                print("-" * 60)

                            elif current_event == "done":
                                print("\n✅ 스트리밍 완료\n")

                            elif current_event == "error":
                                print(f"\n❌ 에러: {data.get('error', '')}\n")

                        except json.JSONDecodeError as e:
                            print(f"JSON 파싱 에러: {e}")
                            print(f"원본 데이터: {data_str}")
            else:
                print(f"에러: {await response.aread()}")


async def test_scenario_normal():
    """시나리오 일반 요청 테스트"""
    print("\n" + "=" * 60)
    print("시나리오 시뮬레이션 일반 요청 테스트")
    print("=" * 60)

    url = "http://localhost:8000/api/query"
    payload = {
        "scenario": {
            "title": "지진 대응 훈련",
            "description": "규모 5.0 지진 발생 대응",
            "start_date": "2024-08-01"
        },
        "report": {
            "title": "건물 균열 발생",
            "longitude": 127.0276,
            "latitude": 37.4979,
            "description": "강남구 오피스 빌딩 3층에서 벽면 균열 발견, 주민들 대피 중",
            "reported_date": "2024-08-01T09:15:00"
        }
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload)

        print(f"응답 상태: {response.status_code}\n")

        if response.status_code == 200:
            result = response.json()

            print("📍 [상황]")
            print("-" * 60)
            print(result.get("situation", ""))
            print("-" * 60)

            print("\n🎯 [선택지 1]")
            print("-" * 60)
            print(result.get("choice1", ""))
            print("-" * 60)

            print("\n🎯 [선택지 2]")
            print("-" * 60)
            print(result.get("choice2", ""))
            print("-" * 60)

            print("\n🎯 [선택지 3]")
            print("-" * 60)
            print(result.get("choice3", ""))
            print("-" * 60)

            print(f"\n사용 모델: {result.get('model', '')}")
        else:
            print(f"에러: {response.text}")


async def test_with_choice():
    """사용자 선택 후 후속 시나리오 테스트"""
    print("\n" + "=" * 60)
    print("사용자 선택 후 후속 시나리오 테스트")
    print("=" * 60)

    url = "http://localhost:8000/api/query"
    payload = {
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
        "user_choice": "1. 즉시 119 구조대를 현장에 출동시킨다",
        "situation_history": "당신은 서울시 재난안전대책본부 현장 지휘관입니다. 강남역 인근 지하 주차장에서 침수 피해가 발생했다는 제보를 받았습니다."
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload)

        print(f"응답 상태: {response.status_code}\n")

        if response.status_code == 200:
            result = response.json()

            print("📍 [새로운 상황]")
            print("-" * 60)
            print(result.get("situation", ""))
            print("-" * 60)

            print("\n🎯 [새로운 선택지 1]")
            print("-" * 60)
            print(result.get("choice1", ""))
            print("-" * 60)

            print("\n🎯 [새로운 선택지 2]")
            print("-" * 60)
            print(result.get("choice2", ""))
            print("-" * 60)

            print("\n🎯 [새로운 선택지 3]")
            print("-" * 60)
            print(result.get("choice3", ""))
            print("-" * 60)
        else:
            print(f"에러: {response.text}")


async def test_health():
    """헬스 체크 테스트"""
    print("=" * 60)
    print("헬스 체크")
    print("=" * 60)

    url = "http://localhost:8000/health"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        print(f"응답: {response.json()}\n")


async def main():
    """메인 함수"""
    try:
        # 헬스 체크
        await test_health()

        # 스트리밍 테스트
        await test_scenario_streaming()

        # 일반 요청 테스트
        # await test_scenario_normal()

        # 선택 후 후속 시나리오 테스트
        # await test_with_choice()

    except httpx.ConnectError:
        print("❌ 서버에 연결할 수 없습니다.")
        print("서버 실행: python -m uvicorn app.main:app --reload")
    except Exception as e:
        print(f"❌ 예외 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
