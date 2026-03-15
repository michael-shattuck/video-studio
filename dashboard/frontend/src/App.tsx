import { useState, useEffect, useCallback } from 'react';
import { api, Project, ProjectConfig, ConfigOptions, VideoScript } from './api/client';
import { useWebSocket } from './hooks/useWebSocket';
import ConfigPanel from './components/ConfigPanel';
import PipelineProgress from './components/PipelineProgress';
import ScriptEditor from './components/ScriptEditor';
import ProjectList from './components/ProjectList';
import VoiceCast from './components/VoiceCast';

const DEFAULT_CONFIG: ProjectConfig = {
  topic: '',
  style: 'turboencabulator',
  format: 'debate',
  duration_minutes: 8,
  voice: 'female_narrator',
  voice_style: 'documentary',
  tts_engine: 'fish',
  chaotic_level: 3,
  cast: [],
  add_music: true,
  music_volume: 0.12,
  is_short: false,
  use_talking_head: false,
  speed: 1.0,
};

export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [config, setConfig] = useState<ProjectConfig>(DEFAULT_CONFIG);
  const [configOptions, setConfigOptions] = useState<ConfigOptions | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showProjects, setShowProjects] = useState(false);
  const [showVoices, setShowVoices] = useState(true);

  const handleProjectUpdate = useCallback((project: Project) => {
    setCurrentProject(project);
    setProjects(prev =>
      prev.map(p => p.id === project.id ? project : p)
    );
  }, []);

  const { isConnected, lastUpdate, connect, disconnect } = useWebSocket(handleProjectUpdate);

  useEffect(() => {
    loadProjects();
    loadConfigOptions();
  }, []);

  useEffect(() => {
    if (lastUpdate && currentProject) {
      api.getProject(currentProject.id).then(setCurrentProject).catch(console.error);
    }
  }, [lastUpdate]);

  useEffect(() => {
    if (currentProject) {
      connect(currentProject.id);
    } else {
      disconnect();
    }
  }, [currentProject?.id, connect, disconnect]);

  async function loadProjects() {
    try {
      const { projects } = await api.listProjects();
      setProjects(projects);
    } catch (e) {
      setError('Failed to load projects');
    }
  }

  async function loadConfigOptions() {
    try {
      const options = await api.getConfigOptions();
      setConfigOptions(options);
    } catch (e) {
      console.error('Failed to load config options:', e);
    }
  }

  async function createProject() {
    if (!config.topic.trim()) {
      setError('Please enter a topic');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const project = await api.createProject(config);
      setProjects(prev => [project, ...prev]);
      setCurrentProject(project);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create project');
    } finally {
      setIsLoading(false);
    }
  }

  async function startPipeline() {
    if (!currentProject) return;

    setIsLoading(true);
    setError(null);

    try {
      await api.startPipeline(currentProject.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start pipeline');
    } finally {
      setIsLoading(false);
    }
  }

  async function pausePipeline() {
    if (!currentProject) return;

    try {
      await api.pausePipeline(currentProject.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to pause pipeline');
    }
  }

  async function runStep(step: string) {
    if (!currentProject) return;

    setIsLoading(true);
    setError(null);

    try {
      const project = await api.runStep(currentProject.id, step);
      setCurrentProject(project);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to run step');
    } finally {
      setIsLoading(false);
    }
  }

  async function updateScript(script: VideoScript) {
    if (!currentProject) return;

    try {
      const project = await api.updateScript(currentProject.id, script);
      setCurrentProject(project);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update script');
    }
  }

  async function regenerateScript() {
    if (!currentProject) return;

    setIsLoading(true);
    setError(null);

    try {
      const project = await api.regenerateScript(currentProject.id);
      setCurrentProject(project);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to regenerate script');
    } finally {
      setIsLoading(false);
    }
  }

  async function selectProject(project: Project) {
    setCurrentProject(project);
    setConfig(project.config);
    setShowProjects(false);
  }

  async function deleteProject(id: string) {
    try {
      await api.deleteProject(id);
      setProjects(prev => prev.filter(p => p.id !== id));
      if (currentProject?.id === id) {
        setCurrentProject(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete project');
    }
  }

  function newProject() {
    setCurrentProject(null);
    setConfig(DEFAULT_CONFIG);
    setShowProjects(false);
    setError(null);
  }

  const isPipelineRunning = currentProject?.status !== 'draft' &&
    currentProject?.status !== 'complete' &&
    currentProject?.status !== 'failed' &&
    currentProject?.status !== 'paused';

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold">Video Studio Dashboard</h1>
          <div className="flex items-center gap-4">
            {isConnected && (
              <span className="flex items-center gap-2 text-sm text-green-400">
                <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
                Connected
              </span>
            )}
            <button
              onClick={() => { setShowVoices(true); setShowProjects(false); }}
              className={`btn ${showVoices ? 'btn-primary' : 'btn-secondary'}`}
            >
              Voices
            </button>
            <button
              onClick={() => { setShowProjects(!showProjects); setShowVoices(false); }}
              className={`btn ${showProjects ? 'btn-primary' : 'btn-secondary'}`}
            >
              Projects ({projects.length})
            </button>
            <button onClick={() => { newProject(); setShowVoices(false); }} className="btn btn-primary">
              New Project
            </button>
          </div>
        </div>
      </header>

      <main className="p-6">
        {error && (
          <div className="mb-4 p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-200">
            {error}
            <button
              onClick={() => setError(null)}
              className="ml-4 text-red-400 hover:text-red-300"
            >
              Dismiss
            </button>
          </div>
        )}

        {showVoices ? (
          <VoiceCast />
        ) : showProjects ? (
          <ProjectList
            projects={projects}
            currentProjectId={currentProject?.id}
            onSelect={selectProject}
            onDelete={deleteProject}
            onClose={() => setShowProjects(false)}
          />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1 space-y-6">
              <ConfigPanel
                config={config}
                options={configOptions}
                onChange={setConfig}
                disabled={isPipelineRunning}
              />

              {currentProject && (
                <div className="card">
                  <h3 className="font-semibold mb-2">Project: {currentProject.id}</h3>
                  <p className="text-sm text-gray-400">
                    Status: <span className="capitalize">{currentProject.status}</span>
                  </p>
                  {currentProject.output_dir && (
                    <p className="text-sm text-gray-400 truncate" title={currentProject.output_dir}>
                      Output: {currentProject.output_dir.split('/').slice(-1)[0]}
                    </p>
                  )}
                </div>
              )}

              <div className="flex gap-2">
                {!currentProject ? (
                  <button
                    onClick={createProject}
                    disabled={isLoading || !config.topic.trim()}
                    className="btn btn-primary flex-1"
                  >
                    {isLoading ? 'Creating...' : 'Create Project'}
                  </button>
                ) : (
                  <>
                    <button
                      onClick={startPipeline}
                      disabled={isLoading || isPipelineRunning}
                      className="btn btn-success flex-1"
                    >
                      {isPipelineRunning ? 'Running...' : 'Start Pipeline'}
                    </button>
                    {isPipelineRunning && (
                      <button
                        onClick={pausePipeline}
                        className="btn btn-secondary"
                      >
                        Pause
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>

            <div className="lg:col-span-2 space-y-6">
              {currentProject && (
                <>
                  <PipelineProgress
                    steps={currentProject.steps}
                    onRunStep={runStep}
                    isLoading={isLoading}
                  />

                  {currentProject.script && (
                    <ScriptEditor
                      script={currentProject.script}
                      onSave={updateScript}
                      onRegenerate={regenerateScript}
                      isLoading={isLoading}
                      disabled={isPipelineRunning}
                    />
                  )}
                </>
              )}

              {!currentProject && (
                <div className="card text-center py-16">
                  <div className="text-6xl mb-4">+</div>
                  <p className="text-xl font-semibold text-white mb-2">Create a New Video</p>
                  <p className="text-gray-400 mb-6">Enter a topic in the configuration panel and click Create Project</p>
                  {!config.topic.trim() && (
                    <p className="text-yellow-400 text-sm">Topic is required</p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
