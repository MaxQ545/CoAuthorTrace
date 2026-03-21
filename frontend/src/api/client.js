const API_BASE = '/api/v1';

class ApiClient {
  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    // Attach admin token for authenticated admin endpoints
    const isAdminAuth = endpoint.startsWith('/admin/') &&
      !endpoint.startsWith('/admin/login') &&
      !endpoint.startsWith('/admin/track');
    if (isAdminAuth) {
      const token = sessionStorage.getItem('admin_token');
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
    }

    const response = await fetch(url, { headers, ...options });

    if (!response.ok) {
      // 401 interceptor — auto-logout on expired/invalid token
      if (response.status === 401 && !endpoint.startsWith('/admin/login')) {
        sessionStorage.removeItem('admin_token');
        sessionStorage.removeItem('admin_role');
        window.location.href = '/admin/login';
        throw new Error('Session expired');
      }
      throw new Error(`API Error: ${response.status}`);
    }

    return response.json();
  }

  // System endpoints
  async getSystemStatus() {
    return this.request('/system/status');
  }

  async getSystemStats() {
    return this.request('/system/status');
  }

  // Author endpoints
  async searchAuthors(query, limit = 20, offset = 0, includeAllIds = true, fuzzy = false) {
    const params = new URLSearchParams({
      q: query,
      limit,
      offset,
      include_all_ids: includeAllIds,
      fuzzy
    });
    return this.request(`/authors/search?${params}`);
  }

  async getAuthor(authorId) {
    return this.request(`/authors/${authorId}`);
  }

  async getAuthorCollaborators(authorId, limit = 50, fromYear = null, toYear = null) {
    const params = new URLSearchParams({ limit });
    if (fromYear) params.append('from_year', fromYear);
    if (toYear) params.append('to_year', toYear);
    return this.request(`/authors/${authorId}/collaborators?${params}`);
  }

  async getAuthorTopRelations(authorId, k = 20, scoreType = 'combined_score') {
    const params = new URLSearchParams({ k, score_type: scoreType });
    return this.request(`/authors/${authorId}/top-relations?${params}`);
  }

  async getAuthorNetworkMetrics(authorId, full = true) {
    const params = new URLSearchParams();
    if (full) params.append('full', 'true');
    const suffix = params.toString() ? `?${params}` : '';
    return this.request(`/authors/${authorId}/network-metrics${suffix}`);
  }

  // Institution endpoints
  async getInstitutions({ query = null, limit = null, offset = 0, refresh = false } = {}) {
    const params = new URLSearchParams();
    if (query) params.append('q', query);
    if (limit !== null && limit !== undefined) params.append('limit', limit);
    if (offset) params.append('offset', offset);
    if (refresh) params.append('refresh', 'true');
    const suffix = params.toString() ? `?${params}` : '';
    return this.request(`/authors/institutions${suffix}`);
  }

  async getInstitutionRanking(institutionId = null, institutionName = null, limit = 50, offset = 0, fromYear = null, toYear = null, fast = true) {
    const params = new URLSearchParams({ limit, offset });
    if (institutionId) params.append('institution_id', institutionId);
    if (institutionName) params.append('institution_name', institutionName);
    if (fromYear) params.append('from_year', fromYear);
    if (toYear) params.append('to_year', toYear);
    if (fast !== null && fast !== undefined) {
      params.append('fast', fast ? 'true' : 'false');
    }
    return this.request(`/authors/ranking/by-institution?${params}`);
  }

  // Admin endpoints
  async adminLogin(password, username = null) {
    const body = { password };
    if (username) body.username = username;
    return this.request('/admin/login', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  async trackVisit(path, authorId = null) {
    return this.request('/admin/track', {
      method: 'POST',
      body: JSON.stringify({ path, author_id: authorId }),
    }).catch(() => {}); // fire-and-forget
  }

  async getAdminAnalytics(days = 30) {
    return this.request(`/admin/analytics?days=${days}`);
  }

  async getAdminVisits(limit = 20, offset = 0) {
    return this.request(`/admin/visits?limit=${limit}&offset=${offset}`);
  }

  async getAdminCrawlStatus() {
    return this.request('/admin/crawl/status');
  }

  async triggerAdminCrawl() {
    return this.request('/admin/crawl/start', { method: 'POST' });
  }

  async getCrawlTargets() {
    return this.request('/admin/crawl/targets');
  }

  async searchOpenAlexInstitution(query) {
    return this.request(`/admin/crawl/search-institution?q=${encodeURIComponent(query)}`);
  }

  async addCrawlTarget(institutionId, institutionName) {
    return this.request('/admin/crawl/targets', {
      method: 'POST',
      body: JSON.stringify({ institution_id: institutionId, institution_name: institutionName }),
    });
  }

  async deleteCrawlTarget(institutionId) {
    return this.request(`/admin/crawl/targets/${institutionId}`, { method: 'DELETE' });
  }

  async initCrawlTargets() {
    return this.request('/admin/crawl/targets/init', { method: 'POST' });
  }

  async getCoAuthoredPapers(authorId, collaboratorId, limit = 20, offset = 0, sortBy = 'publication_date', sortOrder = 'desc', fromYear = null, toYear = null) {
    const params = new URLSearchParams({
      limit,
      offset,
      sort_by: sortBy,
      sort_order: sortOrder
    });
    if (fromYear) params.append('from_year', fromYear);
    if (toYear) params.append('to_year', toYear);
    return this.request(`/authors/${authorId}/co-authored-papers/${collaboratorId}?${params}`);
  }

  // New crawl control endpoints
  async stopCrawl() {
    return this.request('/admin/crawl/stop', { method: 'POST' });
  }

  async stopInstitution(id) {
    return this.request(`/admin/crawl/stop/${id}`, { method: 'POST' });
  }

  async pauseCrawl(id) {
    return this.request(`/admin/crawl/pause/${id}`, { method: 'POST' });
  }

  async resumeCrawl(id) {
    return this.request(`/admin/crawl/resume/${id}`, { method: 'POST' });
  }

  async retryCrawl(id) {
    return this.request(`/admin/crawl/retry/${id}`, { method: 'POST' });
  }

  async reorderQueue(orderedIds) {
    return this.request('/admin/crawl/reorder', {
      method: 'PUT',
      body: JSON.stringify({ ordered_ids: orderedIds }),
    });
  }

  async getCrawlProgress() {
    return this.request('/admin/crawl/progress');
  }
}

export const api = new ApiClient();
export default api;
