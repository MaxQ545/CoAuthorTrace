import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';

function SearchBox({ onSearch, placeholder = '搜索作者...', loading = false, defaultValue = '' }) {
  const [query, setQuery] = useState(defaultValue);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState(false);

  const navigate = useNavigate();
  const containerRef = useRef(null);

  // 同步 defaultValue
  useEffect(() => {
    setQuery(defaultValue);
  }, [defaultValue]);

  // 实时搜索建议（无延迟）
  useEffect(() => {
    const trimmedQuery = query.trim();

    // 输入长度 < 1 时隐藏建议
    if (trimmedQuery.length < 1) {
      setSuggestions([]);
      setShowSuggestions(false);
      setIsLoadingSuggestions(false);
      return;
    }

    // 立即触发搜索
    const fetchSuggestions = async () => {
      setIsLoadingSuggestions(true);
      try {
        const response = await api.searchAuthors(trimmedQuery, 10, 0, false, true);
        setSuggestions(response.results || []);
        setShowSuggestions(true);
        setSelectedIndex(-1);
      } catch (error) {
        console.error('Failed to fetch author suggestions:', error);
        setSuggestions([]);
        setShowSuggestions(false);
      } finally {
        setIsLoadingSuggestions(false);
      }
    };

    fetchSuggestions();
  }, [query]);

  // 点击外部关闭下拉列表
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setShowSuggestions(false);
        setSelectedIndex(-1);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();

    // 如果选中了建议项，跳转到作者详情页
    if (selectedIndex >= 0 && suggestions[selectedIndex]) {
      const author = suggestions[selectedIndex];
      navigate(`/author/${author.id}`);
      setShowSuggestions(false);
      return;
    }

    // 否则触发传统搜索
    if (query.trim()) {
      onSearch(query.trim());
      setShowSuggestions(false);
    }
  };

  const handleKeyDown = (e) => {
    if (!showSuggestions || suggestions.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev =>
          prev < suggestions.length - 1 ? prev + 1 : prev
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => prev > 0 ? prev - 1 : -1);
        break;
      case 'Escape':
        e.preventDefault();
        setShowSuggestions(false);
        setSelectedIndex(-1);
        break;
      default:
        break;
    }
  };

  const handleSuggestionClick = (author) => {
    navigate(`/author/${author.id}`);
    setShowSuggestions(false);
    setSelectedIndex(-1);
  };

  const getInstitutionName = (author) => {
    return author.primary_institution_name ||
           author.last_known_institution_name ||
           '未知机构';
  };

  return (
    <div ref={containerRef} className="relative">
      <form onSubmit={handleSubmit}>
        <div className="flex">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
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

      {/* 下拉建议列表 */}
      {showSuggestions && (
        <div className="absolute top-full left-0 right-0 mt-2 z-50 bg-background border border-border rounded-lg shadow-lg max-h-96 overflow-y-auto text-left">
          {isLoadingSuggestions ? (
            <div className="px-4 py-3 text-muted-foreground text-sm">
              <span className="inline-block animate-spin mr-2">⏳</span>
              搜索中...
            </div>
          ) : suggestions.length > 0 ? (
            <ul>
              {suggestions.map((author, index) => (
                <li
                  key={author.id}
                  className={`px-4 py-3 cursor-pointer transition-colors border-b border-border last:border-b-0 ${
                    index === selectedIndex ? 'bg-muted' : 'hover:bg-muted'
                  }`}
                  onClick={() => handleSuggestionClick(author)}
                  onMouseEnter={() => setSelectedIndex(index)}
                >
                  <div className="text-foreground font-medium">
                    {author.display_name}
                  </div>
                  <div className="text-muted-foreground text-sm mt-1">
                    {getInstitutionName(author)}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="px-4 py-3 text-muted-foreground text-sm">
              未找到匹配的作者
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default SearchBox;
