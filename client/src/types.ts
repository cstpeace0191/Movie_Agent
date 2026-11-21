export interface User {
  id: string;
  username: string;
  email?: string | null;
  country?: string | null;
  phone?: string | null;
  email_verified?: boolean;
}

export interface RegisterPayload {
  username: string;
  password: string;
  country?: string;
  phone?: string;
  email?: string;
}

export interface RegisterResponse {
  id: string;
  username: string;
  email?: string | null;
  verification_required: boolean;
  debug_code?: string | null;
}

export interface CheckUsernameResponse {
  available: boolean;
  message: string;
}

export interface VerifyEmailResponse {
  success: boolean;
  message_ko: string;
  message_en: string;
}

export interface ResendCodeResponse {
  success: boolean;
  message: string;
  email?: string | null;
  code?: string | null;
}

export interface MailMessage {
  id: string;
  recipient: string;
  sender: string;
  subject: string;
  body_text: string;
  verification_code?: string | null;
  created_at: string;
}

export interface LoginResponse {
  id: string;
  username: string;
  csrf_token: string;
}

export interface Provider {
  id: string;
  label: string;
  location: 'local' | 'cloud';
  enabled: boolean;
  is_default: boolean;
  sends_data_externally: boolean;
  max_clip_seconds?: number | null;
  disabled_reason?: string | null;
}

export interface Shot {
  id: string;
  position: number;
  status: string;
  attempts: number;
  scene_excerpt?: string | null;
  source_image_id?: string | null;
  error?: string | null;
}

export interface Job {
  id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'expired';
  input_mode: string;
  progress: number;
  message: string;
  failure_reason?: string | null;
  planned_seconds: number;
  unused_image_count: number;
  created_at: string;
  expires_at: string;
  shots?: Shot[] | null;
}

export interface SSEProgressEvent {
  job_id: string;
  status: string;
  progress: number;
  message: string;
  failure_reason?: string | null;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
  };
}
