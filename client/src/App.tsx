import React, { useState, useEffect, useRef, FormEvent, ChangeEvent } from 'react';
import { Provider, Job, SSEProgressEvent, MailMessage, Transition } from './types';
import { RenderOptions, transitionSecondsError } from './components/RenderOptions';
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
  checkUsernameAvailability,
  verifyEmailCode,
  resendVerificationCode,
  fetchLatestEmail,
} from './api';
import { Language, translations, COUNTRIES } from './i18n';

export const App: React.FC = () => {
  // Language state
  const [lang, setLang] = useState<Language>(() => {
    const saved = localStorage.getItem('movie_lang');
    return saved === 'en' ? 'en' : 'ko';
  });

  const t = translations[lang];

  const handleLangToggle = () => {
    const nextLang: Language = lang === 'ko' ? 'en' : 'ko';
    setLang(nextLang);
    localStorage.setItem('movie_lang', nextLang);
  };

  // Auth state
  const [currentUser, setCurrentUser] = useState<string | null>(null);
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string>('');
  const [authSuccess, setAuthSuccess] = useState<string>('');
  const [authView, setAuthView] = useState<'login' | 'register' | 'verify'>('login');

  // Login form state
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Register form state
  const [regUsername, setRegUsername] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regCountry, setRegCountry] = useState('KR');
  const [regPhone, setRegPhone] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [usernameCheckStatus, setUsernameCheckStatus] = useState<{
    checked: boolean;
    available: boolean;
    message: string;
  }>({ checked: false, available: false, message: '' });

  // Email verification state
  const [pendingEmail, setPendingEmail] = useState('');
  const [pendingUsername, setPendingUsername] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [latestMail, setLatestMail] = useState<MailMessage | null>(null);
  const [isLoadingMail, setIsLoadingMail] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [isRedirecting, setIsRedirecting] = useState(false);

  // Job creation state
  const [scenario, setScenario] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [altTexts, setAltTexts] = useState<string[]>([]);
  const [includeAllPhotos, setIncludeAllPhotos] = useState(true);
  const [width, setWidth] = useState(832);
  const [height, setHeight] = useState(480);
  const [secondsPerShot, setSecondsPerShot] = useState(3.0);
  const [fps, setFps] = useState(16);
  const [transition, setTransition] = useState<Transition>('none');
  const [transitionSeconds, setTransitionSeconds] = useState(0.5);
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
      setAuthError(err.message || t.loginError);
    }
  };

  const handleCheckUsername = async () => {
    const clean = regUsername.trim();
    if (!clean) {
      setUsernameCheckStatus({
        checked: true,
        available: false,
        message: t.usernameRequired,
      });
      return;
    }
    try {
      const res = await checkUsernameAvailability(clean);
      setUsernameCheckStatus({
        checked: true,
        available: res.available,
        message: res.available ? t.usernameAvailable : t.usernameTaken,
      });
    } catch {
      setUsernameCheckStatus({
        checked: true,
        available: false,
        message: t.usernameInvalid,
      });
    }
  };

  const handleRegister = async (e: FormEvent) => {
    e.preventDefault();
    setAuthError('');
    setAuthSuccess('');
    setGlobalError('');

    const cleanUsername = regUsername.trim();
    const cleanEmail = regEmail.trim();

    if (!cleanUsername) {
      setAuthError(t.usernameRequired);
      return;
    }

    if (cleanEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
      setAuthError(t.emailInvalid);
      return;
    }

    try {
      const res = await registerUser({
        username: cleanUsername,
        password: regPassword,
        country: regCountry,
        phone: regPhone.trim(),
        email: cleanEmail,
      });

      if (res.verification_required && cleanEmail) {
        setPendingUsername(cleanUsername);
        setPendingEmail(cleanEmail);
        setVerificationCode(res.debug_code || '');
        setAuthView('verify');
        setAuthSuccess(
          lang === 'ko'
            ? `확인 메세지가 ${cleanEmail} 로 발송되었습니다.`
            : `Verification message sent to ${cleanEmail}.`
        );
        loadLatestMail(cleanEmail);
      } else {
        // Direct registration without email verification
        setAuthSuccess(
          lang === 'ko'
            ? '등록되었습니다. 이제 로그인 할 수있습니다.'
            : 'You are registered, now You can log in.'
        );
        setIsRedirecting(true);
        setTimeout(() => {
          setAuthView('login');
          setIsRedirecting(false);
          setLoginUsername(cleanUsername);
        }, 2000);
      }
    } catch (err: any) {
      const msg = err.message || '';
      if (msg.includes('email_taken') || msg.toLowerCase().includes('email is already')) {
        setAuthError(t.emailTaken);
      } else if (msg.includes('phone_taken') || msg.toLowerCase().includes('phone number is already')) {
        setAuthError(t.phoneTaken);
      } else if (msg.includes('username_taken') || msg.toLowerCase().includes('username is already')) {
        setAuthError(t.usernameTaken);
      } else {
        setAuthError(err.message || 'Registration failed');
      }
    }
  };

  const loadLatestMail = async (emailToFetch: string) => {
    if (!emailToFetch) return;
    setIsLoadingMail(true);
    try {
      const msg = await fetchLatestEmail(emailToFetch);
      if (msg) {
        setLatestMail(msg);
        if (msg.verification_code) {
          setVerificationCode(msg.verification_code);
        }
      }
    } catch {
      // Ignored
    } finally {
      setIsLoadingMail(false);
    }
  };

  // Poll for latest mail in verify view if not yet loaded
  useEffect(() => {
    if (authView !== 'verify' || !pendingEmail) return;
    loadLatestMail(pendingEmail);
    const interval = setInterval(() => {
      loadLatestMail(pendingEmail);
    }, 3000);
    return () => clearInterval(interval);
  }, [authView, pendingEmail]);

  const handleResendCode = async () => {
    if (!pendingUsername) return;
    setIsResending(true);
    setAuthError('');
    try {
      const res = await resendVerificationCode(pendingUsername);
      if (res.code) {
        setVerificationCode(res.code);
      }
      setAuthSuccess(t.codeResentSuccess);
      if (pendingEmail) {
        loadLatestMail(pendingEmail);
      }
    } catch (err: any) {
      setAuthError(err.message || 'Failed to resend code');
    } finally {
      setIsResending(false);
    }
  };

  const handleVerifyEmail = async (e: FormEvent) => {
    e.preventDefault();
    setAuthError('');
    setAuthSuccess('');

    try {
      const res = await verifyEmailCode(pendingUsername, verificationCode.trim());
      // Required success message: '인증되었습니다' / 'You are Verified'
      const successComment = lang === 'ko' ? (res.message_ko || '인증되었습니다') : (res.message_en || 'You are Verified');
      setAuthSuccess(successComment);
      setIsRedirecting(true);

      // Redirect to login page in 2 seconds
      setTimeout(() => {
        setAuthView('login');
        setIsRedirecting(false);
        setLoginUsername(pendingUsername);
        setRegUsername('');
        setRegPassword('');
        setRegPhone('');
        setRegEmail('');
        setVerificationCode('');
        setLatestMail(null);
      }, 2000);
    } catch (err: any) {
      setAuthError(err.message || 'Verification failed');
    }
  };

  const handleLogout = async () => {
    if (csrfToken) {
      await logoutUser(csrfToken);
    }
    setCurrentUser(null);
    setCsrfToken(null);
    setAuthView('login');
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

    // Transition length must be valid before anything is sent (FR-042)
    if (transition !== 'none' && transitionSecondsError(transitionSeconds, t)) {
      setGlobalError(t.transitionSecondsError);
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
    formData.append('transition', transition);
    if (transition !== 'none') {
      formData.append('transition_seconds', String(transitionSeconds));
    }

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

    if (!window.confirm(t.cancelJobConfirm)) {
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
      setProgressStatus(t.jobCancelledStatus);
      loadJobsList();
    } catch (err: any) {
      setGlobalError(err.message || '작업 중지에 실패했습니다.');
    }
  };

  // System Shutdown
  const handleShutdown = async () => {
    if (!csrfToken) return;

    if (!window.confirm(t.shutdownConfirm)) {
      return;
    }

    try {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      await shutdownServer(csrfToken);
      setIsShutdown(true);
    } catch {
      setIsShutdown(true);
    }
  };

  const handleDeleteJob = async (id: string) => {
    if (!csrfToken) return;
    if (!window.confirm(t.deleteConfirm)) return;
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
        <div className="header-left">
          <h1>{t.appTitle}</h1>
          <button
            type="button"
            className="lang-selector-btn"
            onClick={handleLangToggle}
            title={lang === 'ko' ? 'Switch to English' : '한국어로 전환'}
          >
            🌐 {lang === 'ko' ? 'English' : '한국어'}
          </button>
        </div>

        <div className="header-right" id="auth-bar">
          <span id="user-greeting" aria-live="polite">
            {currentUser ? `${t.signedInAs} ${currentUser}` : t.notSignedIn}
          </span>
          {currentUser && (
            <button id="logout-btn" type="button" onClick={handleLogout}>
              {t.signOut}
            </button>
          )}
          {csrfToken && (
            <button
              id="shutdown-btn"
              type="button"
              className="btn-danger"
              title={t.shutdown}
              onClick={handleShutdown}
            >
              {t.shutdown}
            </button>
          )}
        </div>
      </header>

      <main>
        {isShutdown ? (
          <section className="card" style={{ textAlign: 'center', padding: '3rem 1.5rem' }}>
            <h2 style={{ color: 'var(--error)', marginBottom: '1rem' }}>{t.shutdownNoticeTitle}</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem', marginBottom: '0.5rem' }}>
              {t.shutdownNoticeDesc1}
            </p>
            <p style={{ color: 'var(--text-secondary)' }}>{t.shutdownNoticeDesc2}</p>
          </section>
        ) : !currentUser ? (
          /* Google-Style White Background Auth Section */
          <div className="auth-wrapper">
            {authView === 'login' && (
              <div className="auth-card" id="login-card">
                <h2>{t.loginTitle}</h2>
                <div className="subtitle">{t.loginSubtitle}</div>

                {authError && <div role="alert" className="alert-box error">{authError}</div>}
                {authSuccess && <div role="status" className="alert-box success">{authSuccess}</div>}

                <form id="login-form" onSubmit={handleLogin}>
                  <div className="form-group">
                    <label htmlFor="login-username">{t.username}</label>
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
                    <label htmlFor="login-password">{t.password}</label>
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

                  <div className="auth-actions">
                    <button
                      type="button"
                      className="btn-link"
                      id="go-to-register-btn"
                      onClick={() => {
                        setAuthError('');
                        setAuthSuccess('');
                        setAuthView('register');
                      }}
                    >
                      {t.createAccountBtn}
                    </button>
                    <button type="submit" id="login-submit" className="btn-primary">
                      {t.signInBtn}
                    </button>
                  </div>
                </form>
              </div>
            )}

            {authView === 'register' && (
              <div className="auth-card" id="register-card">
                <h2>{t.registerTitle}</h2>
                <div className="subtitle">{t.registerSubtitle}</div>

                {authError && <div role="alert" className="alert-box error">{authError}</div>}
                {authSuccess && <div role="status" className="alert-box success">{authSuccess}</div>}

                <form id="register-form" onSubmit={handleRegister}>
                  {/* Username with availability check */}
                  <div className="form-group">
                    <label htmlFor="reg-username">{t.username}</label>
                    <div className="input-with-button">
                      <input
                        id="reg-username"
                        name="username"
                        type="text"
                        required
                        autoComplete="username"
                        placeholder="3-32 chars (a-z, 0-9, _)"
                        value={regUsername}
                        onChange={(e) => {
                          setRegUsername(e.target.value);
                          setUsernameCheckStatus({ checked: false, available: false, message: '' });
                        }}
                      />
                      <button
                        type="button"
                        id="check-username-btn"
                        className="btn-check"
                        onClick={handleCheckUsername}
                      >
                        {t.checkAvailability}
                      </button>
                    </div>
                    {usernameCheckStatus.checked && (
                      <span
                        className={`validation-msg ${usernameCheckStatus.available ? 'available' : 'unavailable'}`}
                      >
                        {usernameCheckStatus.message}
                      </span>
                    )}
                  </div>

                  {/* Password */}
                  <div className="form-group">
                    <label htmlFor="reg-password">{t.password}</label>
                    <input
                      id="reg-password"
                      name="password"
                      type="password"
                      required
                      autoComplete="new-password"
                      placeholder={t.passwordHint}
                      value={regPassword}
                      onChange={(e) => setRegPassword(e.target.value)}
                    />
                  </div>

                  {/* Country */}
                  <div className="form-group">
                    <label htmlFor="reg-country">{t.country}</label>
                    <select
                      id="reg-country"
                      name="country"
                      value={regCountry}
                      onChange={(e) => setRegCountry(e.target.value)}
                    >
                      {COUNTRIES.map((c) => (
                        <option key={c.code} value={c.code}>
                          {lang === 'ko' ? c.nameKo : c.nameEn}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Phone */}
                  <div className="form-group">
                    <label htmlFor="reg-phone">{t.phone}</label>
                    <input
                      id="reg-phone"
                      name="phone"
                      type="text"
                      autoComplete="tel"
                      placeholder={t.phonePlaceholder}
                      value={regPhone}
                      onChange={(e) => setRegPhone(e.target.value)}
                    />
                  </div>

                  {/* Email */}
                  <div className="form-group">
                    <label htmlFor="reg-email">{t.email}</label>
                    <input
                      id="reg-email"
                      name="email"
                      type="email"
                      required
                      autoComplete="email"
                      placeholder={t.emailPlaceholder}
                      value={regEmail}
                      onChange={(e) => setRegEmail(e.target.value)}
                    />
                  </div>

                  <div className="auth-actions">
                    <button
                      type="button"
                      className="btn-link"
                      id="go-to-login-btn"
                      onClick={() => {
                        setAuthError('');
                        setAuthSuccess('');
                        setAuthView('login');
                      }}
                    >
                      {t.signInInstead}
                    </button>
                    <button type="submit" id="register-submit" className="btn-primary">
                      {t.registerSubmitBtn}
                    </button>
                  </div>
                </form>
              </div>
            )}

            {authView === 'verify' && (
              <div className="auth-card" id="verify-card">
                <h2>{t.verifyTitle}</h2>
                <div className="subtitle">
                  {t.verifyNotice.replace('{email}', pendingEmail)}
                </div>

                {/* In-App Mailbox powered by Python aiosmtpd & Celery */}
                {!isRedirecting && (
                  <div
                    className="mailbox-container"
                    style={{
                      background: '#f8fafc',
                      border: '1px solid #cbd5e1',
                      borderRadius: '8px',
                      padding: '1rem',
                      margin: '1rem 0',
                      textAlign: 'left',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        marginBottom: '0.5rem',
                      }}
                    >
                      <strong style={{ fontSize: '0.95rem', color: '#1e293b' }}>
                        {t.mailboxTitle}
                      </strong>
                      <button
                        type="button"
                        className="btn-link"
                        style={{ fontSize: '0.8rem', padding: '0.2rem 0.4rem' }}
                        onClick={() => pendingEmail && loadLatestMail(pendingEmail)}
                        disabled={isLoadingMail}
                      >
                        {isLoadingMail ? '...' : `🔄 ${t.refreshMailbox}`}
                      </button>
                    </div>

                    {latestMail ? (
                      <div
                        style={{
                          background: '#ffffff',
                          border: '1px solid #e2e8f0',
                          borderRadius: '6px',
                          padding: '0.8rem',
                          fontSize: '0.85rem',
                        }}
                      >
                        <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr', gap: '0.2rem', marginBottom: '0.4rem' }}>
                          <span style={{ color: '#64748b' }}>{t.mailboxSender}:</span>
                          <span style={{ color: '#0f172a', fontWeight: 500 }}>{latestMail.sender}</span>
                          <span style={{ color: '#64748b' }}>{t.mailboxRecipient}:</span>
                          <span style={{ color: '#0f172a' }}>{latestMail.recipient}</span>
                          <span style={{ color: '#64748b' }}>{t.mailboxSubject}:</span>
                          <span style={{ color: '#0369a1', fontWeight: 600 }}>{latestMail.subject}</span>
                          <span style={{ color: '#64748b' }}>{t.mailboxReceivedAt}:</span>
                          <span style={{ color: '#64748b', fontSize: '0.8rem' }}>
                            {new Date(latestMail.created_at).toLocaleString()}
                          </span>
                        </div>

                        {latestMail.verification_code && (
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              background: '#f0f9ff',
                              border: '1px solid #bae6fd',
                              borderRadius: '4px',
                              padding: '0.5rem 0.8rem',
                              margin: '0.6rem 0',
                            }}
                          >
                            <span style={{ fontSize: '1.4rem', fontWeight: 800, letterSpacing: '4px', color: '#0284c7', fontFamily: 'monospace' }}>
                              {latestMail.verification_code}
                            </span>
                            <button
                              type="button"
                              className="btn-secondary"
                              style={{ fontSize: '0.8rem', padding: '0.3rem 0.6rem', cursor: 'pointer' }}
                              onClick={() => {
                                if (latestMail.verification_code) {
                                  setVerificationCode(latestMail.verification_code);
                                }
                              }}
                            >
                              {t.autoFillCode}
                            </button>
                          </div>
                        )}

                        <details style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: '#475569' }}>
                          <summary style={{ cursor: 'pointer', color: '#2563eb' }}>{t.mailboxBody}</summary>
                          <pre
                            style={{
                              whiteSpace: 'pre-wrap',
                              fontFamily: 'monospace',
                              background: '#f1f5f9',
                              padding: '0.5rem',
                              borderRadius: '4px',
                              marginTop: '0.4rem',
                              fontSize: '0.75rem',
                              maxHeight: '150px',
                              overflowY: 'auto',
                            }}
                          >
                            {latestMail.body_text}
                          </pre>
                        </details>
                      </div>
                    ) : (
                      <div style={{ fontSize: '0.85rem', color: '#64748b', padding: '0.5rem 0' }}>
                        {t.noEmailsYet}
                      </div>
                    )}
                  </div>
                )}

                {authError && <div role="alert" className="alert-box error">{authError}</div>}
                {authSuccess && (
                  <div role="status" className="alert-box success">
                    <strong>{authSuccess}</strong>
                    {isRedirecting && (
                      <div style={{ marginTop: '0.4rem', fontSize: '0.9rem' }}>
                        {t.redirectingToLogin}
                      </div>
                    )}
                  </div>
                )}

                {!isRedirecting && (
                  <form id="verify-form" onSubmit={handleVerifyEmail}>
                    <div className="form-group">
                      <label htmlFor="verify-code">{t.verificationCode}</label>
                      <input
                        id="verify-code"
                        type="text"
                        required
                        maxLength={6}
                        placeholder="123456"
                        style={{ textAlign: 'center', fontSize: '1.4rem', letterSpacing: '4px' }}
                        value={verificationCode}
                        onChange={(e) => setVerificationCode(e.target.value)}
                      />
                    </div>

                    <div className="auth-actions" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <button
                        type="button"
                        className="btn-link"
                        onClick={handleResendCode}
                        disabled={isResending}
                        title={t.resendCodeBtn}
                      >
                        {isResending ? '...' : `🔄 ${t.resendCodeBtn}`}
                      </button>
                      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                        <button
                          type="button"
                          className="btn-link"
                          onClick={() => {
                            setAuthError('');
                            setAuthSuccess('');
                            setAuthView('register');
                          }}
                        >
                          {t.signInInstead}
                        </button>
                        <button type="submit" id="verify-submit" className="btn-primary">
                          {t.verifySubmitBtn}
                        </button>
                      </div>
                    </div>
                  </form>
                )}
              </div>
            )}
          </div>
        ) : (
          /* Main Application (Video Creation & Management) */
          <>
            <section id="job-creator-section" className="card">
              <h2>{t.createJobTitle}</h2>
              <form id="job-form" onSubmit={handleCreateJob}>
                <div className="form-group">
                  <label htmlFor="scenario-text">{t.scenarioLabel}</label>
                  <textarea
                    id="scenario-text"
                    name="scenario"
                    rows={4}
                    placeholder={t.scenarioPlaceholder}
                    value={scenario}
                    onChange={(e) => setScenario(e.target.value)}
                  />
                  <small style={{ color: 'var(--text-secondary)', display: 'block', marginTop: '0.25rem' }}>
                    {t.scenarioTip}
                  </small>
                </div>

                <div className="form-group">
                  <label htmlFor="photo-upload">{t.photoUploadLabel}</label>
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
                        {t.includeAllPhotosLabel.replace('{count}', String(selectedFiles.length))}
                      </strong>
                    </label>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'block', marginTop: '0.25rem', paddingLeft: '1.5rem' }}>
                      {includeAllPhotos
                        ? t.includeAllPhotosDescTrue
                            .replace('{count}', String(selectedFiles.length))
                            .replace('{seconds}', String(secondsPerShot))
                            .replace('{total}', (selectedFiles.length * secondsPerShot).toFixed(1))
                        : t.includeAllPhotosDescFalse}
                    </span>
                  </div>
                )}

                {selectedFiles.length > 0 && (
                  <div id="alt-texts-container">
                    <h4>{t.photoAltTitle}</h4>
                    {selectedFiles.map((file, idx) => (
                      <div key={idx} className="form-group">
                        <label htmlFor={`alt-text-${idx}`}>
                          {t.altTextFor.replace('{filename}', file.name)}
                        </label>
                        <input
                          id={`alt-text-${idx}`}
                          type="text"
                          maxLength={500}
                          value={altTexts[idx] || ''}
                          placeholder={t.altTextPlaceholder}
                          onChange={(e) => handleAltTextChange(idx, e.target.value)}
                        />
                      </div>
                    ))}
                  </div>
                )}

                <div className="options-grid">
                  <div className="form-group">
                    <label htmlFor="opt-width">{t.optionsWidth}</label>
                    <input
                      id="opt-width"
                      name="width"
                      type="number"
                      value={width}
                      onChange={(e) => setWidth(Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="opt-height">{t.optionsHeight}</label>
                    <input
                      id="opt-height"
                      name="height"
                      type="number"
                      value={height}
                      onChange={(e) => setHeight(Number(e.target.value))}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="opt-seconds">{t.optionsSeconds}</label>
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
                    <label htmlFor="opt-fps">{t.optionsFps}</label>
                    <input
                      id="opt-fps"
                      name="fps"
                      type="number"
                      value={fps}
                      onChange={(e) => setFps(Number(e.target.value))}
                    />
                  </div>
                </div>

                <RenderOptions
                  t={t}
                  transition={transition}
                  transitionSeconds={transitionSeconds}
                  onTransitionChange={setTransition}
                  onTransitionSecondsChange={setTransitionSeconds}
                />

                <fieldset className="form-group">
                  <legend>{t.videoEngine}</legend>
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
                      {t.cloudConsent}
                    </label>
                  </div>
                )}

                <button
                  type="submit"
                  id="create-job-btn"
                  disabled={isGenerating || (selectedProvider === 'gemini-omni-1.2-flash' && !externalConsent)}
                >
                  {isGenerating ? t.generatingBtn : t.generateBtn}
                </button>
              </form>
            </section>

            {/* Live Status and Progress */}
            <section id="progress-section" className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2>{t.currentProgressTitle}</h2>
                {isGenerating && activeJobId && (
                  <button
                    id="cancel-active-job-btn"
                    type="button"
                    className="btn-stop"
                    onClick={() => handleCancelJob(activeJobId)}
                  >
                    {t.cancelJobBtn}
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
                  <h3 style={{ marginTop: 0, color: 'var(--success)' }}>{t.latestVideoPreview}</h3>
                  <video
                    controls
                    src={`/api/jobs/${lastCompletedJobId}/video`}
                    style={{ width: '100%', maxHeight: '360px', borderRadius: '4px', backgroundColor: '#000' }}
                  >
                    {t.videoUnsupported}
                  </video>
                  <div style={{ marginTop: '0.75rem' }}>
                    <a
                      href={`/api/jobs/${lastCompletedJobId}/video`}
                      download={`movie_${lastCompletedJobId.slice(0, 8)}.mp4`}
                      className="btn-download"
                      id="save-latest-video-btn"
                    >
                      {t.saveVideoBtn}
                    </a>
                  </div>
                </div>
              )}
            </section>

            {/* Job History */}
            <section id="jobs-list-section" className="card">
              <h2>{t.yourVideosTitle}</h2>
              <table id="jobs-table">
                <thead>
                  <tr>
                    <th scope="col">{t.tableId}</th>
                    <th scope="col">{t.tableStatus}</th>
                    <th scope="col">{t.tableProgress}</th>
                    <th scope="col">{t.tableMessage}</th>
                    <th scope="col">{t.tableActions}</th>
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
                            {t.tableStop}
                          </button>
                        )}
                        {j.status === 'succeeded' && (
                          <a
                            href={`/api/jobs/${j.id}/video`}
                            download={`movie_${j.id.slice(0, 8)}.mp4`}
                            className="btn-download"
                            id={`download-btn-${j.id.slice(0, 8)}`}
                          >
                            {t.tableDownload}
                          </a>
                        )}
                        <button type="button" onClick={() => handleDeleteJob(j.id)}>
                          {t.tableDelete}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </>
        )}
      </main>
    </div>
  );
};
