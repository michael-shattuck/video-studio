import { ProjectConfig, ConfigOptions } from '../api/client';

interface ConfigPanelProps {
  config: ProjectConfig;
  options: ConfigOptions | null;
  onChange: (config: ProjectConfig) => void;
  disabled?: boolean;
}

export default function ConfigPanel({ config, options, onChange, disabled }: ConfigPanelProps) {
  const update = <K extends keyof ProjectConfig>(key: K, value: ProjectConfig[K]) => {
    onChange({ ...config, [key]: value });
  };

  return (
    <div className="card space-y-4">
      <h2 className="text-lg font-semibold border-b border-gray-700 pb-2">Configuration</h2>

      <div>
        <label className="label text-base font-semibold text-white">Topic *</label>
        <input
          type="text"
          className="input text-lg py-3 border-2 focus:border-blue-400"
          value={config.topic}
          onChange={e => update('topic', e.target.value)}
          placeholder="What should this video be about?"
          disabled={disabled}
          autoFocus
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">Style</label>
          <select
            className="select"
            value={config.style}
            onChange={e => update('style', e.target.value)}
            disabled={disabled}
          >
            {(options?.styles || ['educational', 'storytelling', 'listicle', 'documentary', 'motivational', 'relaxing', 'turboencabulator']).map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="label">Format</label>
          <select
            className="select"
            value={config.format}
            onChange={e => update('format', e.target.value)}
            disabled={disabled}
          >
            {(options?.formats || ['monologue', 'interview', 'panel', 'debate']).map(f => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className="label">Duration: {config.duration_minutes} min</label>
        <input
          type="range"
          min="1"
          max="30"
          value={config.duration_minutes}
          onChange={e => update('duration_minutes', parseInt(e.target.value))}
          className="w-full accent-blue-500"
          disabled={disabled}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">Voice</label>
          <select
            className="select"
            value={config.voice}
            onChange={e => update('voice', e.target.value)}
            disabled={disabled}
          >
            {(options?.voice_presets || ['female_narrator', 'male_narrator', 'female_casual', 'male_casual']).map(v => (
              <option key={v} value={v}>{v.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="label">TTS Engine</label>
          <select
            className="select"
            value={config.tts_engine}
            onChange={e => update('tts_engine', e.target.value)}
            disabled={disabled}
          >
            {(options?.tts_engines || ['auto', 'fish', 'elevenlabs', 'openai', 'bark', 'edge']).map(e => (
              <option key={e} value={e}>{e}</option>
            ))}
          </select>
        </div>
      </div>

      {config.style === 'turboencabulator' && (
        <div>
          <label className="label">Chaotic Level: {config.chaotic_level}</label>
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map(level => (
              <button
                key={level}
                onClick={() => update('chaotic_level', level)}
                className={`flex-1 py-2 rounded transition-colors ${
                  config.chaotic_level === level
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 hover:bg-gray-600'
                }`}
                disabled={disabled}
              >
                {level}
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {config.chaotic_level === 1 && 'Mostly sane - slow descent'}
            {config.chaotic_level === 2 && 'Gradual build'}
            {config.chaotic_level === 3 && 'Default - balanced chaos'}
            {config.chaotic_level === 4 && 'Faster chaos'}
            {config.chaotic_level === 5 && 'Maximum unhinged'}
          </p>
        </div>
      )}

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="add_music"
            checked={config.add_music}
            onChange={e => update('add_music', e.target.checked)}
            disabled={disabled}
            className="w-4 h-4 accent-blue-500"
          />
          <label htmlFor="add_music" className="text-sm">Add Background Music</label>
        </div>

        {config.add_music && (
          <div>
            <label className="label">Music Volume: {Math.round(config.music_volume * 100)}%</label>
            <input
              type="range"
              min="0"
              max="0.5"
              step="0.01"
              value={config.music_volume}
              onChange={e => update('music_volume', parseFloat(e.target.value))}
              className="w-full accent-blue-500"
              disabled={disabled}
            />
          </div>
        )}
      </div>

      <div>
        <label className="label">Speed: {config.speed?.toFixed(2) || '1.00'}x</label>
        <input
          type="range"
          min="0.8"
          max="1.3"
          step="0.05"
          value={config.speed || 1.0}
          onChange={e => update('speed', parseFloat(e.target.value))}
          className="w-full accent-blue-500"
          disabled={disabled}
        />
        <div className="flex justify-between text-xs text-gray-500">
          <span>Slow</span>
          <span>Normal</span>
          <span>Fast</span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="is_short"
          checked={config.is_short}
          onChange={e => update('is_short', e.target.checked)}
          disabled={disabled}
          className="w-4 h-4 accent-blue-500"
        />
        <label htmlFor="is_short" className="text-sm">Short Format (9:16 vertical)</label>
      </div>

      <div>
        <label className="label">Seed (optional)</label>
        <input
          type="text"
          className="input"
          value={config.seed || ''}
          onChange={e => update('seed', e.target.value || undefined)}
          placeholder="For reproducibility..."
          disabled={disabled}
        />
      </div>

      <div>
        <label className="label">Custom Transcript (JSON, optional)</label>
        <textarea
          className="input h-20 text-sm font-mono"
          value={config.transcript || ''}
          onChange={e => update('transcript', e.target.value || undefined)}
          placeholder='{"title": "...", "hook": "...", "segments": [...]}'
          disabled={disabled}
        />
      </div>
    </div>
  );
}
