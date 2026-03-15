import { useState, useEffect, useRef } from 'react';
import { api, Voice, VoicesResponse } from '../api/client';

const ALL_ROLES = ['HOST', 'SIDE_A', 'SIDE_B', 'GUEST', 'EXPERT_1', 'EXPERT_2', 'EXPERT_3', 'MODERATOR'];

export default function VoiceCast() {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [mappings, setMappings] = useState<Record<string, string>>({});
  const [playingVoice, setPlayingVoice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    loadVoices();
  }, []);

  async function loadVoices() {
    try {
      const data: VoicesResponse = await api.listVoices();
      setVoices(data.voices);
      setMappings(data.mappings);
    } catch (e) {
      console.error('Failed to load voices:', e);
    } finally {
      setLoading(false);
    }
  }

  function playVoice(voiceName: string) {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    if (playingVoice === voiceName) {
      setPlayingVoice(null);
      return;
    }

    const audio = new Audio(api.getVoiceAudioUrl(voiceName));
    audioRef.current = audio;
    setPlayingVoice(voiceName);

    audio.onended = () => {
      setPlayingVoice(null);
      audioRef.current = null;
    };

    audio.onerror = () => {
      setPlayingVoice(null);
      audioRef.current = null;
    };

    audio.play();
  }

  async function assignVoice(role: string, voiceName: string) {
    const newMappings = { ...mappings };
    if (voiceName) {
      newMappings[role] = voiceName;
    } else {
      delete newMappings[role];
    }
    setMappings(newMappings);

    try {
      await api.updateVoiceMappings(newMappings);
    } catch (e) {
      console.error('Failed to update voice mappings:', e);
    }
  }

  if (loading) {
    return (
      <div className="card text-center py-16">
        <p className="text-gray-400">Loading voices...</p>
      </div>
    );
  }

  if (voices.length === 0) {
    return (
      <div className="card text-center py-16">
        <h2 className="text-2xl font-bold mb-4">No Voices Downloaded</h2>
        <p className="text-gray-400 mb-6">Download voice samples to use with XTTS voice cloning:</p>
        <code className="text-sm text-blue-400 block bg-gray-800 p-4 rounded max-w-md mx-auto">
          cd video_studio && python download_voices.py --libri 20
        </code>
        <p className="text-gray-500 text-sm mt-4">Or clone a voice from YouTube:</p>
        <code className="text-sm text-blue-400 block bg-gray-800 p-4 rounded max-w-lg mx-auto mt-2">
          python clone_voice.py "https://youtube.com/..." rachel --start 60 --duration 30
        </code>
      </div>
    );
  }

  const assignedVoices = new Set(Object.values(mappings));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="card">
        <h2 className="text-xl font-bold border-b border-gray-700 pb-3 mb-4">Character Assignments</h2>
        <p className="text-gray-400 text-sm mb-6">Assign voices to characters. These will be used when TTS engine is set to XTTS.</p>

        <div className="space-y-4">
          {ALL_ROLES.map(role => (
            <div key={role} className="flex items-center gap-3">
              <span className="w-28 text-sm font-medium text-gray-300">{role}</span>
              <select
                className="select flex-1"
                value={mappings[role] || ''}
                onChange={e => assignVoice(role, e.target.value)}
                              >
                <option value="">Not assigned</option>
                {voices.map(v => (
                  <option key={v.name} value={v.name}>
                    {v.name}
                  </option>
                ))}
              </select>
              {mappings[role] && (
                <button
                  onClick={() => playVoice(mappings[role])}
                  className={`w-20 py-2 rounded text-sm font-medium transition-colors ${
                    playingVoice === mappings[role]
                      ? 'bg-green-600 text-white'
                      : 'bg-blue-600 hover:bg-blue-500 text-white'
                  }`}
                                  >
                  {playingVoice === mappings[role] ? 'Stop' : 'Play'}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2 className="text-xl font-bold border-b border-gray-700 pb-3 mb-4">
          Available Voices ({voices.length})
        </h2>
        <p className="text-gray-400 text-sm mb-6">Click to preview. Green = assigned to a character.</p>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-[500px] overflow-y-auto">
          {voices.map(v => {
            const isAssigned = assignedVoices.has(v.name);
            const isPlaying = playingVoice === v.name;

            return (
              <button
                key={v.name}
                onClick={() => playVoice(v.name)}
                className={`flex flex-col items-center justify-center p-4 rounded-lg text-sm transition-all ${
                  isPlaying
                    ? 'bg-blue-600 text-white ring-2 ring-blue-400'
                    : isAssigned
                    ? 'bg-green-800 hover:bg-green-700 text-white'
                    : 'bg-gray-800 hover:bg-gray-700 text-gray-300'
                }`}
                              >
                <span className="text-2xl mb-2">{isPlaying ? '||' : '>'}</span>
                <span className="font-medium truncate w-full text-center">{v.name}</span>
                <span className="text-xs opacity-60 mt-1">
                  {isPlaying ? 'Playing...' : `${v.size_kb} KB`}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
