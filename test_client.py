"""
API 테스트 클라이언트
"""
import httpx
import asyncio
import json


async def test_streaming():
    """스트리밍 엔드포인트 테스트"""
    print("=" * 50)
    print("스트리밍 테스트 시작")
    print("=" * 50)

    url = "http://localhost:8000/api/query/stream"
    payload = {
        "prompt": "파이썬으로 간단한 HTTP 서버를 만드는 방법을 설명해줘",
        "system_message": "당신은 친절한 프로그래밍 튜터입니다.",
        "temperature": 0.7,
        "max_tokens": 1024
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            print(f"응답 상태: {response.status_code}\n")

            if response.status_code == 200:
                print("스트리밍 응답:")
                print("-" * 50)

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # "data: " 제거
                        try:
                            data = json.loads(data_str)

                            if "content" in data:
                                print(data["content"], end="", flush=True)
                            elif "done" in data:
                                print("\n" + "-" * 50)
                                print("스트리밍 완료")
                            elif "error" in data:
                                print(f"\n에러: {data['error']}")

                        except json.JSONDecodeError:
                            continue
            else:
                print(f"에러: {await response.aread()}")

    print()


async def test_normal():
    """일반 엔드포인트 테스트"""
    print("=" * 50)
    print("일반 질의 테스트 시작")
    print("=" * 50)

    url = "http://localhost:8000/api/query"
    payload = {
        "prompt": "Hello world를 출력하는 파이썬 코드를 작성해줘",
        "temperature": 0.5
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)

        print(f"응답 상태: {response.status_code}\n")

        if response.status_code == 200:
            result = response.json()
            print("응답:")
            print("-" * 50)
            print(result["response"])
            print("-" * 50)
            print(f"사용 모델: {result['model']}")
        else:
            print(f"에러: {response.text}")

    print()


async def test_health():
    """헬스 체크 테스트"""
    print("=" * 50)
    print("헬스 체크 테스트")
    print("=" * 50)

    url = "http://localhost:8000/health"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        print(f"응답: {response.json()}\n")


async def main():
    """메인 함수"""
    try:
        # 헬스 체크
        await test_health()

        # 일반 질의 테스트
        await test_normal()

        # 스트리밍 질의 테스트
        await test_streaming()

    except httpx.ConnectError:
        print("서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
        print("서버 실행: python -m uvicorn app.main:app --reload")
    except Exception as e:
        print(f"예외 발생: {e}")


if __name__ == "__main__":
    asyncio.run(main())
