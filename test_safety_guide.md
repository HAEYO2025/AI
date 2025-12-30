# 해양 안전 가이드 API 테스트 가이드

## 1. 서버 실행

```bash
# .env 파일에 필요한 환경 변수 설정 확인
# - OPENAI_API_KEY
# - BADA_NURI_OPENAPI_SERVICE_KEY

# 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 2. API 엔드포인트

### 2.1 안전 가이드 조회 (GET /api/ocean/safety-guide)

위도, 경도를 받아서 해양 데이터를 조회하고 LLM을 통해 안전 가이드를 생성합니다.

**요청 예시:**

```bash
curl -X GET "http://localhost:8000/api/ocean/safety-guide?latitude=37.5665&longitude=126.9780&date=20240115&data_type=tideObs&station_data_type=ObsServiceObj"
```

**파라미터:**
- `latitude` (필수): 위도 (예: 37.5665)
- `longitude` (필수): 경도 (예: 126.9780)
- `date` (필수): 날짜 (YYYYMMDD 형식, 예: 20240115)
- `data_type` (선택, 기본값: tideObs): KHOA 데이터 타입
- `station_data_type` (선택, 기본값: ObsServiceObj): 관측소 조회 타입

**응답 예시:**

```json
{
  "location": {
    "latitude": 37.5665,
    "longitude": 126.9780
  },
  "date": "20240115",
  "risk_level": "medium",
  "risk_score": 65,
  "summary": "현재 조위가 상승 중이며, 오후 3시경 만조가 예상됩니다. 해안가 접근 시 주의가 필요합니다.",
  "warnings": [
    "만조 시간대 해안가 접근 주의",
    "높은 파도 예상"
  ],
  "recommendations": [
    "안전 거리 유지",
    "구명조끼 착용",
    "기상 정보 지속 확인"
  ],
  "emergency_contacts": [
    "119",
    "해양경찰 122"
  ],
  "ocean_data": {
    // KHOA API 원본 응답
  },
  "station_info": {
    "obs_code": "DT_0001",
    "obs_name": "인천",
    "station_latitude": 37.4563,
    "station_longitude": 126.5920,
    "distance_km": 5.2
  }
}
```

### 2.2 조위 데이터만 조회 (GET /api/ocean/tide)

LLM 분석 없이 조위 데이터만 조회합니다.

```bash
curl -X GET "http://localhost:8000/api/ocean/tide?latitude=37.5665&longitude=126.9780&date=20240115&data_type=tideObs"
```

## 3. 위험도 수준 (risk_level)

- **low** (0-39): 안전, 일반적인 주의사항 준수
- **medium** (40-69): 주의 필요, 제한적 활동만 가능
- **high** (70-89): 매우 위험, 해양 활동 금지
- **critical** (90-100): 즉시 대피 필요, 생명 위협

## 4. 테스트 시나리오

### 서울 (한강)
```bash
curl -X GET "http://localhost:8000/api/ocean/safety-guide?latitude=37.5665&longitude=126.9780&date=20250115"
```

### 부산 (해운대)
```bash
curl -X GET "http://localhost:8000/api/ocean/safety-guide?latitude=35.1586&longitude=129.1603&date=20250115"
```

### 인천 (영종도)
```bash
curl -X GET "http://localhost:8000/api/ocean/safety-guide?latitude=37.4563&longitude=126.4407&date=20250115"
```

## 5. 주의사항

1. **환경 변수 설정**: `.env` 파일에 다음이 설정되어 있어야 합니다:
   - `OPENAI_API_KEY`: OpenAI API 키
   - `BADA_NURI_OPENAPI_SERVICE_KEY`: 바다누리 Open API 서비스 키

2. **날짜 형식**: 날짜는 `YYYYMMDD` 형식으로 입력해야 합니다 (예: 20250115)

3. **좌표 정확도**: 위도/경도는 소수점 4자리 정도의 정확도를 권장합니다

4. **API 제한**: KHOA API와 OpenAI API의 사용량 제한을 확인하세요

## 6. 에러 처리

- **503 Service Unavailable**: KHOA client 또는 LLM service가 초기화되지 않음
  - 환경 변수 확인 필요
  
- **400 Bad Request**: 잘못된 파라미터 또는 관측소를 찾을 수 없음
  - 좌표 또는 날짜 형식 확인
  
- **500 Internal Server Error**: LLM 분석 중 오류 발생
  - 서버 로그 확인
