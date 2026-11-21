import {
  LoginResponse,
  Provider,
  Job,
  ApiError,
  RegisterPayload,
  RegisterResponse,
  CheckUsernameResponse,
  VerifyEmailResponse,
  ResendCodeResponse,
  MailMessage,
} from './types';

export async function getMe(): Promise<LoginResponse | null> {
  const res = await fetch('/api/auth/me');
  if (!res.ok) return null;
  return res.json();
}

export async function checkUsernameAvailability(username: string): Promise<CheckUsernameResponse> {
  const res = await fetch(`/api/auth/check-username?username=${encodeURIComponent(username)}`);
  return res.json();
}

export async function loginUser(body: { username: string; password: string }): Promise<LoginResponse> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error((data as ApiError).error?.message || 'Login failed');
  }
  return data;
}

export async function registerUser(body: RegisterPayload): Promise<RegisterResponse> {
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error((data as ApiError).error?.message || 'Registration failed');
  }
  return data;
}

export async function verifyEmailCode(username: string, code: string): Promise<VerifyEmailResponse> {
  const res = await fetch('/api/auth/verify-email', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, code }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error((data as ApiError).error?.message || 'Verification failed');
  }
  return data;
}

export async function resendVerificationCode(username: string): Promise<ResendCodeResponse> {
  const res = await fetch('/api/auth/resend-code', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error((data as ApiError).error?.message || 'Failed to resend code');
  }
  return data;
}

export async function fetchLatestEmail(email: string): Promise<MailMessage | null> {
  const res = await fetch(`/api/mail/latest?email=${encodeURIComponent(email)}`);
  if (!res.ok) return null;
  return res.json();
}

export async function fetchMailInbox(email?: string): Promise<MailMessage[]> {
  const url = email ? `/api/mail/inbox?email=${encodeURIComponent(email)}` : '/api/mail/inbox';
  const res = await fetch(url);
  if (!res.ok) return [];
  return res.json();
}

export async function logoutUser(csrfToken: string): Promise<void> {
  await fetch('/api/auth/logout', {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

export async function fetchProviders(): Promise<Provider[]> {
  const res = await fetch('/api/providers');
  if (!res.ok) return [];
  return res.json();
}

export async function fetchJobs(): Promise<Job[]> {
  const res = await fetch('/api/jobs');
  if (!res.ok) return [];
  return res.json();
}

export async function createJob(formData: FormData, csrfToken: string): Promise<Job> {
  const res = await fetch('/api/jobs', {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error((data as ApiError).error?.message || 'Job creation failed');
  }
  return data;
}

export async function removeJob(id: string, csrfToken: string): Promise<void> {
  const res = await fetch(`/api/jobs/${id}`, {
    method: 'DELETE',
    headers: { 'X-CSRF-Token': csrfToken },
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error((data as ApiError).error?.message || 'Delete failed');
  }
}

export async function cancelJob(id: string, csrfToken: string): Promise<void> {
  const res = await fetch(`/api/jobs/${id}/cancel`, {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  });
  if (!res.ok) {
    const data = await res.json();
    throw new Error((data as ApiError).error?.message || 'Cancel failed');
  }
}

export async function shutdownServer(csrfToken: string): Promise<void> {
  await fetch('/api/system/shutdown', {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
  });
}

