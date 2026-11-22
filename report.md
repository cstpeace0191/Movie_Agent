# 002 MVP 구현·테스트 보고서

- **기능**: 002 장면 전환, 사진 캡션, 자막, 배경음악 (`specs/002-transitions-captions-music/`)
- **범위**: MVP = Phase 1 Setup + Phase 2 Foundational + Phase 3 User Story 1(장면 전환)
- **브랜치**: `002-transitions-captions-music`
- **작성일**: 2026-11-21

## 1. 요약

- 장면들을 하나의 타임라인에 배치한 뒤, 정규화·전환·이어 붙이기를 한 번의 FFmpeg 필터 그래프로 처리하는 합성기를 구현했습니다. 기존 `join.py`를 대체합니다.
  - 001에서 FR-013(해상도·fps 정규화)이 지켜지지 않던 문제가 해결됐습니다(specify.txt 16장 #2).
  - 전환 효과 13종을 지원합니다. 장면마다 다르게 지정할 수 있고, 전환 길이는 장면 절반을 넘지 않게 자동으로 줄어듭니다.
  - 기본값(`none`)으로 만든 결과는 001과 같습니다. 장면 수, 순서, 길이가 같습니다.
- 클라이언트 작업 화면에 전환 효과 선택과 길이 입력을 추가했습니다. 한국어·영어로 표시되고 키보드만으로 조작할 수 있습니다.
- 002 이후 단계를 위한 기반도 만들었습니다: DB 컬럼, 렌더 옵션, 미디어 측정(probe), 엔진 속성 플래그, Celery 큐 분리, 브라우저 테스트 기반, CI 작업.
- **테스트**: 전체 113개 중 112개가 통과했습니다. 실패 1건은 이전부터 있던 지연 시간 회귀 판정의 흔들림이고, 단독 실행에서는 통과합니다(이슈 #1).
- **정적 검사**: ruff, ruff format, mypy, TypeScript 검사, 클라이언트 빌드가 모두 통과했습니다.
- **GitHub 이슈**: 6건 등록(#1–#6, 6장 참고)

## 2. 완료한 작업 (tasks.md 29/90)

| 단계 | 작업 | 상태 |
|---|---|---|
| Setup | T001 Pillow 의존성, T003 음악 라이브러리 폴더(빈 목록과 라이선스 안내), T004 설정값, T006 SDK 확인(VERIFY 2), T007 `worker-planning` 서비스, T088 브라우저 테스트 기반, T089 CI 브라우저 작업 | 완료 |
| Setup | T002 Noto Sans KR 폰트 | **연기**. US3에서 필요합니다. 이번 실행에서는 외부 파일을 내려받지 않았고 `server/assets/fonts/README.md`에 안내를 남겼습니다. |
| Setup | T005 FFmpeg libass 확인(VERIFY 1) | **부분 완료**. 개발 PC는 확인했고, Docker 이미지는 빌드해서 확인하지 않았습니다. |
| Foundational | T008–T019 렌더 옵션, probe, DB 컬럼 마이그레이션, 엔진 속성 플래그, 레지스트리, 큐 라우팅, 저장 경로, 작업 상세 응답 확장 | 완료 |
| US1 | T020–T028 타임라인, 합성기, 워커·API 연결, `join.py` 제거, 클라이언트 전환 UI. T078 키보드 브라우저 테스트 | 완료 |
| US3 | T002/T005/T047/T051/T053/T054/T055 자막 9개 지정 위치 표출, 사진 설명글 캡션 매핑, ASS/SRT 생성, NanumGothic 번들 폰트 및 60% 박스 번인 렌더링, 자막 다운로드 API | 완료 |

## 3. 주요 변경 사항

### 서버
- `server/worker/pipeline/timeline.py` (신규): 장면 시작 시각과 전환 겹침을 계산하는 순수 함수입니다. 장면 0에는 전환이 없고, 전환 길이는 양쪽 장면 중 짧은 쪽의 절반으로 제한합니다. `auto`는 6종을 순환합니다.
- `server/worker/pipeline/compose.py` (신규)
  - 각 클립을 scale, pad, fps, yuv420p, trim으로 정규화합니다.
  - 겹침이 있으면 `xfade`, 없으면 `concat`으로 이어 붙입니다.
  - 장면에 오디오가 있으면 유지합니다. 오디오가 없는 클립에는 무음 트랙(`anullsrc`)을 넣고 `acrossfade`로 잇습니다. 모든 클립에 오디오가 없으면 오디오 트랙을 만들지 않습니다.
- `server/worker/pipeline/probe.py` (신규): FFmpeg만으로 길이, 크기, fps, 오디오 유무를 실제로 디코딩해 측정합니다. ffprobe가 필요 없습니다.
- `server/app/render_options.py` (신규): data-model.md의 RenderOptions를 검증합니다. 잘못된 값은 `422 invalid_render_option`으로 응답하고, 메시지에 필드 이름과 허용값을 적습니다.
- `server/worker/tasks.py`: 샷 생성 후 클립을 측정하고, 타임라인을 만들어 `Scene.start_seconds`·`length_seconds`에 기록한 뒤 합성합니다. `Job.final_duration_seconds`도 저장합니다. 합성에 실패하면 작업을 failed로 바꾸고 사유를 남깁니다.
- `server/app/api/jobs.py`
  - `POST /api/jobs`가 `transition`, `transition_seconds`를 받습니다.
  - `GET /api/jobs/{id}` 응답에 `render_options`, `scenes[]`, `final_duration_seconds`가 추가됐습니다.
  - `GET /api/providers`가 `requires_photos`, `sends_data_externally`를 엔진 클래스에서 읽습니다. 클라우드 동의 검사도 엔진 이름 대신 이 플래그로 합니다(FR-016).
- `server/app/models.py`, `db.py`: 새 컬럼을 추가했고, 기존 DB에도 자동으로 컬럼이 추가되도록 마이그레이션 헬퍼를 넓혔습니다(jobs, scenes, source_images).
- `server/worker/celery_app.py`: 큐를 나눴습니다. `run_job`은 `generation`, 캡션·보관 정리·인증 메일은 `planning`입니다.
  - Dockerfile 기본 워커는 두 큐를 모두 처리합니다.
  - compose.yaml은 두 서비스로 나눴습니다.
  - README에 실행 방법을 반영했습니다.
- `server/worker/pipeline/subtitles.py` (신규):
  - 9개 화면 위치(`top_left`, `top_center`, `top_right`, `middle_left`, `middle_center`, `middle_right`, `bottom_left`, `bottom_center`, `bottom_right`, `none`)와 ASS 정렬(Numpad alignment 1~9)을 매핑합니다.
  - SRT 및 번들 폰트(나눔고딕 NanumGothic)와 60% 반투명 박스(`BorderStyle=3`)를 적용한 스타일화된 ASS 자막 생성기를 구현했습니다.
- `server/worker/pipeline/compose.py`: FFmpeg `subtitles` 필터를 필터그래프 끝단에 연결하여 지정 위치에 번인 자막을 렌더링합니다. Windows/Linux 경로 호환을 위한 드라이브 콜론 이스케이프(`\:`)를 처리합니다.
- `server/app/api/jobs.py`:
  - `POST /api/jobs`: 업로드된 사진 설명글(`alt_text`)을 각 장면의 자막(`Scene.caption`, `caption_source="verbatim"`)으로 자동 매핑합니다.
  - `GET /api/jobs/{id}/subtitles?format=srt|ass`: 자막 파일 다운로드 엔드포인트를 추가했습니다.
- `server/assets/fonts/`: CJK 문자 깨짐 방지를 위해 `NanumGothic.ttf` 및 `NotoSansKR-Regular.ttf` 번들 폰트를 추가했습니다.
- `server/app/main.py`: **버그 수정**. Windows에서는 레지스트리 때문에 `.js` 파일이 `text/plain`으로 응답돼, 브라우저가 React 번들을 실행하지 않고 앱이 뜨지 않았습니다. 이제 `.js`와 `.css`의 MIME 유형을 명시적으로 등록합니다.

### 클라이언트
- `client/src/components/PhotoList.tsx` (신규):
  - 파일 추가 시 기존 사진을 덮어쓰지 않고 계속 누적(Append) 등록하는 다중 사진 목록 관리 컴포넌트입니다.
  - 등록된 각 사진의 썸네일 미리보기, 장면 번호(#1, #2...), 파일명, 파일 용량을 시각적 카드로 표시합니다.
  - 각 사진 카드마다 **`[🔄 사진 교체]`** 버튼이 제공되어 특정 사진만 손쉽게 새 이미지로 교체할 수 있습니다.
  - 각 사진 카드마다 개별 캡션(자막) 텍스트를 입력 및 실시간 수정할 수 있으며, 재생 순서 변경(위로/아래로), 개별 삭제, 전체 삭제를 지원합니다.
  - "➕ 사진 추가하기" 버튼을 통해 사진을 여러 번에 나누어 등록할 수 있습니다.
- `client/src/App.tsx`:
  - 동영상 제작 중 및 프리뷰 상태에서도 사진 목록과 캡션 입력 상태를 그대로 유지하여, 프리뷰를 확인한 뒤 각 정지 사진 교체나 캡션 수정을 거쳐 `[🎬 수정 내용으로 동영상 다시 제작]`할 수 있습니다.
  - 프리뷰 영역에 `[✅ 제작 완료 및 새 작업 시작]` 버튼을 추가하여, 사용자가 동영상 제작을 최종 완료했을 때 폼과 사진 목록을 초기화하도록 개선했습니다.
  - 사용자가 동영상 파일 이름(`video_filename`)을 직접 입력할 수 있도록 지원하며, 프리뷰 박스 및 보관함 목록에서 입력한 파일명(`{video_filename}.mp4`)으로 저장 및 표시됩니다.
- `client/src/components/RenderOptions.tsx` (신규)
  - 전환 효과 선택(13종)과 길이 입력(0.1–2.0초)
  - 9개 캡션 위치 선택(상단/중단/하단 × 좌측/중앙/우측, 없음) 드롭다운 추가
  - 사진 설명글을 자막으로 자동 표출하는 안내 문구 및 한/영 다국어 지원
  - 범위를 벗어나면 텍스트 오류를 보여 주고 제출을 막습니다.
  - 대비는 카드 배경 기준으로 안내문 11.0:1, 오류 7.6:1입니다.
- `App.tsx`, `types.ts`, `i18n.ts`(한·영 문자열), `style.css`

### 테스트·CI
- **새 테스트**: 단위 테스트 8개 파일, 통합 테스트 1개 파일(그리고 `test_engine_list.py`에 테스트 1개 추가), 브라우저 테스트 1개 파일, `tests/integration/conftest.py`
- **브라우저 테스트 기반**
  - 임시 DB와 임시 저장소를 쓰는 서버를 별도 프로세스로 띄웁니다.
  - Playwright Chromium과 axe-core를 씁니다.
  - `@pytest.mark.browser` 마커로 구분합니다.
- **CI**: `browser-tests` 작업을 추가했습니다. 기존 통합 테스트 작업은 `-m "not browser"`로 브라우저 테스트를 제외합니다.

## 4. 테스트 결과

| 검사 | 명령 | 결과 |
|---|---|---|
| Lint | `uv run --extra dev ruff check .` | 통과 |
| Format | `uv run --extra dev ruff format --check .` | 통과 (129 파일) |
| 타입 | `uv run --extra dev mypy server tests` | 통과 (87 파일, 오류 0) |
| 클라이언트 타입·빌드 | `npm --prefix client run build` | 통과 |
| 전체 테스트 | `uv run --extra dev pytest tests/unit tests/contract tests/integration --ignore=tests/integration/test_ltx_gpu.py` | **112 통과 / 1 실패** (5분 28초) |
| 지연 시간 테스트 단독 | `pytest tests/integration/test_latency.py` | 3회 중 3회 통과 |

`test_ltx_gpu.py`는 실제 GPU와 ComfyUI가 필요한 테스트라서 제외했습니다.

**새로 추가한 002 테스트 (모두 통과)**

| 파일 | 검증 내용 |
|---|---|
| `tests/unit/test_render_options.py` | 기본값, 경계값, 잘못된 값의 필드 이름, 전환 13종 |
| `tests/unit/test_probe.py` | 길이, 크기, fps, 오디오 유무 |
| `tests/unit/test_db_migration.py` | 001 스키마 DB에 새 컬럼 추가, 기존 데이터 보존, 두 번 실행해도 변화 없음 |
| `tests/unit/test_provider_metadata.py`, `test_storage_paths.py` | 엔진 플래그, `motion` 필드, 큐 라우팅, 저장 경로와 삭제 |
| `tests/unit/test_timeline.py` | 전환 없음, fade, 길이 제한, 장면 1개, auto, 장면별 지정, 실측 길이 사용 |
| `tests/unit/test_compose_graph.py` | 정규화, `xfade`·`concat` 선택, 전환 이름 매핑, 오디오 처리. 크기와 fps가 다른 실제 클립 합성(FR-013) |
| `tests/unit/test_static_mime_types.py` | Windows MIME 버그 회귀 |
| `tests/integration/test_transitions_job.py` | 기본값은 001과 같음(15초, 832×480, 오디오 없음); fade 1초면 13초, 시작 시각 [0, 4, 8]; 사용자 지정 크기·fps; 잘못된 옵션 422 |
| `tests/integration/test_client_render_options.py` (브라우저) | 키보드만으로 fade와 1.0초를 골라 Enter로 제출하면 요청에 두 값이 들어감; 2.5초는 텍스트 오류가 뜨고 전송되지 않음; 전환 컨트롤에 axe serious·critical 위반 없음 |

**quickstart 수동 시나리오와 대응하는 자동 테스트**
- 시나리오 1(기본값 유지)과 2(전환): `test_transitions_job.py`가 같은 조건으로 검증합니다.
- 시나리오 3(크기 혼합): `test_compose_runs_and_normalizes_mixed_clips`가 검증합니다.
- 시나리오 4–11은 US2 이후 범위라 이번에 실행하지 않았습니다.

## 5. 남은 일 (002 범위)

- **US2–US5와 Polish**: T029–T077, T079–T087, T090
- **T002**: 폰트 파일 추가. US3 번인에 필요합니다.
- **T005**: Docker 이미지 FFmpeg에 libass가 있는지 확인
- **VERIFY 2 후속**: `messages.parse`가 받는 정확한 구조화 출력 인자 이름은 US2에서 `captions.py`를 쓸 때 SDK 문서와 대조해야 합니다(research R6).
- **`image_url`**: 작업 상세의 `scenes[].image_url`은 사진 조회 경로(T040, US2)가 생길 때까지 `null`입니다.

## 6. 등록한 GitHub 이슈

| # | 제목 | 비고 |
|---|---|---|
| [#1](https://github.com/cstpeace0191/Movie_Agent/issues/1) | 지연 시간 회귀 판정이 전체 실행에서만 실패 | 테스트 신뢰성. 이전부터 있던 문제입니다. |
| [#2](https://github.com/cstpeace0191/Movie_Agent/issues/2) | LTX-2.3·Gemini 엔진이 영상을 만들지 않음. 알 수 없는 엔진은 조용히 mock으로 대체됨 | specify.txt 16장 #1 |
| [#3](https://github.com/cstpeace0191/Movie_Agent/issues/3) | 로그인한 아무 사용자나 서버를 종료할 수 있음 | 보안, 16장 #6 |
| [#4](https://github.com/cstpeace0191/Movie_Agent/issues/4) | 인증 코드가 가입·재발송 응답과 공개 메일함 API로 노출됨 | 보안, 16장 #7 |
| [#5](https://github.com/cstpeace0191/Movie_Agent/issues/5) | 클라이언트가 클라우드 동의 검사에 Gemini 엔진 ID를 하드코딩함 | FR-016 |
| [#6](https://github.com/cstpeace0191/Movie_Agent/issues/6) | 통합 테스트가 개발용 DB(`movie_agent.db`)에 기록함 | 테스트 격리. #1의 원인일 가능성이 있습니다. |

Windows MIME 버그는 이번에 바로 고쳤기 때문에 이슈로 등록하지 않았습니다.

## 7. 실행 환경 참고

- Windows 개발 PC에는 PATH에 FFmpeg가 없습니다. 파이프라인은 `imageio-ffmpeg`에 들어 있는 FFmpeg 9.0.2를 씁니다.
- 브라우저 테스트를 돌리려면 다음 두 명령을 먼저 한 번 실행해야 합니다.
  - `npm ci --prefix client`
  - `python -m playwright install chromium`
- 이미 빌드한 클라이언트를 다시 쓰려면 `MOVIE_SKIP_CLIENT_BUILD=1`을 설정합니다.
