export interface User {
  id: string;
  username: string;
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
