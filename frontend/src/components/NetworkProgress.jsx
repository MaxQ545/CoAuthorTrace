import { motion } from 'framer-motion';
import { Loader2, CheckCircle2, AlertCircle, Waypoints, GitBranch, Users, Share2 } from 'lucide-react';

/**
 * Real-time progress display for progressive network expansion.
 *
 * Props:
 * - status: 'idle' | 'connecting' | 'expanding' | 'complete' | 'error'
 * - progress: 0-100
 * - nodesCount: total nodes discovered
 * - edgesCount: total edges discovered
 * - depth: current BFS depth
 * - components: number of disconnected components
 * - allConnected: whether all seeds are in one component
 * - seedCount: number of seed authors
 * - error: error message string or null
 * - onStop: callback to cancel the build
 */
function NetworkProgress({
  status,
  progress,
  nodesCount,
  edgesCount,
  depth,
  components,
  allConnected,
  seedCount,
  error,
  onStop,
}) {
  if (status === 'idle') return null;

  const isActive = status === 'connecting' || status === 'expanding';
  const isComplete = status === 'complete';
  const isError = status === 'error';

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-card border border-border rounded-xl shadow-sm overflow-hidden"
    >
      {/* Progress bar */}
      <div className="h-1.5 bg-secondary/50 relative overflow-hidden">
        <motion.div
          className={`h-full ${isError ? 'bg-destructive' : isComplete ? 'bg-emerald-500' : 'bg-primary'}`}
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(progress, isActive ? 5 : 0)}%` }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
        />
        {isActive && (
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
        )}
      </div>

      <div className="p-4">
        {/* Status header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {isActive && <Loader2 size={16} className="animate-spin text-primary" />}
            {isComplete && <CheckCircle2 size={16} className="text-emerald-500" />}
            {isError && <AlertCircle size={16} className="text-destructive" />}
            <span className="text-sm font-medium text-foreground">
              {status === 'connecting' && '正在连接...'}
              {status === 'expanding' && '正在展开合作网络...'}
              {status === 'complete' && '网络构建完成'}
              {status === 'error' && '构建出错'}
            </span>
          </div>

          {isActive && onStop && (
            <button
              onClick={onStop}
              className="text-xs px-3 py-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg transition-colors"
            >
              取消
            </button>
          )}
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatItem
            icon={<Users size={12} />}
            label="节点"
            value={nodesCount}
          />
          <StatItem
            icon={<Share2 size={12} />}
            label="连边"
            value={edgesCount}
          />
          <StatItem
            icon={<Waypoints size={12} />}
            label="深度"
            value={depth}
          />
          <StatItem
            icon={<GitBranch size={12} />}
            label="连通分量"
            value={components}
            highlight={allConnected && seedCount > 1}
            highlightLabel={allConnected ? '已连通' : null}
          />
        </div>

        {/* Error message */}
        {isError && error && (
          <div className="mt-3 text-xs text-destructive bg-destructive/10 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        {/* Connected notification */}
        {allConnected && seedCount > 1 && isComplete && (
          <div className="mt-3 text-xs text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 rounded-lg px-3 py-2 flex items-center gap-2">
            <CheckCircle2 size={12} />
            所有种子作者已在同一连通分量中
          </div>
        )}
      </div>
    </motion.div>
  );
}

function StatItem({ icon, label, value, highlight = false, highlightLabel = null }) {
  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs ${
      highlight ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' : 'bg-secondary/30 text-muted-foreground'
    }`}>
      {icon}
      <span>{label}</span>
      <span className="font-bold text-foreground ml-auto">{value}</span>
      {highlightLabel && (
        <span className="text-emerald-500 font-medium">{highlightLabel}</span>
      )}
    </div>
  );
}

export default NetworkProgress;
