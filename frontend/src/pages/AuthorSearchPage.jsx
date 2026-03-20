import { useEffect, useState, useRef, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuthorSearch } from '../hooks/queries';
import SearchBox from '../components/SearchBox';
import { motion } from 'framer-motion';
import { User, Building2, FileText, Quote, Loader2, Search as SearchIcon, X, Clock } from 'lucide-react';
import { cn } from '../lib/utils';

const SEARCH_HISTORY_KEY = 'coauthor_search_history';
const MAX_HISTORY = 5;

function getSearchHistory() {
  try {
    return JSON.parse(localStorage.getItem(SEARCH_HISTORY_KEY)) || [];
  } catch {
    return [];
  }
}

function saveToSearchHistory(query) {
  if (!query || !query.trim()) return;
  const trimmed = query.trim();
  let history = getSearchHistory();
  history = history.filter((q) => q !== trimmed);
  history.unshift(trimmed);
  history = history.slice(0, MAX_HISTORY);
  localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(history));
}

function clearSearchHistory() {
  localStorage.removeItem(SEARCH_HISTORY_KEY);
}

function AuthorSearchPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const query = searchParams.get('q') || '';
  const [searchHistory, setSearchHistory] = useState(getSearchHistory);
  const [showHistory, setShowHistory] = useState(false);

  // Institution filter with debounce
  const [institutionInput, setInstitutionInput] = useState('');
  const [institutionFilter, setInstitutionFilter] = useState(null);
  const debounceRef = useRef(null);

  const handleInstitutionChange = useCallback((e) => {
    const value = e.target.value;
    setInstitutionInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setInstitutionFilter(value.trim() || null);
    }, 300);
  }, []);

  const clearInstitutionFilter = useCallback(() => {
    setInstitutionInput('');
    setInstitutionFilter(null);
    if (debounceRef.current) clearTimeout(debounceRef.current);
  }, []);

  // Clean up debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  useEffect(() => {
    document.title = query ? `搜索: ${query} - CoAuthorTrace` : '搜索 - CoAuthorTrace';
    return () => { document.title = '论文合作者追踪系统'; };
  }, [query]);

  const { data, isLoading: loading, error } = useAuthorSearch(query, 50, 0, true, false, institutionFilter);
  const results = data?.results || [];
  const total = data?.total || 0;

  const handleSearch = (newQuery) => {
    navigate(`/authors/search?q=${encodeURIComponent(newQuery)}`);
  };

  const handleAuthorClick = (authorId) => {
    if (query) {
      saveToSearchHistory(query);
      setSearchHistory(getSearchHistory());
    }
    navigate(`/author/${authorId}`);
  };

  const handleHistoryClick = (historyQuery) => {
    setShowHistory(false);
    navigate(`/authors/search?q=${encodeURIComponent(historyQuery)}`);
  };

  const handleClearHistory = () => {
    clearSearchHistory();
    setSearchHistory([]);
    setShowHistory(false);
  };

  return (
    <div className="space-y-6">
      {/* Search Header */}
      <div className="bg-secondary/30 rounded-2xl p-6 border border-border">
        <div className="max-w-2xl mx-auto space-y-4">
          <h1 className="text-2xl font-bold text-center text-foreground">作者搜索</h1>
          <div
            onFocus={() => { if (!query) setShowHistory(true); }}
            onBlur={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget)) {
                setTimeout(() => setShowHistory(false), 150);
              }
            }}
          >
            <SearchBox
              onSearch={handleSearch}
              placeholder="输入作者姓名搜索..."
              defaultValue={query}
            />
            {showHistory && searchHistory.length > 0 && !query && (
              <div className="mt-2 p-3 bg-background border border-border rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Clock size={12} /> 最近搜索
                  </span>
                  <button
                    onClick={handleClearHistory}
                    className="text-xs text-muted-foreground hover:text-destructive transition-colors"
                  >
                    清除历史
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {searchHistory.map((q) => (
                    <button
                      key={q}
                      onMouseDown={(e) => { e.preventDefault(); handleHistoryClick(q); }}
                      className="px-3 py-1 text-sm bg-secondary text-secondary-foreground rounded-full hover:bg-primary/10 hover:text-primary transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
          {/* Institution Filter */}
          <div className="relative">
            <Building2 size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              value={institutionInput}
              onChange={handleInstitutionChange}
              placeholder="筛选机构..."
              className={cn(
                "w-full pl-9 pr-9 py-2 rounded-lg border border-border bg-background text-foreground text-sm",
                "placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
              )}
            />
            {institutionInput && (
              <button
                onClick={clearInstitutionFilter}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
              >
                <X size={16} />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Results Section */}
      <div className="space-y-4">
        {/* Results Header */}
        {query && (
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">
              搜索 "{query}" 的结果
              {!loading && <span className="text-muted-foreground ml-2">({total} 位作者)</span>}
            </h2>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <span className="ml-3 text-muted-foreground">搜索中...</span>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-destructive/10 text-destructive p-4 rounded-lg text-center">
            搜索失败，请稍后重试
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && query && results.length === 0 && (
          <div className="text-center py-12 space-y-3">
            <SearchIcon className="h-12 w-12 mx-auto text-muted-foreground/50" />
            <p className="text-muted-foreground">未找到匹配的作者</p>
            <p className="text-sm text-muted-foreground">尝试使用不同的关键词或检查拼写</p>
          </div>
        )}

        {/* Results List */}
        {!loading && !error && results.length > 0 && (
          <div className="space-y-3">
            {results.map((author, index) => (
              <motion.div
                key={author.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                onClick={() => handleAuthorClick(author.id)}
                className={cn(
                  "bg-card border border-border rounded-xl p-5 cursor-pointer transition-all duration-200",
                  "hover:shadow-lg hover:border-primary/50 hover:-translate-y-0.5"
                )}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 space-y-3">
                    {/* Author Name & ORCID */}
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-primary/10 text-primary rounded-full flex items-center justify-center flex-shrink-0">
                        <User size={20} />
                      </div>
                      <div>
                        <h3 className="text-lg font-bold text-foreground hover:text-primary transition-colors">
                          {author.display_name}
                        </h3>
                        {author.orcid && (
                          <a
                            href={author.orcid}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="text-xs text-muted-foreground hover:text-primary"
                          >
                            ORCID: {author.orcid.split('/').pop()}
                          </a>
                        )}
                      </div>
                    </div>

                    {/* Institution */}
                    {(author.primary_institution_name || author.last_known_institution_name) && (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Building2 size={16} className="flex-shrink-0" />
                        <span>{author.primary_institution_name || author.last_known_institution_name}</span>
                      </div>
                    )}

                    {/* Stats */}
                    <div className="flex items-center gap-6 text-sm">
                      <div className="flex items-center gap-1.5 text-muted-foreground">
                        <FileText size={16} />
                        <span>{author.works_count} 篇论文</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-muted-foreground">
                        <Quote size={16} />
                        <span>{author.cited_by_count} 次引用</span>
                      </div>
                    </div>

                    {/* Research Fields */}
                    {author.research_fields && author.research_fields.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {author.research_fields.slice(0, 3).map((field) => (
                          <span
                            key={field.id}
                            className="px-2 py-1 bg-primary/10 text-primary text-xs rounded-full"
                          >
                            {field.name}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Multiple IDs indicator */}
                    {author.all_ids && author.all_ids.length > 1 && (
                      <div className="text-xs text-muted-foreground bg-secondary/50 inline-block px-2 py-1 rounded">
                        {author.all_ids.length} 个可能的身份
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {/* No Query State */}
        {!query && !loading && (
          <div className="text-center py-12 space-y-3">
            <SearchIcon className="h-12 w-12 mx-auto text-muted-foreground/50" />
            <p className="text-muted-foreground">请输入作者姓名开始搜索</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default AuthorSearchPage;
