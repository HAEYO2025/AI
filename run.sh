#!/bin/bash

# 서버 실행 스크립트

# 가상환경 활성화 (있는 경우)
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 환경 변수 체크
if [ ! -f ".env" ]; then
    echo "⚠️  .env 파일이 없습니다. .env.example을 참고하여 .env 파일을 생성하세요."
    exit 1
fi

# 서버 실행
echo "🚀 서버를 시작합니다..."
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
