import { Link } from 'react-router-dom';
import { useState } from 'react';
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
    <div className="bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2">
            {rank && (
              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-100 text-blue-600 text-sm font-bold">
                {rank}
              </span>
            )}
            <Link
              to={`/author/${author.id}`}
              className="text-lg font-semibold text-gray-900 hover:text-blue-600"
            >
              {author.display_name}
            </Link>
            {hasMultipleIds && (
              <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">
                {author.all_ids.length} 个ID合并
              </span>
            )}
          </div>

          {displayInstitution && (
            <p className="text-sm text-gray-600 mt-1">
              🏛️ {displayInstitution}
            </p>
          )}

          {/* Research Fields */}
          {author.research_fields && author.research_fields.length > 0 && (
            <div className="mt-2">
              <ResearchFieldsBadges fields={author.research_fields} maxDisplay={3} />
            </div>
          )}

          {/* ID and ORCID info */}
          <div className="mt-2 text-xs text-gray-500">
            {hasMultipleIds ? (
              <div>
                <button
                  onClick={() => setShowAllIds(!showAllIds)}
                  className="text-blue-600 hover:underline flex items-center"
                >
                  {showAllIds ? '收起' : '展开'} {author.all_ids.length} 个ID
                  <span className="ml-1">{showAllIds ? '▲' : '▼'}</span>
                </button>
                {showAllIds && (
                  <div className="mt-2 space-y-1 bg-gray-50 p-2 rounded max-h-32 overflow-y-auto">
                    {author.all_ids.map((idInfo) => (
                      <div key={idInfo.id} className="flex justify-between items-center">
                        <span>
                          <code className="bg-gray-200 px-1 rounded">{idInfo.id}</code>
                          <span className="text-gray-400 ml-1">({idInfo.works_count}篇)</span>
                        </span>
                        {idInfo.orcid ? (
                          <a
                            href={idInfo.orcid}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-500 hover:underline"
                          >
                            {idInfo.orcid.split('/').pop()}
                          </a>
                        ) : (
                          <span className="text-gray-300">无ORCID</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                <code className="bg-gray-100 px-1 rounded">{author.id}</code>
                {author.orcid && (
                  <a
                    href={author.orcid}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:underline"
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
            <div className="text-blue-600 font-medium">
              {collabCount} 次合作
            </div>
          ) : (
            <>
              {author.works_count > 0 && (
                <div className="text-gray-600">
                  📄 {author.works_count} 篇{hasMultipleIds && '(合并)'}
                </div>
              )}
              {author.cited_by_count > 0 && (
                <div className="text-gray-600">
                  📊 {author.cited_by_count} 次引用
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          to={`/author/${author.id}`}
          className="text-xs px-3 py-1 bg-gray-100 text-gray-700 rounded-full hover:bg-gray-200"
        >
          查看详情
        </Link>
        <Link
          to={`/network/${author.id}`}
          className="text-xs px-3 py-1 bg-blue-100 text-blue-700 rounded-full hover:bg-blue-200"
        >
          合作网络
        </Link>
        {showViewPapersButton && mainAuthorId && onViewPapers && (
          <button
            onClick={() => onViewPapers(author.id, author.display_name)}
            className="text-xs px-3 py-1 bg-green-100 text-green-700 rounded-full hover:bg-green-200"
          >
            查看 {collabCount} 篇合作论文
          </button>
        )}
      </div>
    </div>
  );
}

export default AuthorCard;
