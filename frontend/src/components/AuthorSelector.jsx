import { useState, useEffect, useRef } from 'react';
import { Search, X, Loader2, UserPlus, Users } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api from '../api/client';

/**
 * Multi-author search & select component with chips.
 *
 * Props:
 * - selectedAuthors: Array of { id, display_name, institution? }
 * - onAdd: (author) => void
 * - onRemove: (authorId) => void
 * - maxAuthors: number (default 5)
 * - disabled: boolean
 */
function AuthorSelector({ selectedAuthors = [], onAdd, onRemove, maxAuthors = 5, disabled = false }) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);

  const containerRef = useRef(null);
  const inputRef = useRef(null);

  const selectedIds = new Set(selectedAuthors.map(a => a.id));
  const atLimit = selectedAuthors.length >= maxAuthors;

  // Debounced search
  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setSuggestions([]);
      setShowDropdown(false);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);

    const timeout = setTimeout(async () => {
      try {
        const response = await api.searchAuthors(trimmed, 8, 0, false, false);
        const results = (response.results || []).filter(a => !selectedIds.has(a.id));
        setSuggestions(results);
        setShowDropdown(true);
        setSelectedIndex(-1);
      } catch (error) {
        console.error('Author search failed:', error);
        setSuggestions([]);
        setShowDropdown(false);
      } finally {
        setIsSearching(false);
      }
    }, 500);

    return () => clearTimeout(timeout);
  }, [query]);

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setShowDropdown(false);
        setSelectedIndex(-1);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (author) => {
    if (atLimit || selectedIds.has(author.id)) return;
    onAdd({
      id: author.id,
      display_name: author.display_name,
      institution: author.primary_institution_name || author.last_known_institution_name || null,
      works_count: author.works_count,
    });
    setQuery('');
    setSuggestions([]);
    setShowDropdown(false);
    setSelectedIndex(-1);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e) => {
    if (!showDropdown || suggestions.length === 0) {
      // Backspace when input empty removes last chip
      if (e.key === 'Backspace' && query === '' && selectedAuthors.length > 0) {
        onRemove(selectedAuthors[selectedAuthors.length - 1].id);
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev => prev < suggestions.length - 1 ? prev + 1 : prev);
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => prev > 0 ? prev - 1 : -1);
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0 && suggestions[selectedIndex]) {
          handleSelect(suggestions[selectedIndex]);
        }
        break;
      case 'Escape':
        e.preventDefault();
        setShowDropdown(false);
        setSelectedIndex(-1);
        break;
    }
  };

  return (
    <div ref={containerRef} className="relative">
      {/* Input area with chips */}
      <div
        className={`flex flex-wrap items-center gap-2 px-3 py-2 bg-background border border-border rounded-xl transition-colors min-h-[48px] ${
          disabled ? 'opacity-50 pointer-events-none' : 'focus-within:ring-2 focus-within:ring-primary focus-within:border-primary'
        }`}
        onClick={() => inputRef.current?.focus()}
      >
        {/* Selected author chips */}
        <AnimatePresence mode="popLayout">
          {selectedAuthors.map((author) => (
            <motion.span
              key={author.id}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              layout
              className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-primary/10 text-primary text-sm font-medium rounded-lg border border-primary/20"
            >
              <span className="truncate max-w-[120px]">{author.display_name}</span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onRemove(author.id);
                }}
                className="p-0.5 hover:bg-primary/20 rounded transition-colors"
                disabled={disabled}
              >
                <X size={12} />
              </button>
            </motion.span>
          ))}
        </AnimatePresence>

        {/* Search input */}
        {!atLimit && (
          <div className="flex-1 flex items-center gap-2 min-w-[140px]">
            <Search size={14} className="text-muted-foreground shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={selectedAuthors.length === 0 ? '搜索并添加作者...' : '继续添加...'}
              className="flex-1 bg-transparent text-foreground placeholder:text-muted-foreground outline-none text-sm py-0.5"
              disabled={disabled}
            />
            {isSearching && <Loader2 size={14} className="animate-spin text-muted-foreground" />}
          </div>
        )}

        {atLimit && (
          <span className="text-xs text-muted-foreground">已达最大数量 ({maxAuthors})</span>
        )}
      </div>

      {/* Helper text */}
      <div className="flex items-center justify-between mt-1.5 px-1">
        <span className="text-xs text-muted-foreground flex items-center gap-1">
          <Users size={10} />
          {selectedAuthors.length}/{maxAuthors} 位作者
        </span>
        {selectedAuthors.length >= 2 && (
          <span className="text-xs text-primary font-medium">可以开始构建网络</span>
        )}
      </div>

      {/* Suggestions dropdown */}
      <AnimatePresence>
        {showDropdown && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.15 }}
            className="absolute top-full left-0 right-0 mt-2 z-50 bg-popover border border-border rounded-xl shadow-xl max-h-72 overflow-y-auto"
          >
            {suggestions.length > 0 ? (
              <ul>
                {suggestions.map((author, index) => (
                  <li
                    key={author.id}
                    className={`px-4 py-3 cursor-pointer transition-colors border-b border-border/50 last:border-b-0 ${
                      index === selectedIndex ? 'bg-accent' : 'hover:bg-accent/50'
                    }`}
                    onClick={() => handleSelect(author)}
                    onMouseEnter={() => setSelectedIndex(index)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-foreground text-sm">{author.display_name}</div>
                        <div className="text-xs text-muted-foreground truncate mt-0.5">
                          {author.primary_institution_name || author.last_known_institution_name || '未知机构'}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0 ml-3">
                        <span className="text-xs bg-secondary px-2 py-0.5 rounded text-secondary-foreground">
                          {author.works_count} 篇
                        </span>
                        <UserPlus size={14} className="text-primary opacity-0 group-hover:opacity-100" />
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            ) : !isSearching ? (
              <div className="px-4 py-3 text-sm text-muted-foreground">
                未找到匹配的作者
              </div>
            ) : (
              <div className="px-4 py-3 text-sm text-muted-foreground flex items-center gap-2">
                <Loader2 size={14} className="animate-spin" />
                搜索中...
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default AuthorSelector;
