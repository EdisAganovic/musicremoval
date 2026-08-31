import { useState, useRef, useCallback } from "react";

export function useProjectHistory({ onApplyHistory, onNotify }) {
  const [history, setHistory] = useState([]);
  const [historyIdx, setHistoryIdx] = useState(-1);
  const isHistoryActionRef = useRef(false);

  const pushHistory = useCallback((tracks) => {
    if (isHistoryActionRef.current || !tracks) return;
    setHistory(prev => {
      const truncated = prev.slice(0, historyIdx + 1);
      return [...truncated, JSON.parse(JSON.stringify(tracks))];
    });
    setHistoryIdx(prev => prev + 1);
  }, [historyIdx]);

  const handleUndo = useCallback(() => {
    if (historyIdx > 0 && history[historyIdx - 1]) {
      isHistoryActionRef.current = true;
      const targetTracks = JSON.parse(JSON.stringify(history[historyIdx - 1]));
      setHistoryIdx(prev => prev - 1);
      if (onApplyHistory) onApplyHistory(targetTracks);
      if (onNotify) onNotify("↶ Undo: Reverted last track edit");
      setTimeout(() => { isHistoryActionRef.current = false; }, 60);
    }
  }, [history, historyIdx, onApplyHistory, onNotify]);

  const handleRedo = useCallback(() => {
    if (historyIdx < history.length - 1 && history[historyIdx + 1]) {
      isHistoryActionRef.current = true;
      const targetTracks = JSON.parse(JSON.stringify(history[historyIdx + 1]));
      setHistoryIdx(prev => prev + 1);
      if (onApplyHistory) onApplyHistory(targetTracks);
      if (onNotify) onNotify("↷ Redo: Re-applied track edit");
      setTimeout(() => { isHistoryActionRef.current = false; }, 60);
    }
  }, [history, historyIdx, onApplyHistory, onNotify]);

  const resetHistory = useCallback((initialTracks) => {
    if (initialTracks) {
      setHistory([JSON.parse(JSON.stringify(initialTracks))]);
      setHistoryIdx(0);
    } else {
      setHistory([]);
      setHistoryIdx(-1);
    }
  }, []);

  return {
    history,
    historyIdx,
    canUndo: historyIdx > 0,
    canRedo: historyIdx < history.length - 1,
    pushHistory,
    handleUndo,
    handleRedo,
    resetHistory,
    isHistoryActionRef
  };
}
