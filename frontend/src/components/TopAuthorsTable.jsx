import { Link } from 'react-router-dom';

function TopAuthorsTable({ authors, title = '高产作者排行' }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-4 py-3 bg-gray-50 border-b">
        <h3 className="font-semibold text-gray-900">{title}</h3>
      </div>
      <div className="divide-y">
        {authors.map((author, index) => (
          <div
            key={author.id}
            className="px-4 py-3 flex items-center justify-between hover:bg-gray-50"
          >
            <div className="flex items-center space-x-3">
              <span
                className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-sm font-bold ${
                  index < 3
                    ? 'bg-yellow-100 text-yellow-700'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                {index + 1}
              </span>
              <Link
                to={`/author/${author.id}`}
                className="font-medium text-gray-900 hover:text-blue-600"
              >
                {author.display_name}
              </Link>
            </div>
            <div className="text-sm text-gray-500">
              {author.paper_count || author.collaboration_count} {author.paper_count ? '篇' : '次合作'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default TopAuthorsTable;
