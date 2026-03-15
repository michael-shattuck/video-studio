import { useEffect, useRef, useCallback, useState } from 'react';
import { Project } from '../api/client';

interface ProgressUpdate {
  project_id: string;
  step: string;
  status: string;
  progress: number;
  message: string;
  timestamp: string;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  lastUpdate: ProgressUpdate | null;
  connect: (projectId: string) => void;
  disconnect: () => void;
}

export function useWebSocket(onProjectUpdate?: (project: Project) => void): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<ProgressUpdate | null>(null);
  const pingIntervalRef = useRef<number | null>(null);

  const disconnect = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback((projectId: string) => {
    disconnect();

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const ws = new WebSocket(`${protocol}//${host}/ws/${projectId}`);

    ws.onopen = () => {
      setIsConnected(true);
      pingIntervalRef.current = window.setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        }
      }, 25000);
    };

    ws.onmessage = (event) => {
      if (event.data === 'pong') return;

      try {
        const data = JSON.parse(event.data);

        if (data.type === 'init' && data.project && onProjectUpdate) {
          onProjectUpdate(data.project);
        } else if (data.project_id) {
          setLastUpdate(data as ProgressUpdate);
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = null;
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    wsRef.current = ws;
  }, [disconnect, onProjectUpdate]);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return { isConnected, lastUpdate, connect, disconnect };
}
