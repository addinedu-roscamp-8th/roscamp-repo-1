# Voice Order API Server

OpenAI API 기반 음성 주문 서버. STT, TTS, 웨이크업(주문 시작 의도), 펑션 콜링, 파이프라인, Agent, A2A 엔드포인트 제공.

## 요구사항

- Python 3.10+
- OpenAI API Key

## 설치

```bash
cd voice_processing_server
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 설정 (API Key 등)

1. `config/.env.example` 을 참고해 프로젝트 루트에 `.env` 생성.
2. `OPENAI_API_KEY=sk-...` 설정.
3. `.env` 는 `.gitignore` 에 포함되어 있으므로 저장소에 올라가지 않음.

```bash
cp config/.env.example .env
# .env 편집하여 OPENAI_API_KEY 입력
```

## 실행

```bash
python run.py
# 또는
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- API 문서: http://localhost:8000/docs
- 테스트 GUI: http://localhost:8000/static/index.html

## 프로젝트 구조

```
voice_processing_server/
├── app/
│   ├── main.py           # FastAPI 앱
│   ├── config/           # 설정 로드
│   ├── core/             # STT, TTS, wakeword, function_calling
│   ├── pipeline/         # voice_pipeline
│   ├── agent/            # Agent 진입점
│   ├── a2a/              # A2A 진입점
│   ├── api/               # 라우터 (stt, tts, wakeword, functions, pipeline, agent, a2a)
│   └── schemas/
├── config/
│   ├── .env.example
│   ├── wakeword_reference.yaml   # 웨이크 워드 목록
│   └── wakeword_prompt.yaml      # 웨이크 워드 의도 판별 프롬프트
├── static/
│   └── index.html        # 테스트 GUI
├── docs/
│   └── API.md            # API 문서
├── .env                  # 비밀 (gitignore)
├── .gitignore
├── requirements.txt
└── run.py
```

## API 요약

| 기능 | 메서드 | 경로 |
|------|--------|------|
| STT | POST | /stt/ |
| TTS | POST | /tts/, /tts/json |
| 웨이크업(텍스트) | POST | /wakeword/check/text |
| 웨이크업(오디오) | POST | /wakeword/check/audio |
| 웨이크업 레퍼런스 | GET | /wakeword/reference |
| 펑션 호출 | POST | /functions/call |
| 펑션 목록 | GET | /functions/list |
| 파이프라인 | POST | /pipeline/run |
| Agent(오디오) | POST | /agent/voice |
| Agent(텍스트) | POST | /agent/voice/text |
| A2A(오디오) | POST | /a2a/voice |
| A2A(텍스트) | POST | /a2a/voice/text |

상세: [docs/API.md](docs/API.md) 또는 `/docs`.

## 429 발생 시 / 플랫폼에 호출 이력이 안 보일 때

**증상**: TTS/STT 호출 시 `429 Too Many Requests` 가 나오는데, OpenAI Platform 사용량 대시보드에는 호출 이력이 없다.

**가능한 원인**

1. **거절된 요청은 사용량에 안 잡힘**  
   429는 “한도 초과로 요청이 거절된 것”이라, **정상 처리된 요청만** 사용량/비용으로 집계됩니다. 그래서 대시보드에는 성공한 호출만 보이고, 429로 막힌 요청은 사용 이력에 안 나올 수 있습니다.

2. **다른 API 키 사용**  
   서버가 쓰는 키와 플랫폼에서 보고 있는 계정/키가 다를 수 있습니다.  
   - **확인**: `GET http://localhost:8000/debug/api-key-check` 호출 시 `key_suffix`(키 끝 4자)가 반환됩니다.  
   - [OpenAI API keys](https://platform.openai.com/api-keys) 에서 사용 중인 키 끝 4자와 동일한지 확인하세요.  
   - `.env` 의 `OPENAI_API_KEY` 가 프로젝트 루트(`voice_processing_server/`)의 `.env` 에 있는지, 다른 `.env` 를 읽고 있지는 않은지 확인하세요.

3. **대시보드 지연**  
   사용량/비용 대시보드는 수 분~몇 시간 지연될 수 있습니다.  
   - [Usage](https://platform.openai.com/usage), [Rate limits](https://platform.openai.com/account/limits) 를 함께 확인하세요.

4. **TTS/STT 한도**  
   무료 체험 또는 Tier 1 구간에서는 분당 요청 수(RPM) 한도가 낮습니다.  
   - [Rate limits](https://platform.openai.com/account/limits) 에서 Audio(TTS 등) 한도 확인.  
   - 한도 상향은 유료 결제·사용량 구간 상승으로 가능합니다.

**요약**: 429가 나오면 “요청은 갔지만 한도 때문에 거절된 것”이라, 플랫폼에 호출 이력이 안 보이는 경우가 있습니다. `GET /debug/api-key-check` 로 키가 의도한 계정 것인지 먼저 확인하는 것을 권장합니다.
