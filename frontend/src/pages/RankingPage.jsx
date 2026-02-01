import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import api from '../api/client';
import { useTimeFilter } from '../contexts/TimeFilterContext';
import ResearchFieldsBadges from '../components/ResearchFieldsBadges';

function RankingPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { timeRange } = useTimeFilter();
  const [institutions, setInstitutions] = useState([]);
  const [ranking, setRanking] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const selectedInstitutionId = searchParams.get('institution_id');

  useEffect(() => {
    loadInstitutions();
  }, []);

  useEffect(() => {
    if (selectedInstitutionId) {
      loadRanking(selectedInstitutionId);
    } else {
      setRanking(null);
    }
  }, [selectedInstitutionId, timeRange.fromYear, timeRange.toYear]);

  const loadInstitutions = async () => {
    try {
      const data = await api.getInstitutions();
      setInstitutions(data.institutions || []);
    } catch (err) {
      console.error('Failed to load institutions:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadRanking = async (institutionId) => {
    setLoading(true);
    setError(null);

    try {
      const data = await api.getInstitutionRanking(
        institutionId, null, 100, 0, timeRange.fromYear, timeRange.toYear
      );
      setRanking(data);
    } catch (err) {
      console.error('Failed to load ranking:', err);
      setError('Failed to load ranking');
    } finally {
      setLoading(false);
    }
  };

  const handleInstitutionSelect = (institutionId) => {
    setSearchParams({ institution_id: institutionId });
  };

  if (loading && !institutions.length) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin text-4xl mb-4">...</div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="text-sm text-gray-500">
        <Link to="/" className="hover:text-blue-600">Home</Link>
        <span className="mx-2">/</span>
        <span className="text-gray-900">Institution Rankings</span>
      </nav>

      <h1 className="text-2xl font-bold text-gray-900">Institution Author Rankings</h1>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Institution List */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Institutions ({institutions.length})
            </h2>
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {institutions.map((inst) => (
                <button
                  key={inst.id}
                  onClick={() => handleInstitutionSelect(inst.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                    selectedInstitutionId === inst.id
                      ? 'bg-blue-100 text-blue-700 border border-blue-300'
                      : 'hover:bg-gray-100 text-gray-700'
                  }`}
                >
                  <div className="font-medium text-sm truncate">{inst.name}</div>
                  <div className="text-xs text-gray-500">{inst.author_count} authors</div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Ranking Table */}
        <div className="lg:col-span-3">
          {selectedInstitutionId ? (
            loading ? (
              <div className="flex items-center justify-center h-64">
                <div className="text-center">
                  <div className="animate-spin text-4xl mb-4">...</div>
                  <p className="text-gray-600">Loading ranking...</p>
                </div>
              </div>
            ) : error ? (
              <div className="text-center py-12">
                <p className="text-red-500">{error}</p>
              </div>
            ) : ranking ? (
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-gray-900">
                    {ranking.institution_name}
                  </h2>
                  <span className="text-sm text-gray-500">
                    Total {ranking.total} authors
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="text-left py-3 px-2 text-sm font-semibold text-gray-600 w-16">Rank</th>
                        <th className="text-left py-3 px-2 text-sm font-semibold text-gray-600">Author</th>
                        <th className="text-left py-3 px-2 text-sm font-semibold text-gray-600">Research Fields</th>
                        <th className="text-right py-3 px-2 text-sm font-semibold text-gray-600 w-24">Papers</th>
                        <th className="text-right py-3 px-2 text-sm font-semibold text-gray-600 w-24">Citations</th>
                        <th className="text-center py-3 px-2 text-sm font-semibold text-gray-600 w-20">ORCID</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ranking.authors.map((author) => (
                        <tr
                          key={author.id}
                          className="border-b border-gray-100 hover:bg-gray-50"
                        >
                          <td className="py-3 px-2">
                            <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${
                              author.rank <= 3
                                ? 'bg-yellow-100 text-yellow-700'
                                : author.rank <= 10
                                ? 'bg-blue-100 text-blue-600'
                                : 'bg-gray-100 text-gray-600'
                            }`}>
                              {author.rank}
                            </span>
                          </td>
                          <td className="py-3 px-2">
                            <Link
                              to={`/author/${author.id}`}
                              className="text-blue-600 hover:underline font-medium"
                            >
                              {author.display_name}
                            </Link>
                          </td>
                          <td className="py-3 px-2">
                            <ResearchFieldsBadges fields={author.research_fields} maxDisplay={2} />
                          </td>
                          <td className="py-3 px-2 text-right font-mono text-sm">
                            {author.works_count}
                          </td>
                          <td className="py-3 px-2 text-right font-mono text-sm text-gray-600">
                            {author.cited_by_count}
                          </td>
                          <td className="py-3 px-2 text-center">
                            {author.orcid ? (
                              <a
                                href={author.orcid}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-green-600 hover:text-green-700"
                                title={author.orcid}
                              >
                                V
                              </a>
                            ) : (
                              <span className="text-gray-300">-</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null
          ) : (
            <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
              <div className="text-4xl mb-4">...</div>
              <p className="text-gray-500">Select an institution to view the author ranking</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default RankingPage;
