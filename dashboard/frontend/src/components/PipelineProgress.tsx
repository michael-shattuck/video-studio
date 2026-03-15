import { PipelineStep } from '../api/client';

interface PipelineProgressProps {
  steps: Record<string, PipelineStep>;
  onRunStep: (step: string) => void;
  isLoading: boolean;
}

const STEP_ORDER = ['script', 'voice', 'music', 'visuals', 'assembly', 'thumbnail'];

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-600',
  running: 'bg-blue-500 animate-pulse',
  complete: 'bg-green-500',
  failed: 'bg-red-500',
  skipped: 'bg-gray-500',
};

export default function PipelineProgress({ steps, onRunStep, isLoading }: PipelineProgressProps) {
  const getOverallProgress = () => {
    let completed = 0;
    let total = 0;

    for (const step of STEP_ORDER) {
      const s = steps[step];
      if (s) {
        total++;
        if (s.status === 'complete' || s.status === 'skipped') {
          completed++;
        } else if (s.status === 'running') {
          completed += s.progress / 100;
        }
      }
    }

    return total > 0 ? (completed / total) * 100 : 0;
  };

  const getCurrentStepMessage = () => {
    for (const step of STEP_ORDER) {
      const s = steps[step];
      if (s?.status === 'running') {
        return s.message || `Running ${s.name}...`;
      }
    }

    for (const step of STEP_ORDER) {
      const s = steps[step];
      if (s?.status === 'failed') {
        return `Failed: ${s.error || s.message || s.name}`;
      }
    }

    return null;
  };

  const overallProgress = getOverallProgress();
  const currentMessage = getCurrentStepMessage();

  return (
    <div className="card">
      <h2 className="text-lg font-semibold border-b border-gray-700 pb-2 mb-4">Pipeline Progress</h2>

      <div className="flex items-center gap-2 mb-4">
        {STEP_ORDER.map((stepName, index) => {
          const step = steps[stepName];
          if (!step) return null;

          const isActive = step.status === 'running';
          const canRun = step.status === 'pending' || step.status === 'failed';

          return (
            <div key={stepName} className="flex items-center">
              <button
                onClick={() => canRun && onRunStep(stepName)}
                disabled={isLoading || !canRun}
                className={`
                  relative flex items-center justify-center w-10 h-10 rounded-full
                  transition-all duration-200
                  ${STATUS_COLORS[step.status]}
                  ${canRun && !isLoading ? 'hover:ring-2 hover:ring-blue-400 cursor-pointer' : ''}
                  ${isActive ? 'ring-2 ring-blue-400' : ''}
                `}
                title={`${step.name}: ${step.status}${step.message ? ` - ${step.message}` : ''}`}
              >
                <span className="text-xs font-bold uppercase">
                  {stepName.charAt(0)}
                </span>
                {step.status === 'running' && (
                  <div className="absolute inset-0 rounded-full border-2 border-blue-300 border-t-transparent animate-spin" />
                )}
              </button>
              {index < STEP_ORDER.length - 1 && (
                <div className={`w-6 h-0.5 ${
                  steps[STEP_ORDER[index + 1]]?.status !== 'pending'
                    ? 'bg-green-500'
                    : 'bg-gray-600'
                }`} />
              )}
            </div>
          );
        })}
      </div>

      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span>{Math.round(overallProgress)}%</span>
          <span className="text-gray-400">
            {STEP_ORDER.filter(s => steps[s]?.status === 'complete' || steps[s]?.status === 'skipped').length}
            /{STEP_ORDER.length} steps
          </span>
        </div>
        <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-green-500 transition-all duration-300"
            style={{ width: `${overallProgress}%` }}
          />
        </div>
        {currentMessage && (
          <p className="text-sm text-gray-400">{currentMessage}</p>
        )}
      </div>

      <div className="mt-4 space-y-2">
        {STEP_ORDER.map(stepName => {
          const step = steps[stepName];
          if (!step) return null;

          return (
            <div
              key={stepName}
              className={`flex items-center justify-between text-sm p-2 rounded ${
                step.status === 'running' ? 'bg-blue-900/30' :
                step.status === 'failed' ? 'bg-red-900/30' : ''
              }`}
            >
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${STATUS_COLORS[step.status]}`} />
                <span className="font-medium">{step.name}</span>
              </div>
              <div className="flex items-center gap-2 text-gray-400">
                {step.status === 'running' && (
                  <span>{Math.round(step.progress)}%</span>
                )}
                {step.artifacts.length > 0 && (
                  <span title={step.artifacts.join(', ')}>
                    {step.artifacts.length} file{step.artifacts.length !== 1 ? 's' : ''}
                  </span>
                )}
                <span className="capitalize">{step.status}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
