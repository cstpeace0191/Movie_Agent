import { LoginResponse, Provider, Job, ApiError } from './types';

export async function getMe(): Promise<LoginResponse | null> {
  const res = await fetch('/api/auth/me');
  if (!res.ok) return null;
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

export async function registerUser(body: { username: string; password: string }): Promise<void> {
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error((data as ApiError).error?.message || 'Registration failed');
  }
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

