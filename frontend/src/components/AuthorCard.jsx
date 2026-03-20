import { Link } from 'react-router-dom';
import { useState } from 'react';
import { Building2, FileText, BarChart3 } from 'lucide-react';
import ResearchFieldsBadges from './ResearchFieldsBadges';

function AuthorCard({
  author,
  showCollabCount = false,
  collabCount = 0,
  rank = null,
  showViewPapersButton = false,
  mainAuthorId = null,
  onViewPapers = null
}) {
  const [showAllIds, setShowAllIds] = useState(false);
  const hasMultipleIds = author.all_ids && author.all_ids.length > 1;
  const displayInstitution = author.primary_institution_name || author.last_known_institution_name;

  return (
    <div className="bg-card rounded-lg border border-border p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2">
            {rank && (
              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 text-primary text-sm font-bold">
                {rank}
              </span>
            )}
            <Link
              to={`/author/${author.id}`}
              className="text-lg font-semibold text-foreground hover:text-primary"
            >
              {author.display_name}
            </Link>
            {hasMultipleIds && (
              <span className="text-xs bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 px-2 py-0.5 rounded-full">
                {author.all_ids.length} 个ID合并
              </span>
            )}
          </div>

          {displayInstitution && (
            <p className="text-sm text-muted-foreground mt-1 flex items-center gap-1">
              <Building2 className="w-3.5 h-3.5" /> {displayInstitution}
            </p>
          )}

          {/* Research Fields */}
          {author.research_fields && author.research_fields.length > 0 && (
            <div className="mt-2">
              <ResearchFieldsBadges fields={author.research_fields} maxDisplay={3} />
            </div>
          )}

          {/* ID and ORCID info */}
          <div className="mt-2 text-xs text-muted-foreground">
            {hasMultipleIds ? (
              <div>
                <button
                  onClick={() => setShowAllIds(!showAllIds)}
                  className="text-primary hover:underline flex items-center"
                >
                  {showAllIds ? '收起' : '展开'} {author.all_ids.length} 个ID
                  <span className="ml-1">{showAllIds ? '▲' : '▼'}</span>
                </button>
                {showAllIds && (
                  <div className="mt-2 space-y-1 bg-secondary/30 p-2 rounded max-h-32 overflow-y-auto">
                    {author.all_ids.map((idInfo) => (
                      <div key={idInfo.id} className="flex justify-between items-center">
                        <span>
                          <code className="bg-muted px-1 rounded text-foreground">{idInfo.id}</code>
                          <span className="text-muted-foreground ml-1">({idInfo.works_count}篇)</span>
                        </span>
                        {idInfo.orcid ? (
                          <a
                            href={idInfo.orcid}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline"
                          >
                            {idInfo.orcid.split('/').pop()}
                          </a>
                        ) : (
                          <span className="text-muted-foreground/30">无ORCID</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                <code className="bg-muted px-1 rounded text-foreground">{author.id}</code>
                {author.orcid && (
                  <a
                    href={author.orcid}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    ORCID
                  </a>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="text-right text-sm">
          {showCollabCount ? (
            <div>
              <div className="text-primary font-medium">
                {collabCount} 次合作
              </div>
              {(() => {
                const strength = Math.min(collabCount / 10, 1);
                const barColor = strength > 0.7 ? 'bg-green-500' : strength >= 0.3 ? 'bg-yellow-500' : 'bg-gray-300';
                return (
                  <div className="mt-1 w-16 h-1.5 bg-muted rounded-full overflow-hidden ml-auto">
                    <div
                      className={`h-full rounded-full ${barColor}`}
                      style={{ width: `${strength * 100}%` }}
                    />
                  </div>
                );
              })()}
            </div>
          ) : (
            <>
              {author.works_count > 0 && (
                <div className="text-muted-foreground flex items-center gap-1">
                  <FileText className="w-3.5 h-3.5" /> {author.works_count} 篇{hasMultipleIds && '(合并)'}
                </div>
              )}
              {author.cited_by_count > 0 && (
                <div className="text-muted-foreground flex items-center gap-1">
                  <BarChart3 className="w-3.5 h-3.5" /> {author.cited_by_count} 次引用
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          to={`/author/${author.id}`}
          className="text-xs px-3 py-1 bg-secondary text-secondary-foreground rounded-full hover:bg-secondary/80 transition-colors"
        >
          查看详情
        </Link>
        <Link
          to={`/network/${author.id}`}
          className="text-xs px-3 py-1 bg-primary/10 text-primary rounded-full hover:bg-primary/20 transition-colors"
        >
          合作网络
        </Link>
        {showViewPapersButton && mainAuthorId && onViewPapers && (
          <button
            onClick={() => onViewPapers(author.id, author.display_name)}
            className="text-xs px-3 py-1 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 rounded-full hover:bg-emerald-200 dark:hover:bg-emerald-900/50 transition-colors"
          >
            查看 {collabCount} 篇合作论文
          </button>
        )}
      </div>
    </div>
  );
}

export default AuthorCard;
