import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * SSE EventSource hook for progressive network expansion.
 *
 * Connects to /api/v1/network/expand and dispatches callbacks
 * for each SSE event type. Manages connection lifecycle.
 *
 * Usage:
 *   const { state, progress, error, connect, disconnect } = useNetworkStream();
 *
 *   connect({
 *     authorIds: ['A123', 'A456'],
 *     maxDepth: 2,
 *     topK: 15,
 *   }, {
 *     onNode: (data) => { ... },
 *     onEdge: (data) => { ... },
 *     onProgress: (data) => { ... },
 *     onConnected: (data) => { ... },
 *     onComplete: (data) => { ... },
 *     onError: (data) => { ... },
 *   });
 */
export function useNetworkStream() {
  const [state, setState] = useState('idle');      // 'idle' | 'connecting' | 'streaming' | 'complete' | 'error'
  const [progress, setProgress] = useState(null);   // latest progress event data
  const [error, setError] = useState(null);          // error message string

  const eventSourceRef = useRef(null);
  const callbacksRef = useRef({});
  const stateRef = useRef('idle');
  const retryCountRef = useRef(0);
  const lastParamsRef = useRef(null);
  const maxRetries = 3;
  const retryDelays = [2000, 4000, 8000];

  // Keep a ref to state to avoid stale closure in onerror
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const connect = useCallback((params, callbacks, isRetry = false) => {
    // params: { authorIds, maxDepth, topK, maxNodes, fromYear, toYear }
    // callbacks: { onNode, onEdge, onProgress, onConnected, onComponent, onComplete, onError }
    if (!isRetry) {
      callbacksRef.current = callbacks || {};
      retryCountRef.current = 0;
    }
    lastParamsRef.current = params;

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    // Reset state
    setState('connecting');
    if (!isRetry) {
      setProgress(null);
      setError(null);
    }

    const searchParams = new URLSearchParams({
      author_ids: params.authorIds.join(','),
      max_depth: String(params.maxDepth || 2),
      max_nodes: String(params.maxNodes || 200),
      top_k: String(params.topK || 15),
    });
    if (params.fromYear) searchParams.set('from_year', String(params.fromYear));
    if (params.toYear) searchParams.set('to_year', String(params.toYear));
    if (params.minCollabCount != null && params.minCollabCount > 1) {
      searchParams.set('min_collab_count', String(params.minCollabCount));
    }

    const url = `/api/v1/network/expand?${searchParams}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.addEventListener('init', () => {
      setState('streaming');
    });

    es.addEventListener('node', (e) => {
      const data = JSON.parse(e.data);
      callbacksRef.current.onNode?.(data);
    });

    es.addEventListener('edge', (e) => {
      const data = JSON.parse(e.data);
      callbacksRef.current.onEdge?.(data);
    });

    es.addEventListener('progress', (e) => {
      const data = JSON.parse(e.data);
      // Compute percent from authors_processed/authors_total if not provided
      if (data.percent == null && data.authors_processed != null && data.authors_total > 0) {
        data.percent = Math.round((data.authors_processed / data.authors_total) * 100);
      }
      setProgress(data);
      callbacksRef.current.onProgress?.(data);
    });

    es.addEventListener('connected', (e) => {
      const data = JSON.parse(e.data);
      callbacksRef.current.onConnected?.(data);
    });

    es.addEventListener('component', (e) => {
      const data = JSON.parse(e.data);
      callbacksRef.current.onComponent?.(data);
    });

    es.addEventListener('complete', (e) => {
      const data = JSON.parse(e.data);
      setState('complete');
      setProgress(prev => prev ? { ...prev, authors_processed: prev.authors_total || 0 } : null);
      callbacksRef.current.onComplete?.(data);
      es.close();
      eventSourceRef.current = null;
    });

    es.addEventListener('error', (e) => {
      // Server-sent error event with data
      if (e.data) {
        try {
          const data = JSON.parse(e.data);
          setError(data.message || 'Unknown error');
          callbacksRef.current.onError?.(data);
        } catch {
          setError('Connection lost');
        }
      } else {
        setError('Connection lost');
      }
      setState('error');
      es.close();
      eventSourceRef.current = null;
    });

    // Browser-level connection error with reconnection
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        // Only attempt reconnect if we didn't already complete
        if (stateRef.current !== 'complete') {
          es.close();
          eventSourceRef.current = null;

          if (retryCountRef.current < maxRetries && stateRef.current === 'streaming') {
            const delay = retryDelays[retryCountRef.current];
            retryCountRef.current += 1;
            setError(`Connection lost, reconnecting (${retryCountRef.current}/${maxRetries})...`);
            setTimeout(() => {
              if (lastParamsRef.current) {
                connect(lastParamsRef.current, null, true);
              }
            }, delay);
          } else {
            setState('error');
            setError('Connection closed unexpectedly');
          }
        } else {
          eventSourceRef.current = null;
        }
      }
    };
  }, []);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setState('idle');
    setProgress(null);
    setError(null);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  return { state, progress, error, connect, disconnect };
}

export default useNetworkStream;
