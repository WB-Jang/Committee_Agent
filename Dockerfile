# 1. Base Image: Python 3.9 Slim (가볍고 안정적)
FROM python:3.9-slim

# 2. 시스템 패키지 설치
# - libreoffice: PDF 변환 기능에 필수 (pdf_converter.py 사용)
# - fonts-nanum: 한글 문서 깨짐 방지
# - git, curl: 유틸리티
RUN apt-get update && apt-get install -y \
    build-essential \
    libreoffice \
    fonts-nanum \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 3. 작업 디렉토리 설정
WORKDIR /app

# 4. Python 라이브러리 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. NLTK 데이터 다운로드 (read_docx_util.py 실행 속도 향상)
RUN python -m nltk.downloader punkt

# 6. 소스 코드 복사
COPY . .

# 7. 포트 노출
EXPOSE 8501

# 8. 환경 변수 설정
ENV PYTHONUNBUFFERED=1

# 9. 실행 명령어
# src 폴더 내의 app.py를 실행합니다.
CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
