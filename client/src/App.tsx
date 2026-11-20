import React, { useState, useEffect, useRef, FormEvent, ChangeEvent } from 'react';
import { Provider, Job, SSEProgressEvent } from './types';
import {
  getMe,
  loginUser,
  registerUser,
  logoutUser,
  fetchProviders,
  fetchJobs,
  createJob,
  removeJob,
  cancelJob,
  shutdownServer,
} from './api';

export const App: React.FC = () => {
  // Auth state
  const [currentUser, setCurrentUser] = useState<string | null>(null);
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string>('');
  const [authSuccess, setAuthSuccess] = useState<string>('');

  // Form states
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [regUsername, setRegUsername] = useState('');
  const [regPassword, setRegPassword] = useState('');

  // Job creation state
  const [scenario, setScenario] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [altTexts, setAltTexts] = useState<string[]>([]);
  const [includeAllPhotos, setIncludeAllPhotos] = useState(true);
  const [width, setWidth] = useState(832);
  const [height, setHeight] = useState(480);
  const [secondsPerShot, setSecondsPerShot] = useState(3.0);
  const [fps, setFps] = useState(16);
  const [selectedProvider, setSelectedProvider] = useState('ltx-2.3');
  const [externalConsent, setExternalConsent] = useState(false);
  const [providers, setProviders] = useState<Provider[]>([]);

  // Progress & Jobs state
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isShutdown, setIsShutdown] = useState(false);
  const [lastCompletedJobId, setLastCompletedJobId] = useState<string | null>(null);
  const [progressStatus, setProgressStatus] = useState('No job running.');
  const [progressBarWidth, setProgressBarWidth] = useState(0);
  const [globalError, setGlobalError] = useState('');
  const [jobs, setJobs] = useState<Job[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Check auth on mount
  useEffect(() => {
    checkCurrentUser();
  }, []);

  // Fetch providers and jobs when authenticated
  useEffect(() => {
    if (currentUser) {
      loadProviders();
      loadJobsList();
    } else {
      setProviders([]);
      setJobs([]);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    }
  }, [currentUser]);

  const checkCurrentUser = async () => {
    try {
      const data = await getMe();
      if (data) {
        setCurrentUser(data.username);
        setCsrfToken(data.csrf_token);
      } else {
        setCurrentUser(null);
        setCsrfToken(null);
      }
    } catch {
      setCurrentUser(null);
      setCsrfToken(null);
    }
  };

  const loadProviders = async () => {
    try {
      const provs = await fetchProviders();
      setProviders(provs);
      const def = provs.find((p) => p.is_default);
      if (def) setSelectedProvider(def.id);
    } catch {
      // ignore
    }
  };

  const loadJobsList = async () => {
    try {
      const list = await fetchJobs();
      setJobs(list);
    } catch {
      // ignore
    }
  };

  // Auth actions
  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setAuthError('');
    setAuthSuccess('');
    setGlobalError('');
    try {
      const res = await loginUser({ username: loginUsername, password: loginPassword });
      setCurrentUser(res.username);
      setCsrfToken(res.csrf_token);
      setLoginPassword('');
    } catch (err: any) {
      setAuthError(err.message || 'Login failed');
    }
  };

  const handleRegister = async (e: FormEvent) => {
    e.preventDefault();
    setAuthError('');
    setAuthSuccess('');
    setGlobalError('');
    try {
      await registerUser({ username: regUsername, password: regPassword });
      setAuthSuccess('Account created! Please sign in with your credentials.');
      setRegUsername('');
      setRegPassword('');
    } catch (err: any) {
      setAuthError(err.message || 'Registration failed');
    }
  };

  const handleLogout = async () => {
    if (csrfToken) {
      await logoutUser(csrfToken);
    }
    setCurrentUser(null);
    setCsrfToken(null);
  };

  // File selection
  const handleFilesChange = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    setSelectedFiles(files);
    setAltTexts(new Array(files.length).fill(''));
  };

  const handleAltTextChange = (index: number, val: string) => {
    const next = [...altTexts];
    next[index] = val;
    setAltTexts(next);
  };

  // SSE tracking
  const startSSE = (jobId: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    setActiveJobId(jobId);
    setIsGenerating(true);

    const es = new EventSource(`/api/jobs/${jobId}/events`);
    eventSourceRef.current = es;

    es.addEventListener('progress', (e: MessageEvent) => {
      try {
        const data: SSEProgressEvent = JSON.parse(e.data);
        setProgressBarWidth(data.progress);
        setProgressStatus(`${data.message} (${data.progress}%)`);
        if (data.status === 'failed') {
          setIsGenerating(false);
        } else if (data.status === 'succeeded') {
          setIsGenerating(false);
          setLastCompletedJobId(jobId);
        }
      } catch {
        // ignore
      }
    });

    es.addEventListener('done', (e: MessageEvent) => {
      try {
        const data: SSEProgressEvent = JSON.parse(e.data);
        setProgressBarWidth(data.progress);
        setProgressStatus(`${data.message} (${data.progress}%)`);
        setIsGenerating(false);
        if (data.status === 'succeeded' || data.progress === 100) {
          setLastCompletedJobId(jobId);
        }
      } catch {
        // ignore
      }
      es.close();
      loadJobsList();
    });

    es.onerror = () => {
      // Reconnect handled automatically
    };
  };

  // Job Submission
  const handleCreateJob = async (e: FormEvent) => {
    e.preventDefault();
    setGlobalError('');

    if (!csrfToken) {
      setGlobalError('CSRF token missing');
      return;
    }

    // Cloud consent gate
    if (selectedProvider === 'gemini-omni-1.2-flash' && !externalConsent) {
      setGlobalError('Confirmation is required before sending data to cloud AI.');
      return;
    }

    const formData = new FormData();
    if (scenario.trim()) {
      formData.append('scenario', scenario);
    }
    selectedFiles.forEach((file) => {
      formData.append('images', file);
    });
    if (altTexts.some((t) => t.trim().length > 0)) {
      formData.append('image_alt_texts', JSON.stringify(altTexts));
    }
    formData.append('width', String(width));
    formData.append('height', String(height));
    formData.append('seconds_per_shot', String(secondsPerShot));
    formData.append('fps', String(fps));
    formData.append('provider', selectedProvider);
    formData.append('chain_frames', 'true');
    formData.append('external_consent', externalConsent ? 'true' : 'false');
    formData.append('include_all_photos', includeAllPhotos ? 'true' : 'false');

    try {
      const created = await createJob(formData, csrfToken);
      setScenario('');
      setSelectedFiles([]);
      setAltTexts([]);
      startSSE(created.id);
      loadJobsList();
    } catch (err: any) {
      setGlobalError(err.message || 'Job submission failed');
    }
  };

  // Job Cancellation
  const handleCancelJob = async (jobIdToCancel?: string) => {
    const targetId = jobIdToCancel || activeJobId;
    if (!targetId || !csrfToken) return;

    if (!window.confirm('정말로 비디오 생성을 중지하시겠습니까?')) {
      return;
    }

    try {
      await cancelJob(targetId, csrfToken);
      if (eventSourceRef.current && targetId === activeJobId) {
        eventSourceRef.current.close();
      }
      if (targetId === activeJobId) {
        setIsGenerating(false);
      }
      setProgressStatus('비디오 제작이 중지되었습니다.');
      loadJobsList();
    } catch (err: any) {
      setGlobalError(err.message || '작업 중지에 실패했습니다.');
    }
  };

  // System Shutdown
  const handleShutdown = async () => {
    if (!csrfToken) return;

    if (!window.confirm('Movie Maker 서버를 종료하시겠습니까? 실행 중인 모든 작업이 중단됩니다.')) {
      return;
    }

    try {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      await shutdownServer(csrfToken);
      setIsShutdown(true);
    } catch (err: any) {
      // 서버 프로세스가 즉시 종료되어 네트워크 오류가 날 수도 있으므로 화면상 종료로 전환
      setIsShutdown(true);
    }
  };

  const handleDeleteJob = async (id: string) => {
    if (!csrfToken) return;
    try {
      await removeJob(id, csrfToken);
      loadJobsList();
    } catch (err: any) {
      setGlobalError(err.message || 'Failed to delete job');
    }
  };

  return (
    <div>
      <header>
        <h1>Movie Maker</h1>
        <div id="auth-bar" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span id="user-greeting" aria-live="polite">
            {currentUser ? `Signed in as ${currentUser}` : 'Not signed in'}
          </span>
          {currentUser && (
            <button id="logout-btn" type="button" onClick={handleLogout}>
              Sign Out
            </button>
          )}
          {csrfToken && (
            <button
              id="shutdown-btn"
              type="button"
              className="btn-danger"
              title="Movie Maker 서버 프로세스를 종료합니다."
              onClick={handleShutdown}
            >
              프로그램 종료
            </button>
          )}
        </div>
      </header>

      <main>
        {isShutdown ? (
          <section className="card" style={{ textAlign: 'center', padding: '3rem 1.5rem' }}>
            <h2 style={{ color: 'var(--error)', marginBottom: '1rem' }}>🛑 프로그램이 종료되었습니다</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem', marginBottom: '0.5rem' }}>
              Movie Maker 백엔드 서버가 안전하게 종료되었습니다.
            </p>
            <p style={{ color: 'var(--text-secondary)' }}>
              브라우저 탭이나 창을 닫으셔도 좋습니다. 다시 사용하시려면 서버 컨테이너를 재시작해 주세요.
            </p>
          </section>
        ) : (
          <>
            {!currentUser ? (
              <section id="auth-section" className="card">
            <h2>Account Access</h2>
            {authError && <div role="alert" className="error-text">{authError}</div>}
            {authSuccess && <div role="status" className="success-text" style={{ color: '#03543f', marginBottom: '1rem' }}>{authSuccess}</div>}
            <div className="auth-forms">
              {/* Sign In Form */}
              <form id="login-form" onSubmit={handleLogin}>
                <h3>Sign In</h3>
                <div className="form-group">
                  <label htmlFor="login-username">Username</label>
                  <input
                    id="login-username"
                    name="username"
                    type="text"
                    required
                    autoComplete="username"
                    value={loginUsername}
                    onChange={(e) => setLoginUsername(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="login-password">Password</label>
                  <input
                    id="login-password"
                    name="password"
                    type="password"
                    required
                    autoComplete="current-password"
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                  />
                </div>
                <button type="submit" id="login-submit">
                  Sign In
                </button>
              </form>

              {/* Register Form */}
              <form id="register-form" onSubmit={handleRegister}>
                <h3>Register</h3>
                <div className="form-group">
                  <label htmlFor="reg-username">Username (3-32 chars)</label>
                  <input
                    id="reg-username"
                    name="username"
                    type="text"
                    required
                    autoComplete="username"
                    value={regUsername}
                    onChange={(e) => setRegUsername(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="reg-password">Password (min 12 chars)</label>
                  <input
                    id="reg-password"
                    name="password"
                    type="password"
                    required
                    autoComplete="new-password"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                  />
                </div>
                <button type="submit" id="register-submit">
                  Create Account
                </button>
              </form>
            </div>
          </section>
        ) : (
          <section id="job-creator-section" className="card">
            <h2>Create Movie Job</h2>
            <form id="job-form" onSubmit={handleCreateJob}>
              <div className="form-group">
                <label htmlFor="scenario-text">Story Scenario (Optional if uploading photos)</label>
                <textarea
                  id="scenario-text"
                  name="scenario"
                  rows={4}
                  placeholder="Enter scenario text... (One paragraph per scene. Leave empty for photo slideshow)"
                  value={scenario}
                  onChange={(e) => setScenario(e.target.value)}
                />
                <small style={{ color: 'var(--text-secondary)', display: 'block', marginTop: '0.25rem' }}>
                  💡 팁: 사진 여러 장을 올리셨다면 시나리오 없이 사진만으로 슬라이드쇼 비디오를 제작할 수 있습니다. 각 장면에 별도의 스토리를 지정하려면 문단(Enter 두 번)으로 구분해 작성하세요.
                </small>
              </div>

              <div className="form-group">
                <label htmlFor="photo-upload">
                  Upload Photos (JPG, PNG, WebP, max 100 files, ≤ 20 MB each)
                </label>
                <input
                  id="photo-upload"
                  name="images"
                  type="file"
                  multiple
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleFilesChange}
                />
              </div>

              {selectedFiles.length > 0 && (
                <div
                  style={{
                    backgroundColor: '#1e293b',
                    padding: '0.75rem 1rem',
                    borderRadius: '6px',
                    border: '1px solid var(--accent)',
                    marginBottom: '1rem',
                  }}
                >
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', margin: 0 }}>
                    <input
                      type="checkbox"
                      checked={includeAllPhotos}
                      onChange={(e) => setIncludeAllPhotos(e.target.checked)}
                      style={{ width: 'auto' }}
                    />
                    <strong style={{ color: 'var(--text-primary)' }}>
                      📸 업로드한 모든 사진({selectedFiles.length}장)을 동영상 컷으로 모두 포함하기
                    </strong>
                  </label>
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'block', marginTop: '0.25rem', paddingLeft: '1.5rem' }}>
                    {includeAllPhotos
                      ? `총 ${selectedFiles.length}개의 샷이 생성되며, 컷당 ${secondsPerShot}초씩 총 ${(selectedFiles.length * secondsPerShot).toFixed(1)}초 동안 모든 사진이 순서대로 상영됩니다.`
                      : '체크 해제 시 시나리오 문단 수만큼만 사진이 사용되고 남는 사진은 제외됩니다.'}
                  </span>
                </div>
              )}

              {selectedFiles.length > 0 && (
                <div id="alt-texts-container">
                  <h4>Photo Descriptions & Alt Text (max 500 chars)</h4>
                  {selectedFiles.map((file, idx) => (
                    <div key={idx} className="form-group">
                      <label htmlFor={`alt-text-${idx}`}>Alt text for {file.name}</label>
                      <input
                        id={`alt-text-${idx}`}
                        type="text"
                        maxLength={500}
                        value={altTexts[idx] || ''}
                        placeholder="Description of visual contents"
                        onChange={(e) => handleAltTextChange(idx, e.target.value)}
                      />
                    </div>
                  ))}
                </div>
              )}

              <div className="options-grid">
                <div className="form-group">
                  <label htmlFor="opt-width">Width</label>
                  <input
                    id="opt-width"
                    name="width"
                    type="number"
                    value={width}
                    onChange={(e) => setWidth(Number(e.target.value))}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="opt-height">Height</label>
                  <input
                    id="opt-height"
                    name="height"
                    type="number"
                    value={height}
                    onChange={(e) => setHeight(Number(e.target.value))}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="opt-seconds">Seconds per Shot (1-5)</label>
                  <input
                    id="opt-seconds"
                    name="seconds_per_shot"
                    type="number"
                    step="0.5"
                    min="1"
                    max="5"
                    value={secondsPerShot}
                    onChange={(e) => setSecondsPerShot(Number(e.target.value))}
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="opt-fps">FPS</label>
                  <input
                    id="opt-fps"
                    name="fps"
                    type="number"
                    value={fps}
                    onChange={(e) => setFps(Number(e.target.value))}
                  />
                </div>
              </div>

              <fieldset className="form-group">
                <legend>Video Engine</legend>
                <div id="provider-options">
                  {providers.length > 0 ? (
                    providers.map((p) => (
                      <label key={p.id}>
                        <input
                          type="radio"
                          name="provider"
                          value={p.id}
                          checked={selectedProvider === p.id}
                          disabled={!p.enabled}
                          onChange={(e) => setSelectedProvider(e.target.value)}
                        />
                        {p.label} {!p.enabled && p.disabled_reason ? `(${p.disabled_reason})` : ''}
                      </label>
                    ))
                  ) : (
                    <>
                      <label>
                        <input
                          type="radio"
                          name="provider"
                          value="ltx-2.3"
                          checked={selectedProvider === 'ltx-2.3'}
                          onChange={(e) => setSelectedProvider(e.target.value)}
                        />
                        LTX-2.3 (local GPU, default)
                      </label>
                      <label>
                        <input
                          type="radio"
                          name="provider"
                          value="gemini-omni-1.2-flash"
                          checked={selectedProvider === 'gemini-omni-1.2-flash'}
                          onChange={(e) => setSelectedProvider(e.target.value)}
                        />
                        Gemini Omni 1.2 Flash (cloud)
                      </label>
                    </>
                  )}
                </div>
              </fieldset>

              {selectedProvider === 'gemini-omni-1.2-flash' && (
                <div id="cloud-consent-group" className="form-group">
                  <label>
                    <input
                      type="checkbox"
                      id="cloud-consent"
                      name="external_consent"
                      checked={externalConsent}
                      onChange={(e) => setExternalConsent(e.target.checked)}
                    />
                    I confirm that scenario text and photos may be sent to Google Gemini cloud servers for generation.
                  </label>
                </div>
              )}

              <button
                type="submit"
                id="create-job-btn"
                disabled={isGenerating || (selectedProvider === 'gemini-omni-1.2-flash' && !externalConsent)}
              >
                {isGenerating ? 'Generating Video...' : 'Generate Video'}
              </button>
            </form>
          </section>
        )}

        {/* Live Status and Progress */}
        <section id="progress-section" className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2>Current Job Progress</h2>
            {isGenerating && activeJobId && (
              <button
                id="cancel-active-job-btn"
                type="button"
                className="btn-stop"
                onClick={() => handleCancelJob(activeJobId)}
              >
                ⛔ 제작 중지
              </button>
            )}
          </div>
          <div id="progress-status" aria-live="polite">
            {progressStatus}
          </div>
          <div id="progress-bar-container">
            <div id="progress-bar" style={{ width: `${progressBarWidth}%` }} />
          </div>
          {globalError && (
            <div id="error-message" role="alert" className="error-text">
              {globalError}
            </div>
          )}

          {lastCompletedJobId && (
            <div
              id="completed-video-box"
              style={{
                marginTop: '1.25rem',
                padding: '1rem',
                backgroundColor: '#0f172a',
                borderRadius: '6px',
                border: '1px solid var(--border)',
              }}
            >
              <h3 style={{ marginTop: 0, color: 'var(--success)' }}>🎬 생성된 동영상 미리보기</h3>
              <video
                controls
                src={`/api/jobs/${lastCompletedJobId}/video`}
                style={{ width: '100%', maxHeight: '360px', borderRadius: '4px', backgroundColor: '#000' }}
              >
                브라우저가 비디오 재생을 지원하지 않습니다.
              </video>
              <div style={{ marginTop: '0.75rem' }}>
                <a
                  href={`/api/jobs/${lastCompletedJobId}/video`}
                  download={`movie_${lastCompletedJobId.slice(0, 8)}.mp4`}
                  className="btn-download"
                  id="save-latest-video-btn"
                >
                  💾 생성된 동영상 저장
                </a>
              </div>
            </div>
          )}
        </section>

        {/* Job History */}
        {currentUser && (
          <section id="jobs-list-section" className="card">
            <h2>Your Videos</h2>
            <table id="jobs-table">
              <thead>
                <tr>
                  <th scope="col">ID</th>
                  <th scope="col">Status</th>
                  <th scope="col">Progress</th>
                  <th scope="col">Message</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody id="jobs-table-body">
                {jobs.map((j) => (
                  <tr key={j.id}>
                    <td>{j.id.slice(0, 8)}...</td>
                    <td>{j.status}</td>
                    <td>{j.progress}%</td>
                    <td>{j.message}</td>
                    <td>
                      {(j.status === 'queued' || j.status === 'running') && (
                        <button
                          type="button"
                          className="btn-stop"
                          style={{ marginRight: '0.5rem' }}
                          onClick={() => handleCancelJob(j.id)}
                        >
                          중지
                        </button>
                      )}
                      {j.status === 'succeeded' && (
                        <a
                          href={`/api/jobs/${j.id}/video`}
                          download={`movie_${j.id.slice(0, 8)}.mp4`}
                          className="btn-download"
                          id={`download-btn-${j.id.slice(0, 8)}`}
                        >
                          동영상 저장
                        </a>
                      )}
                      <button type="button" onClick={() => handleDeleteJob(j.id)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
          </>
        )}
      </main>
    </div>
  );
};

