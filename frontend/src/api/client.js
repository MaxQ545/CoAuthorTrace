const API_BASE = '/api/v1';

class ApiClient {
  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }

    return response.json();
  }

  // System endpoints
  async getSystemStatus() {
    return this.request('/system/status');
  }

  async getSystemStats() {
    return this.request('/system/stats');
  }

  // Author endpoints
  async searchAuthors(query, limit = 20, offset = 0, includeAllIds = true) {
    const params = new URLSearchParams({
      q: query,
      limit,
      offset,
      include_all_ids: includeAllIds
    });
    return this.request(`/authors/search?${params}`);
  }

  async getAuthor(authorId) {
    return this.request(`/authors/${authorId}`);
  }

  async getAuthorCollaborators(authorId, limit = 50) {
    const params = new URLSearchParams({ limit });
    return this.request(`/authors/${authorId}/collaborators?${params}`);
  }

  async getAuthorTopRelations(authorId, k = 20, scoreType = 'combined_score') {
    const params = new URLSearchParams({ k, score_type: scoreType });
    return this.request(`/authors/${authorId}/top-relations?${params}`);
  }

  async getAuthorNetworkMetrics(authorId) {
    return this.request(`/authors/${authorId}/network-metrics`);
  }

  // Institution endpoints
  async getInstitutions() {
    return this.request('/authors/institutions');
  }

  async getInstitutionRanking(institutionId = null, institutionName = null, limit = 50, offset = 0) {
    const params = new URLSearchParams({ limit, offset });
    if (institutionId) params.append('institution_id', institutionId);
    if (institutionName) params.append('institution_name', institutionName);
    return this.request(`/authors/ranking/by-institution?${params}`);
  }
}

export const api = new ApiClient();
export default api;
