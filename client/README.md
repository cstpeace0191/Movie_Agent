# Movie Maker - Client (Frontend)

Movie Maker의 프론트엔드 클라이언트는 **React 18 + TypeScript + Vite** 기반의 Single Page Application(SPA)으로 구축되어 있으며, WCAG 2.2 AA 접근성 표준을 준수합니다.

---

## 1. 코드 구조 (Directory Structure)

```text
client/
├── package.json           # React, TypeScript, Vite 의존성 및 빌드 스크립트
├── tsconfig.json          # TypeScript 컴파일러 설정 (ES2020, Bundler 모드)
├── tsconfig.node.json     # Vite 설정용 TypeScript 컴파일러 설정
├── vite.config.ts         # Vite 빌드/개발 서버 설정 (포트 3000, /api 프록시 설정)
├── index.html             # 시맨틱 랜드마크 마크업, 접근성 폴백 및 React 마운트 지점
├── style.css              # 고대비(>= 4.5:1), 눈에 띄는 포커스 링, 반응형 UI 스타일
├── scripts/
│   └── copy-to-server.js  # 빌드 후 client/dist를 server/app/static으로 복사하는 스크립트
├── src/
│   ├── main.tsx           # React DOM Root 인스턴스 생성 및 App 컴포넌트 렌더링
│   ├── App.tsx            # 메인 애플리케이션 컴포넌트 (상태 관리, 폼, SSE 연동, 작업 테이블)
│   ├── types.ts           # REST API 및 SSE 이벤트용 TypeScript 인터페이스 정의
│   └── api.ts             # 백엔드 엔드포인트 비동기 호출 헬퍼 (Auth, Jobs, Providers)
└── dist/                  # npm run build 실행 시 생성되는 프로덕션 정적 번들 아웃풋
```

### 주요 파일별 역할

- **`src/types.ts`**:
  - `User`, `LoginResponse`, `Provider`, `Job`, `Shot`, `SSEProgressEvent`, `ApiError` 등 백엔드 스키마와 1:1로 대응되는 엄격한 타입 정의.
- **`src/api.ts`**:
  - 세션 인증(`getMe`, `loginUser`, `registerUser`, `logoutUser`), 엔진 목록 조회(`fetchProviders`), 작업 제출 및 삭제(`createJob`, `removeJob`), 작업 목록 조회(`fetchJobs`) 비동기 함수.
- **`src/App.tsx`**:
  - **인증 관리**: 세션 쿠키 기반 로그인/회원가입/로그아웃 및 `X-CSRF-Token` 헤더 전송.
  - **작업 생성 폼**: 텍스트 시나리오, 다중 사진 업로드, 사진별 대체 텍스트(alt text, 최대 500자) 동적 입력 필드 지원.
  - **옵션 설정**: 너비/높이, FPS, 씬당 시간(5–10초).
  - **비디오 엔진 선택**: `LTX-2.3`(로컬 기본값) 및 `Gemini Omni 1.2 Flash`(클라우드 선택 시 외부 전송 고지 및 동의 체크박스 게이트).
  - **실시간 진행률 추적**: `EventSource`를 통한 SSE 스트림 구독으로 0%~100% 진행률 및 상태 메시지 실시간 반영.
  - **작업 목록 & 다운로드**: 완성된 MP4 다운로드 링크 및 작업 삭제 기능.
- **`index.html` & `style.css`**:
  - 스크린 리더 및 키보드 사용자를 위한 시맨틱 태그(`<main>`, `<form>`, `<label>`, `<button>`, `<fieldset>`)와 `aria-live="polite"`, `role="alert"` 지원.
  - 3px 아웃라인 포커스 링 및 4.5:1 이상의 텍스트 대비율 유지.

---

## 2. 실행 방법 (How to Run)

### 사전 요구사항

- **Node.js**: v18.0.0 이상 (권장 v20.x 또는 v22.x)
- **npm**: v9.0.0 이상

### 설치

```bash
cd client
npm install
```

---

### 개발 모드 (Vite HMR Development Server)

프론트엔드 코드를 수정하면서 실시간 핫 리로딩(HMR)으로 작업할 때 사용합니다:

```bash
npm run dev
```

- 실행 주소: **`http://localhost:3000/`**
- 백엔드 API 연동: `vite.config.ts`에 의해 `/api/*` 경로의 모든 HTTP 및 SSE 요청이 로컬 FastAPI 서버(`http://127.0.0.1:8000`)로 자동 프록시됩니다. (백엔드 서버가 먼저 실행되어 있어야 합니다)

---

### 프로덕션 빌드 및 서버 정적 폴더 자동 복사 (Production Build & Copy)

FastAPI 서버가 정적으로 서빙할 수 있도록 최적화된 번들을 생성하고, 백엔드의 정적 디렉터리로 자동 복사합니다:

```bash
npm run build
```

- 실행 시 **`tsc && vite build && node scripts/copy-to-server.js`** 파이프라인이 순차적으로 동작합니다:
  1. `tsc`: TypeScript 정적 타입 검사.
  2. `vite build`: 프로덕션 최적화 번들을 `client/dist/`에 생성.
  3. `node scripts/copy-to-server.js`: `client/dist/`의 모든 산출물을 `server/app/static/`으로 자동 복사.
- 백엔드 FastAPI 서버(`server/app/main.py`)는 `server/app/static/` 디렉터리가 채워지면 최우선으로 해당 정적 파일을 루트 경로(`/`)에서 자동으로 서빙합니다.

---

### 빌드 결과물 로컬 미리보기

```bash
npm run preview
```

