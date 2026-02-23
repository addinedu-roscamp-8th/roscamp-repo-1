# Voice Order API 문서

OpenAI API 기반 STT, TTS, 웨이크업, 펑션 콜링, 파이프라인, Agent, A2A 엔드포인트 명세.

---

## 1. 개요

| 항목 | 내용 |
|------|------|
| Base URL | `http://localhost:8000` (또는 배포 주소) |
| 인증 | 현재 API Key는 서버 측 환경 변수(`OPENAI_API_KEY`)에서만 사용. 엔드포인트별 클라이언트 인증 없음. |
| 문서 | Swagger UI: `GET /docs`, ReDoc: `GET /redoc` |
| 테스트 GUI | `GET /static/index.html` |

---

## 2. 공통

- **Content-Type**: JSON 요청 시 `application/json`
- **오디오 업로드**: `multipart/form-data`, 필드명 `file`, 파일명 확장자로 형식 힌트 (예: `audio.webm`, `audio.mp3`)
- **에러**: 4xx/5xx 시 JSON `{"detail": "메시지"}`

---

## 3. STT (Speech-to-Text)

### `POST /stt/`

오디오 파일을 텍스트로 변환. OpenAI Whisper API 사용.

**Request**

- Body: `multipart/form-data`
  - `file`: 오디오 파일 (webm, mp3, wav 등)

**Response (200)**

```json
{ "text": "인식된 텍스트" }
```

---

## 4. TTS (Text-to-Speech)

### `POST /tts/`

텍스트를 음성(MP3)으로 변환. OpenAI Audio API 사용.

**Request**

- Body: `application/json`
```json
{
  "text": "변환할 문장",
  "voice": "alloy",
  "model": "tts-1"
}
```
- `voice`: (선택) alloy | echo | fable | onyx | nova | shimmer
- `model`: (선택) tts-1 | tts-1-hd

**Response (200)**

- Content-Type: `audio/mpeg`
- Body: MP3 바이너리

### `POST /tts/json`

동일 입력. 응답을 JSON으로.

**Response (200)**

```json
{
  "audio_base64": "base64 인코딩된 MP3",
  "media_type": "audio/mpeg"
}
```

---

## 5. Wake word (웨이크업)

### `POST /wakeword/check/text`

텍스트가 주문 시작 웨이크 워드(ORDER_START)인지 판별. 레퍼런스 목록 + LLM 의도 분석.

**Request**

```json
{
  "text": "여기 주문이요.",
  "use_llm": true
}
```

**Response (200)**

```json
{
  "is_wake": true,
  "intent": "ORDER_START",
  "matched_phrase": "여기 주문이요.",
  "text": "여기 주문이요.",
  "llm_intent": "ORDER_START"
}
```

### `POST /wakeword/check/audio`

오디오 파일을 STT 후 웨이크 워드 판별.

**Request**

- Body: `multipart/form-data`, `file`: 오디오
- Query: `use_llm` (bool, 기본 true)

**Response (200)**

- 위 텍스트 판별 필드 + `stt_text`: STT 결과

### `GET /wakeword/reference`

웨이크 워드 레퍼런스 목록 반환 (config/wakeword_reference.yaml).

**Response (200)**

```json
{
  "flat_list": ["여기 주문이요.", ...],
  "categories": { ... }
}
```

---

## 6. Function calling (펑션 콜링)

### `POST /functions/call`

등록된 함수 호출. 테스트 함수는 로그로 동작 여부 확인.

**Request**

```json
{
  "function_name": "test_voice_order",
  "arguments": { "source": "api", "payload": {} }
}
```

**Response (200)**

```json
{
  "success": true,
  "message": "Test function called successfully; check logs for confirmation.",
  "result": { "action": "test_voice_order", "received_args": { ... } },
  "logged": true
}
```

### `GET /functions/list`

호출 가능한 함수 목록 및 스키마.

**Response (200)**

```json
{
  "functions": [
    {
      "name": "test_voice_order",
      "description": "테스트용 음성 주문 펑션. 호출 시 로그로 동작 여부 확인.",
      "parameters": { ... }
    }
  ]
}
```

---

## 7. Pipeline (파이프라인)

### `POST /pipeline/run`

오디오 → STT → 웨이크업 판별 → (웨이크 시 펑션 콜) → TTS 응답.

**Request**

- Body: `multipart/form-data`, `file`: 오디오
- Query:
  - `run_wakeword` (bool, 기본 true)
  - `run_function_on_wake` (bool, 기본 true)
  - `tts_reply` (bool, 기본 true)
  - `use_llm_wakeword` (bool, 기본 true)

**Response (200)**

```json
{
  "success": true,
  "stt_text": "여기 주문이요.",
  "wake": { "is_wake": true, "intent": "ORDER_START", ... },
  "function_called": true,
  "function_result": { ... },
  "tts_audio_base64": "base64 MP3",
  "reply_text": "주문 모드를 시작했습니다. 무엇을 도와드릴까요?",
  "error": null
}
```

---

## 8. Agent

### `POST /agent/voice`

오디오 1회에 대해 Agent 1턴: STT → 웨이크업 → 펑션콜 → TTS.

**Request**

- Body: `multipart/form-data`, `file`: 오디오
- Query: `run_wakeword`, `run_function_on_wake`, `tts_reply` (기본 true)

**Response (200)**

- 구조는 Pipeline 응답과 동일.

### `POST /agent/voice/text`

텍스트 입력만. STT 생략, 웨이크업 → 펑션콜 → TTS.

**Request**

```json
{
  "text": "여기 주문이요.",
  "run_wakeword": true,
  "run_function_on_wake": true,
  "tts_reply": true
}
```

**Response (200)**

- 구조는 Pipeline 응답과 동일.

---

## 9. A2A (Agent-to-Agent)

### `POST /a2a/voice`

다른 에이전트/시스템이 호출. 파이프라인과 동일 + `a2a` 메타데이터.

**Request**

- Body: `multipart/form-data`, `file`: 오디오
- Query: `caller_id`, `request_id`, `run_wakeword`, `run_function_on_wake`, `tts_reply`

**Response (200)**

- Pipeline 필드 + `a2a`: `{ "caller_id": "...", "request_id": "...", "metadata": {} }`

### `POST /a2a/voice/text`

텍스트 입력. 동일 파이프라인 + A2A 메타데이터.

**Request**

```json
{
  "text": "여기 주문이요.",
  "caller_id": "agent-1",
  "request_id": "req-123",
  "metadata": {},
  "run_wakeword": true,
  "run_function_on_wake": true,
  "tts_reply": true
}
```

---

## 10. 기타

### `GET /`

서비스 정보 및 엔드포인트 목록.

### `GET /health`

헬스 체크. `{"status": "ok"}`

---

## 11. 설정 및 보안

- **API Key**: `OPENAI_API_KEY` 환경 변수 또는 프로젝트 루트 `.env` 파일. `.env`는 `.gitignore`에 포함.
- **설정 예시**: `config/.env.example` 참고. 비밀 값은 저장소에 올리지 않음.
- **웨이크 워드 목록**: `config/wakeword_reference.yaml`
- **웨이크 워드 프롬프트**: `config/wakeword_prompt.yaml`
