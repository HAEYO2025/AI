# LangChain LLM Streaming API

LangChain과 FastAPI를 사용한 LLM 스트리밍 질의 API입니다.

## 주요 기능

- LangChain을 이용한 LLM 클래스 정의
- FastAPI를 통한 RESTful API 제공
- Server-Sent Events를 이용한 실시간 스트리밍 응답
- 일반 질의 및 스트리밍 질의 모두 지원
- CORS 지원으로 웹 클라이언트 연동 가능

## 프로젝트 구조

```
haeyo-ai/
├── app/
│   ├── __init__.py
│   ├── llm.py          # LangChain LLM 클래스
│   ├── models.py       # Pydantic 모델
│   └── main.py         # FastAPI 애플리케이션
├── requirements.txt    # 의존성 패키지
├── .env.example       # 환경변수 예제
├── .env               # 환경변수 (생성 필요)
├── test_client.py     # 테스트 클라이언트
├── run.sh             # 서버 실행 스크립트
└── README.md
```

## 설치 및 설정

### 1. 가상환경 생성 및 활성화

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 환경변수 설정

`.env.example` 파일을 복사하여 `.env` 파일을 생성하고, API 키를 설정합니다.

```bash
cp .env .env
```

`.env` 파일 내용:
```
OPENAI_API_KEY=your-actual-api-key
MODEL_NAME=gpt-4-turbo-preview
TEMPERATURE=0.7
MAX_TOKENS=2048
```

## 서버 실행

### 방법 1: 스크립트 사용

```bash
chmod +x run.sh
./run.sh
```

### 방법 2: 직접 실행

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

서버가 실행되면 http://localhost:8000 에서 접근 가능합니다.

## API 엔드포인트

### 1. 루트 (/)
- **메소드**: GET
- **설명**: API 정보 확인

### 2. 헬스 체크 (/health)
- **메소드**: GET
- **설명**: 서비스 상태 확인

### 3. 스트리밍 질의 (/api/query/stream)
- **메소드**: POST
- **Content-Type**: application/json
- **설명**: Server-Sent Events를 통한 스트리밍 응답

**요청 예시:**
```json
{
  "prompt": "파이썬으로 피보나치 수열을 생성하는 함수를 작성해줘",
  "system_message": "당신은 전문 프로그래머입니다.",
  "temperature": 0.7,
  "max_tokens": 2048
}
```

**응답:** Server-Sent Events 스트림
```
data: {"content": "def"}
data: {"content": " fibonacci"}
...
data: {"done": true}
```

### 4. 일반 질의 (/api/query)
- **메소드**: POST
- **Content-Type**: application/json
- **설명**: 전체 응답을 한 번에 반환

**요청 예시:**
```json
{
  "prompt": "Hello world를 출력하는 파이썬 코드를 작성해줘",
  "temperature": 0.5
}
```

**응답 예시:**
```json
{
  "response": "print('Hello world')",
  "model": "gpt-4-turbo-preview"
}
```

## 테스트

테스트 클라이언트를 실행하여 API를 테스트할 수 있습니다:

```bash
python test_client.py
```

## cURL 예제

### 스트리밍 질의
```bash
curl -X POST http://localhost:8000/api/query/stream \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "파이썬이란 무엇인가?",
    "temperature": 0.7
  }'
```

### 일반 질의
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Hello world를 출력하는 코드",
    "temperature": 0.5
  }'
```

## 웹 클라이언트 예제

```javascript
// 스트리밍 질의 예제
const eventSource = new EventSource('http://localhost:8000/api/query/stream');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.content) {
    console.log(data.content);
  } else if (data.done) {
    console.log('완료');
    eventSource.close();
  } else if (data.error) {
    console.error('에러:', data.error);
    eventSource.close();
  }
};
```

## API 문서

서버 실행 후 다음 URL에서 자동 생성된 API 문서를 확인할 수 있습니다:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 주의사항

- OpenAI API 키가 필요합니다
- 스트리밍 응답은 Server-Sent Events를 사용합니다
- CORS가 모든 origin에 대해 열려있으므로, 프로덕션 환경에서는 적절히 제한해야 합니다

## 라이선스

MIT
