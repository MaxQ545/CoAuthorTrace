import { usePublicationTimeline } from '../hooks/queries';
import { useI18n } from '../contexts/I18nContext';
import { TrendingUp, Loader2 } from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ComposedChart,
} from 'recharts';

function PublicationTimeline({ authorId, fromYear = null, toYear = null }) {
  const { t } = useI18n();
  const { data: timeline = [], isLoading } = usePublicationTimeline(
    authorId,
    fromYear,
    toYear,
  );

  // Detect dark mode for recharts colors
  const isDark = document.documentElement.classList.contains('dark');
  const chartColors = {
    bar: isDark ? '#60a5fa' : '#3b82f6',
    line: isDark ? '#4ade80' : '#22c55e',
    axis: isDark ? '#9ca3af' : '#6b7280',
    grid: isDark ? '#374151' : '#e5e7eb',
  };

  if (isLoading) {
    return (
      <div className="bg-card rounded-xl border border-border shadow-sm p-6">
        <div className="flex items-center gap-2 mb-6">
          <TrendingUp className="text-primary" size={20} />
          <h2 className="text-lg font-semibold text-foreground">
            {t('timeline.title')}
          </h2>
        </div>
        <div className="flex items-center justify-center h-48 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin mr-2" />
          {t('timeline.loading')}
        </div>
      </div>
    );
  }

  if (!timeline || timeline.length === 0) {
    return null;
  }

  return (
    <div className="bg-card rounded-xl border border-border shadow-sm p-6">
      <div className="flex items-center gap-2 mb-6">
        <TrendingUp className="text-primary" size={20} />
        <h2 className="text-lg font-semibold text-foreground">
          {t('timeline.title')}
        </h2>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={timeline} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} className="opacity-30" />
          <XAxis
            dataKey="year"
            tick={{ fontSize: 12, fill: chartColors.axis }}
            tickFormatter={(v) => String(v)}
          />
          <YAxis
            yAxisId="left"
            tick={{ fontSize: 12, fill: chartColors.axis }}
            allowDecimals={false}
            label={{ value: t('timeline.papers_count'), angle: -90, position: 'insideLeft', style: { fontSize: 12, fill: chartColors.axis } }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fontSize: 12, fill: chartColors.axis }}
            allowDecimals={false}
            label={{ value: t('timeline.citations_count'), angle: 90, position: 'insideRight', style: { fontSize: 12, fill: chartColors.axis } }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: isDark ? '#1f2937' : '#ffffff',
              border: `1px solid ${chartColors.grid}`,
              borderRadius: '8px',
              fontSize: '13px',
              color: isDark ? '#e5e7eb' : '#1f2937',
            }}
            formatter={(value, name) => {
              const label = name === 'works_count' ? t('timeline.papers_count') : t('timeline.citations_count');
              return [value, label];
            }}
            labelFormatter={(label) => t('timeline.year_suffix', { year: label })}
          />
          <Legend
            formatter={(value) =>
              value === 'works_count' ? t('timeline.papers_count') : t('timeline.citations_count')
            }
          />
          <Bar
            yAxisId="left"
            dataKey="works_count"
            fill={chartColors.bar}
            radius={[4, 4, 0, 0]}
            maxBarSize={40}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="cited_by_count"
            stroke={chartColors.line}
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export default PublicationTimeline;
