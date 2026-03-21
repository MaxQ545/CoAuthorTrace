import { useState, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuthorSearch } from '../hooks/queries';
import SearchBox from '../components/SearchBox';
import { motion } from 'framer-motion';
import { User, Building2, FileText, Quote, Loader2, Search as SearchIcon, Tag } from 'lucide-react';
import { cn } from '../lib/utils';

function AuthorSearchPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const query = searchParams.get('q') || '';
  const [selectedFields, setSelectedFields] = useState(new Set());

  const { data, isLoading: loading, error } = useAuthorSearch(query, 50, 0, true);
  const results = data?.results || [];
  const total = data?.total || 0;

  // Extract top 8 most common research fields from results
  const topFields = useMemo(() => {
    const fieldCounts = new Map();
    for (const author of results) {
      if (author.research_fields) {
        for (const field of author.research_fields) {
          const name = field.display_name || field.name;
          if (name) {
            fieldCounts.set(name, (fieldCounts.get(name) || 0) + 1);
          }
        }
      }
    }
    return [...fieldCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([name]) => name);
  }, [results]);

  // Filter results by selected fields (OR logic)
  const filteredResults = useMemo(() => {
    if (selectedFields.size === 0) return results;
    return results.filter((author) =>
      author.research_fields?.some((field) =>
        selectedFields.has(field.display_name || field.name)
      )
    );
  }, [results, selectedFields]);

  const toggleField = (fieldName) => {
    setSelectedFields((prev) => {
      const next = new Set(prev);
      if (next.has(fieldName)) {
        next.delete(fieldName);
      } else {
        next.add(fieldName);
      }
      return next;
    });
  };

  const clearFields = () => setSelectedFields(new Set());

  const handleSearch = (newQuery) => {
    navigate(`/authors/search?q=${encodeURIComponent(newQuery)}`);
  };

  const handleAuthorClick = (authorId) => {
    navigate(`/author/${authorId}`);
  };

  return (
    <div className="space-y-6">
      {/* Search Header */}
      <div className="bg-secondary/30 rounded-2xl p-6 border border-border">
        <div className="max-w-2xl mx-auto space-y-4">
          <h1 className="text-2xl font-bold text-center text-foreground">作者搜索</h1>
          <SearchBox
            onSearch={handleSearch}
            placeholder="输入作者姓名搜索..."
            defaultValue={query}
          />
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

        {/* Research Field Filter Chips */}
        {!loading && !error && topFields.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1.5 text-sm text-muted-foreground mr-1">
              <Tag size={16} />
              <span>领域筛选</span>
            </div>
            {topFields.map((fieldName) => (
              <button
                key={fieldName}
                onClick={() => toggleField(fieldName)}
                className={cn(
                  "px-3 py-1 text-xs rounded-full transition-colors duration-150",
                  selectedFields.has(fieldName)
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
              >
                {fieldName}
              </button>
            ))}
            {selectedFields.size > 0 && (
              <button
                onClick={clearFields}
                className="px-3 py-1 text-xs rounded-full border border-border text-muted-foreground hover:text-foreground transition-colors"
              >
                清除
              </button>
            )}
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
        {!loading && !error && query && filteredResults.length === 0 && (
          <div className="text-center py-12 space-y-3">
            <SearchIcon className="h-12 w-12 mx-auto text-muted-foreground/50" />
            <p className="text-muted-foreground">未找到匹配的作者</p>
            <p className="text-sm text-muted-foreground">尝试使用不同的关键词或检查拼写</p>
          </div>
        )}

        {/* Results List */}
        {!loading && !error && filteredResults.length > 0 && (
          <div className="space-y-3">
            {filteredResults.map((author, index) => (
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
                            {field.display_name}
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
