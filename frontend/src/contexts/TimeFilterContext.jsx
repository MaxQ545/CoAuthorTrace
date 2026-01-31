import { createContext, useContext, useState } from 'react';

const TimeFilterContext = createContext(null);

export function TimeFilterProvider({ children }) {
  const [timeRange, setTimeRange] = useState({
    fromYear: null,  // null means no limit
    toYear: null
  });

  return (
    <TimeFilterContext.Provider value={{ timeRange, setTimeRange }}>
      {children}
    </TimeFilterContext.Provider>
  );
}

export function useTimeFilter() {
  const context = useContext(TimeFilterContext);
  if (!context) {
    throw new Error('useTimeFilter must be used within a TimeFilterProvider');
  }
  return context;
}
