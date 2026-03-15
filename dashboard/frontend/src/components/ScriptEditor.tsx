import { useState, useEffect } from 'react';
import { VideoScript, ScriptSegment } from '../api/client';

interface ScriptEditorProps {
  script: VideoScript;
  onSave: (script: VideoScript) => void;
  onRegenerate: () => void;
  isLoading: boolean;
  disabled?: boolean;
}

export default function ScriptEditor({ script, onSave, onRegenerate, isLoading, disabled }: ScriptEditorProps) {
  const [editedScript, setEditedScript] = useState<VideoScript>(script);
  const [isEditing, setIsEditing] = useState(false);
  const [expandedSegment, setExpandedSegment] = useState<number | null>(null);

  useEffect(() => {
    setEditedScript(script);
  }, [script]);

  const updateField = <K extends keyof VideoScript>(key: K, value: VideoScript[K]) => {
    setEditedScript(prev => ({ ...prev, [key]: value }));
    setIsEditing(true);
  };

  const updateSegment = (index: number, updates: Partial<ScriptSegment>) => {
    setEditedScript(prev => ({
      ...prev,
      segments: prev.segments.map((seg, i) =>
        i === index ? { ...seg, ...updates } : seg
      ),
    }));
    setIsEditing(true);
  };

  const handleSave = () => {
    onSave(editedScript);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditedScript(script);
    setIsEditing(false);
  };

  const wordCount = [
    editedScript.hook,
    ...editedScript.segments.map(s => s.text),
    editedScript.outro
  ].join(' ').split(/\s+/).filter(Boolean).length;

  const estimatedDuration = Math.round(wordCount / 150 * 60);

  return (
    <div className="card">
      <div className="flex items-center justify-between border-b border-gray-700 pb-2 mb-4">
        <h2 className="text-lg font-semibold">Script Editor</h2>
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <span>{wordCount} words</span>
          <span>~{Math.floor(estimatedDuration / 60)}:{(estimatedDuration % 60).toString().padStart(2, '0')}</span>
        </div>
      </div>

      <div className="space-y-4">
        <div>
          <label className="label">Title</label>
          <input
            type="text"
            className="input text-lg font-semibold"
            value={editedScript.title}
            onChange={e => updateField('title', e.target.value)}
            disabled={disabled}
          />
        </div>

        <div>
          <label className="label">Hook</label>
          <textarea
            className="input h-24 text-sm"
            value={editedScript.hook}
            onChange={e => updateField('hook', e.target.value)}
            disabled={disabled}
          />
        </div>

        <div>
          <label className="label">Segments ({editedScript.segments.length})</label>
          <div className="space-y-2 max-h-96 overflow-y-auto pr-2">
            {editedScript.segments.map((segment, index) => (
              <div
                key={index}
                className={`border rounded p-3 transition-colors ${
                  expandedSegment === index ? 'border-blue-500 bg-blue-900/20' : 'border-gray-700'
                }`}
              >
                <div
                  className="flex items-start justify-between cursor-pointer"
                  onClick={() => setExpandedSegment(expandedSegment === index ? null : index)}
                >
                  <div className="flex-1 min-w-0">
                    <span className="text-xs text-gray-500 font-mono">#{index + 1}</span>
                    <p className={`text-sm ${expandedSegment === index ? '' : 'line-clamp-2'}`}>
                      {segment.text}
                    </p>
                  </div>
                  <span className="ml-2 text-gray-500">
                    {expandedSegment === index ? '' : ''}
                  </span>
                </div>

                {expandedSegment === index && (
                  <div className="mt-3 space-y-2 pt-3 border-t border-gray-700">
                    <div>
                      <label className="label text-xs">Text</label>
                      <textarea
                        className="input h-32 text-sm"
                        value={segment.text}
                        onChange={e => updateSegment(index, { text: e.target.value })}
                        disabled={disabled}
                      />
                    </div>
                    <div>
                      <label className="label text-xs">Visual Cue</label>
                      <input
                        type="text"
                        className="input text-sm"
                        value={segment.visual_cue}
                        onChange={e => updateSegment(index, { visual_cue: e.target.value })}
                        placeholder="Description for stock footage..."
                        disabled={disabled}
                      />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div>
          <label className="label">Outro</label>
          <textarea
            className="input h-20 text-sm"
            value={editedScript.outro}
            onChange={e => updateField('outro', e.target.value)}
            disabled={disabled}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Thumbnail Text</label>
            <input
              type="text"
              className="input"
              value={editedScript.thumbnail_text}
              onChange={e => updateField('thumbnail_text', e.target.value)}
              disabled={disabled}
            />
          </div>
          <div>
            <label className="label">Tags</label>
            <input
              type="text"
              className="input"
              value={editedScript.tags.join(', ')}
              onChange={e => updateField('tags', e.target.value.split(',').map(t => t.trim()).filter(Boolean))}
              placeholder="tag1, tag2, tag3"
              disabled={disabled}
            />
          </div>
        </div>

        <div>
          <label className="label">Description</label>
          <textarea
            className="input h-20 text-sm"
            value={editedScript.description}
            onChange={e => updateField('description', e.target.value)}
            disabled={disabled}
          />
        </div>

        <div>
          <label className="label">Key Phrases</label>
          <input
            type="text"
            className="input"
            value={editedScript.key_phrases.join(', ')}
            onChange={e => updateField('key_phrases', e.target.value.split(',').map(p => p.trim()).filter(Boolean))}
            placeholder="phrase1, phrase2, phrase3"
            disabled={disabled}
          />
        </div>
      </div>

      <div className="flex gap-2 mt-4 pt-4 border-t border-gray-700">
        {isEditing && (
          <>
            <button
              onClick={handleSave}
              disabled={isLoading || disabled}
              className="btn btn-success"
            >
              Save Changes
            </button>
            <button
              onClick={handleCancel}
              disabled={isLoading}
              className="btn btn-secondary"
            >
              Cancel
            </button>
          </>
        )}
        <button
          onClick={onRegenerate}
          disabled={isLoading || disabled}
          className="btn btn-primary ml-auto"
        >
          {isLoading ? 'Regenerating...' : 'Regenerate Script'}
        </button>
      </div>
    </div>
  );
}
