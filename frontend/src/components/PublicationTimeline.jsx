import { usePublicationTimeline } from '../hooks/queries';
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
  const { data: timeline = [], isLoading } = usePublicationTimeline(
    authorId,
    fromYear,
    toYear,
  );

  if (isLoading) {
    return (
      <div className="bg-card rounded-xl border border-border shadow-sm p-6">
        <div className="flex items-center gap-2 mb-6">
          <TrendingUp className="text-primary" size={20} />
          <h2 className="text-lg font-semibold text-foreground">
            发表趋势
          </h2>
        </div>
        <div className="flex items-center justify-center h-48 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin mr-2" />
          加载中...
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
          发表趋势
        </h2>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={timeline} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
          <XAxis
            dataKey="year"
            tick={{ fontSize: 12 }}
            tickFormatter={(v) => String(v)}
          />
          <YAxis
            yAxisId="left"
            tick={{ fontSize: 12 }}
            allowDecimals={false}
            label={{ value: '论文数', angle: -90, position: 'insideLeft', style: { fontSize: 12, fill: 'var(--muted-foreground)' } }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fontSize: 12 }}
            allowDecimals={false}
            label={{ value: '被引次数', angle: 90, position: 'insideRight', style: { fontSize: 12, fill: 'var(--muted-foreground)' } }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--card)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              fontSize: '13px',
            }}
            formatter={(value, name) => {
              const label = name === 'works_count' ? '论文数' : '被引次数';
              return [value, label];
            }}
            labelFormatter={(label) => `${label} 年`}
          />
          <Legend
            formatter={(value) =>
              value === 'works_count' ? '论文数' : '被引次数'
            }
          />
          <Bar
            yAxisId="left"
            dataKey="works_count"
            fill="hsl(221, 83%, 53%)"
            radius={[4, 4, 0, 0]}
            maxBarSize={40}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="cited_by_count"
            stroke="hsl(142, 71%, 45%)"
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
