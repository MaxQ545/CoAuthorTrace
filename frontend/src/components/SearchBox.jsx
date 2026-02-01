import { useState, useEffect } from 'react';

function SearchBox({ onSearch, placeholder = '搜索作者...', loading = false, defaultValue = '' }) {
  const [query, setQuery] = useState(defaultValue);

  useEffect(() => {
    setQuery(defaultValue);
  }, [defaultValue]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
    }
  };

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className="flex">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          className="flex-1 px-4 py-3 bg-background border border-border text-foreground placeholder:text-muted-foreground rounded-l-lg focus:ring-2 focus:ring-primary focus:border-primary outline-none transition-colors"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="px-6 py-3 bg-primary text-primary-foreground rounded-r-lg hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground disabled:cursor-not-allowed transition-colors font-medium"
        >
          {loading ? (
            <span className="inline-block animate-spin">⏳</span>
          ) : (
            '🔍 搜索'
          )}
        </button>
      </div>
    </form>
  );
}

export default SearchBox;
