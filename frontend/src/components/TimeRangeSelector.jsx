import { useTimeFilter } from '../contexts/TimeFilterContext';
import { Calendar, X, Filter } from 'lucide-react';
import { cn } from '../lib/utils';
import { motion } from 'framer-motion';

function TimeRangeSelector() {
  const { timeRange, setTimeRange } = useTimeFilter();
  const currentYear = new Date().getFullYear();

  // Generate year options from 1950 to current year
  const years = [];
  for (let y = currentYear; y >= 1950; y--) {
    years.push(y);
  }

  const handleFromYearChange = (e) => {
    const value = e.target.value ? parseInt(e.target.value) : null;
    setTimeRange(prev => ({ ...prev, fromYear: value }));
  };

  const handleToYearChange = (e) => {
    const value = e.target.value ? parseInt(e.target.value) : null;
    setTimeRange(prev => ({ ...prev, toYear: value }));
  };

  const setQuickRange = (years) => {
    if (years === null) {
      setTimeRange({ fromYear: null, toYear: null });
    } else {
      setTimeRange({
        fromYear: currentYear - years + 1,
        toYear: currentYear
      });
    }
  };

  const clearFilter = () => {
    setTimeRange({ fromYear: null, toYear: null });
  };

  const hasFilter = timeRange.fromYear !== null || timeRange.toYear !== null;

  return (
    <div className="w-full flex flex-col sm:flex-row items-center justify-between gap-4 text-sm">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Filter size={16} />
        <span className="font-medium text-foreground">时间筛选</span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {/* Year Selectors */}
        <div className="flex items-center bg-card border rounded-md px-2 py-1 shadow-sm">
          <Calendar size={14} className="text-muted-foreground mr-2" />
          <select
            value={timeRange.fromYear || ''}
            onChange={handleFromYearChange}
            className="bg-transparent border-none outline-none text-foreground focus:ring-0 cursor-pointer text-xs sm:text-sm"
          >
            <option value="">起始年份</option>
            {years.map(y => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <span className="text-muted-foreground mx-2">-</span>
          <select
            value={timeRange.toYear || ''}
            onChange={handleToYearChange}
            className="bg-transparent border-none outline-none text-foreground focus:ring-0 cursor-pointer text-xs sm:text-sm"
          >
            <option value="">结束年份</option>
            {years.map(y => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>

        {/* Quick Options */}
        <div className="flex items-center bg-secondary/50 rounded-md p-1">
          {[
            { label: '近5年', value: 5 },
            { label: '近10年', value: 10 },
            { label: '全部', value: null }
          ].map((option) => {
            const isActive = option.value === null
              ? !hasFilter
              : timeRange.fromYear === currentYear - option.value + 1;

            return (
              <button
                key={option.label}
                onClick={() => setQuickRange(option.value)}
                className={cn(
                  "px-3 py-1 rounded text-xs font-medium transition-all duration-200",
                  isActive
                    ? "bg-background text-primary shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                )}
              >
                {option.label}
              </button>
            );
          })}
        </div>

        {/* Clear Button */}
        {hasFilter && (
          <motion.button
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={clearFilter}
            className="flex items-center justify-center p-1.5 text-muted-foreground hover:text-destructive bg-destructive/10 hover:bg-destructive/20 rounded-md transition-colors"
            title="清除筛选"
          >
            <X size={14} />
          </motion.button>
        )}
      </div>
    </div>
  );
}

export default TimeRangeSelector;
