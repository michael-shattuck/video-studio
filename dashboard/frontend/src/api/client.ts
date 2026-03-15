export interface ProjectConfig {
  topic: string;
  style: string;
  format: string;
  duration_minutes: number;
  voice: string;
  voice_style: string;
  tts_engine: string;
  chaotic_level: number;
  seed?: string;
  transcript?: string;
  cast: string[];
  add_music: boolean;
  music_volume: number;
  is_short: boolean;
  use_talking_head: boolean;
  avatar_path?: string;
  elevenlabs_voice_id?: string;
  speed: number;
}

export interface PipelineStep {
  name: string;
  status: 'pending' | 'running' | 'complete' | 'failed' | 'skipped';
  started_at?: string;
  completed_at?: string;
  progress: number;
  message: string;
  artifacts: string[];
  error?: string;
}

export interface ScriptSegment {
  text: string;
  visual_cue: string;
  speaker?: string;
}

export interface VideoScript {
  title: string;
  hook: string;
  segments: ScriptSegment[];
  outro: string;
  thumbnail_text: string;
  description: string;
  tags: string[];
  key_phrases: string[];
}

export interface Project {
  id: string;
  config: ProjectConfig;
  status: string;
  steps: Record<string, PipelineStep>;
  script?: VideoScript;
  output_dir?: string;
  created_at: string;
  updated_at: string;
  error?: string;
}

export interface ConfigOptions {
  styles: string[];
  formats: string[];
  tts_engines: string[];
  voice_presets: string[];
  voice_styles: string[];
  voice_personas: Record<string, string[]>;
  chaotic_thresholds: Record<number, Record<string, number>>;
}

export interface Voice {
  name: string;
  size_kb: number;
  path: string;
}

export interface VoicesResponse {
  voices: Voice[];
  mappings: Record<string, string>;
}

const API_BASE = '/api';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export const api = {
  async listProjects(): Promise<{ projects: Project[] }> {
    return fetchJson(`${API_BASE}/projects`);
  },

  async createProject(config: ProjectConfig): Promise<Project> {
    return fetchJson(`${API_BASE}/projects`, {
      method: 'POST',
      body: JSON.stringify({ config }),
    });
  },

  async getProject(id: string): Promise<Project> {
    return fetchJson(`${API_BASE}/projects/${id}`);
  },

  async updateConfig(id: string, config: ProjectConfig): Promise<Project> {
    return fetchJson(`${API_BASE}/projects/${id}/config`, {
      method: 'PUT',
      body: JSON.stringify({ config }),
    });
  },

  async deleteProject(id: string): Promise<void> {
    await fetchJson(`${API_BASE}/projects/${id}`, { method: 'DELETE' });
  },

  async startPipeline(id: string): Promise<{ status: string }> {
    return fetchJson(`${API_BASE}/projects/${id}/start`, { method: 'POST' });
  },

  async pausePipeline(id: string): Promise<{ status: string }> {
    return fetchJson(`${API_BASE}/projects/${id}/pause`, { method: 'POST' });
  },

  async runStep(id: string, step: string): Promise<Project> {
    return fetchJson(`${API_BASE}/projects/${id}/step/${step}`, { method: 'POST' });
  },

  async updateScript(id: string, script: VideoScript): Promise<Project> {
    return fetchJson(`${API_BASE}/projects/${id}/script`, {
      method: 'PUT',
      body: JSON.stringify({ script }),
    });
  },

  async regenerateScript(id: string): Promise<Project> {
    return fetchJson(`${API_BASE}/projects/${id}/regenerate`, { method: 'POST' });
  },

  async resetProject(id: string, fromStep?: string): Promise<Project> {
    const params = fromStep ? `?from_step=${fromStep}` : '';
    return fetchJson(`${API_BASE}/projects/${id}/reset${params}`, { method: 'POST' });
  },

  async getConfigOptions(): Promise<ConfigOptions> {
    return fetchJson(`${API_BASE}/config/options`);
  },

  async listVoices(): Promise<VoicesResponse> {
    return fetchJson(`${API_BASE}/voices`);
  },

  async getVoiceMappings(): Promise<Record<string, string>> {
    return fetchJson(`${API_BASE}/voices/mappings`);
  },

  async updateVoiceMappings(mappings: Record<string, string>): Promise<Record<string, string>> {
    return fetchJson(`${API_BASE}/voices/mappings`, {
      method: 'POST',
      body: JSON.stringify(mappings),
    });
  },

  getVoiceAudioUrl(voiceName: string): string {
    return `${API_BASE}/voices/${voiceName}/audio`;
  },
};

export function createWebSocket(projectId: string): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return new WebSocket(`${protocol}//${host}/ws/${projectId}`);
}
