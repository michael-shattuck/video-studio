import { Project } from '../api/client';

interface ProjectListProps {
  projects: Project[];
  currentProjectId?: string;
  onSelect: (project: Project) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'text-gray-400',
  script: 'text-yellow-400',
  voice: 'text-yellow-400',
  music: 'text-yellow-400',
  visuals: 'text-yellow-400',
  assembly: 'text-yellow-400',
  thumbnail: 'text-yellow-400',
  complete: 'text-green-400',
  paused: 'text-orange-400',
  failed: 'text-red-400',
};

export default function ProjectList({ projects, currentProjectId, onSelect, onDelete, onClose }: ProjectListProps) {
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between border-b border-gray-700 pb-2 mb-4">
        <h2 className="text-lg font-semibold">Projects</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-white">
          Close
        </button>
      </div>

      {projects.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <p>No projects yet</p>
          <p className="text-sm mt-1">Create a new project to get started</p>
        </div>
      ) : (
        <div className="space-y-2">
          {projects.map(project => (
            <div
              key={project.id}
              className={`
                flex items-center justify-between p-3 rounded-lg border transition-colors cursor-pointer
                ${project.id === currentProjectId
                  ? 'border-blue-500 bg-blue-900/30'
                  : 'border-gray-700 hover:border-gray-600 hover:bg-gray-800/50'
                }
              `}
              onClick={() => onSelect(project)}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-gray-500">{project.id}</span>
                  <span className={`text-xs capitalize ${STATUS_COLORS[project.status]}`}>
                    {project.status}
                  </span>
                </div>
                <p className="font-medium truncate">{project.config.topic}</p>
                <div className="flex items-center gap-3 text-xs text-gray-500 mt-1">
                  <span>{project.config.style}</span>
                  <span>{project.config.format}</span>
                  <span>{formatDate(project.created_at)}</span>
                </div>
              </div>

              <div className="flex items-center gap-2 ml-4">
                {project.status === 'complete' && project.output_dir && (
                  <span className="text-xs text-green-400" title={project.output_dir}>
                    Output ready
                  </span>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm(`Delete project "${project.config.topic}"?`)) {
                      onDelete(project.id);
                    }
                  }}
                  className="p-1 text-gray-500 hover:text-red-400 transition-colors"
                  title="Delete project"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
