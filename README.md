# Committee Agent (Document AI Platform)

이 프로젝트는 문서 교정(오타, 논리, 스타일) 및 PDF 일괄 변환 기능을 제공하는 AI 에이전트 서비스입니다.

## 주요 기능
1. **문서 복합 분석**: Google Gemini Pro를 활용한 오타, 논리적 오류, 비즈니스 영어 스타일 교정.
2. **PDF 변환**: LibreOffice 엔진을 활용한 docx/pptx -> pdf 고품질 일괄 변환.

## 📂 프로젝트 구조
```bash
.
├── src/                # 소스 코드 디렉토리
│   ├── app.py          # Streamlit 메인 진입점
│   ├── pdf_converter.py   
│   ├── read_docx_util.py        
│   ├── highlighting.py
│   └── sample_data/
├── run_streamlit.py    # docker 배포 시 미사용, Ngrok 공식 이미지를 통해 외부 url 터널 연결
├── Dockerfile          # 도커 빌드 설정 (LibreOffice + 한글폰트 포함)
├── docker-compose.yml  # 서버용 Docker 배포
├── requirements.txt    # 의존성 목록
└── .env                # (필수) API Key 설정 파일
```

## 실행 방법
### -d 옵션은 'Detached'(백그라운드) 모드입니다.
### 터미널을 꺼도 서버는 계속 돌아갑니다.
```
docker-compose up -d --build
docker-compose down # 서버 종료 시

```

## 외부 접속 URL 확인 방법
```
웹 브라우저로 확인 : 내 컴퓨터 http://localhost:4040 에 접속
Status 항목 -> https://xxxx-xxxx.ngrok-free.app가 외부에서 접속 가능한 주소
```

