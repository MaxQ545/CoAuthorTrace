import { useTimeFilter } from '../contexts/TimeFilterContext';

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
    <div className="bg-gray-50 border-b">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2">
        <div className="flex flex-wrap items-center gap-4">
          {/* Label */}
          <span className="text-sm font-medium text-gray-600">
            时间范围:
          </span>

          {/* Year Selectors */}
          <div className="flex items-center gap-2">
            <select
              value={timeRange.fromYear || ''}
              onChange={handleFromYearChange}
              className="text-sm border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">起始年份</option>
              {years.map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <span className="text-gray-400">-</span>
            <select
              value={timeRange.toYear || ''}
              onChange={handleToYearChange}
              className="text-sm border border-gray-300 rounded px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">结束年份</option>
              {years.map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          {/* Quick Options */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setQuickRange(5)}
              className={`text-xs px-2 py-1 rounded transition-colors ${
                timeRange.fromYear === currentYear - 4 && timeRange.toYear === currentYear
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              近5年
            </button>
            <button
              onClick={() => setQuickRange(10)}
              className={`text-xs px-2 py-1 rounded transition-colors ${
                timeRange.fromYear === currentYear - 9 && timeRange.toYear === currentYear
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              近10年
            </button>
            <button
              onClick={() => setQuickRange(null)}
              className={`text-xs px-2 py-1 rounded transition-colors ${
                !hasFilter
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              全部
            </button>
          </div>

          {/* Current Selection & Clear */}
          {hasFilter && (
            <div className="flex items-center gap-2 ml-auto">
              <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded">
                {timeRange.fromYear || '...'} - {timeRange.toYear || '...'}
              </span>
              <button
                onClick={clearFilter}
                className="text-xs text-gray-500 hover:text-red-500"
                title="清除筛选"
              >
                x
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default TimeRangeSelector;
