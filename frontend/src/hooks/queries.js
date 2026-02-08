import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api/client';

// ---------------------------------------------------------------------------
// Query key factories
// ---------------------------------------------------------------------------
export const queryKeys = {
  systemStats: ['systemStats'],
  authorSearch: (query, limit, offset, includeAllIds, fuzzy) =>
    ['authorSearch', query, limit, offset, includeAllIds, fuzzy],
  author: (authorId) => ['author', authorId],
  authorCollaborators: (authorId, fromYear, toYear) =>
    ['authorCollaborators', authorId, fromYear, toYear],
  authorTopRelations: (authorId, topK) =>
    ['authorTopRelations', authorId, topK],
  networkMetrics: (authorId) => ['networkMetrics', authorId],
  coAuthoredPapers: (authorId, collaboratorId, limit, offset, sortBy, sortOrder, fromYear, toYear) =>
    ['coAuthoredPapers', authorId, collaboratorId, limit, offset, sortBy, sortOrder, fromYear, toYear],
  institutions: (query) => ['institutions', query],
  institutionRanking: (institutionId, sortBy, limit, offset) =>
    ['institutionRanking', institutionId, sortBy, limit, offset],
  adminAnalytics: (days) => ['adminAnalytics', days],
  adminCrawlTargets: ['adminCrawlTargets'],
  adminCrawlStatus: ['adminCrawlStatus'],
};

// ---------------------------------------------------------------------------
// System
// ---------------------------------------------------------------------------
export function useSystemStats() {
  return useQuery({
    queryKey: queryKeys.systemStats,
    queryFn: () => api.getSystemStats(),
    staleTime: 5 * 60 * 1000,
    select: (data) => ({
      works_count: data.database.total_works,
      authors_count: data.database.total_authors,
      collaborations_count: data.database.total_collaborations,
      total_relationship_scores: data.database.total_relationship_scores,
      last_crawl_date: data.crawl.last_crawl_date,
      status: data.status,
    }),
  });
}

// ---------------------------------------------------------------------------
// Author search
// ---------------------------------------------------------------------------
export function useAuthorSearch(query, limit = 50, offset = 0, includeAllIds = true, fuzzy = false) {
  return useQuery({
    queryKey: queryKeys.authorSearch(query, limit, offset, includeAllIds, fuzzy),
    queryFn: () => api.searchAuthors(query, limit, offset, includeAllIds, fuzzy),
    enabled: !!query,
  });
}

// ---------------------------------------------------------------------------
// Author detail (shared between AuthorPage and NetworkPage)
// ---------------------------------------------------------------------------
export function useAuthor(authorId) {
  return useQuery({
    queryKey: queryKeys.author(authorId),
    queryFn: () => api.getAuthor(authorId),
    enabled: !!authorId,
  });
}

// ---------------------------------------------------------------------------
// Author collaborators
// ---------------------------------------------------------------------------
export function useAuthorCollaborators(authorId, limit = 30, fromYear = null, toYear = null) {
  return useQuery({
    queryKey: queryKeys.authorCollaborators(authorId, fromYear, toYear),
    queryFn: () => api.getAuthorCollaborators(authorId, limit, fromYear, toYear),
    enabled: !!authorId,
    select: (data) => data.collaborators || [],
  });
}

// ---------------------------------------------------------------------------
// Author top relations
// ---------------------------------------------------------------------------
export function useTopRelations(authorId, topK = 20) {
  return useQuery({
    queryKey: queryKeys.authorTopRelations(authorId, topK),
    queryFn: () => api.getAuthorTopRelations(authorId, topK),
    enabled: !!authorId,
  });
}

// ---------------------------------------------------------------------------
// Network metrics
// ---------------------------------------------------------------------------
export function useNetworkMetrics(authorId) {
  return useQuery({
    queryKey: queryKeys.networkMetrics(authorId),
    queryFn: () => api.getAuthorNetworkMetrics(authorId, true),
    enabled: !!authorId,
    staleTime: 10 * 60 * 1000,
    select: (data) => data.metrics,
  });
}

// ---------------------------------------------------------------------------
// Co-authored papers
// ---------------------------------------------------------------------------
export function useCoAuthoredPapers(authorId, collaboratorId, limit = 10, offset = 0, sortBy = 'publication_date', sortOrder = 'desc', fromYear = null, toYear = null) {
  return useQuery({
    queryKey: queryKeys.coAuthoredPapers(authorId, collaboratorId, limit, offset, sortBy, sortOrder, fromYear, toYear),
    queryFn: () => api.getCoAuthoredPapers(authorId, collaboratorId, limit, offset, sortBy, sortOrder, fromYear, toYear),
    enabled: !!authorId && !!collaboratorId,
  });
}

// ---------------------------------------------------------------------------
// Institutions
// ---------------------------------------------------------------------------
export function useInstitutions(query = null) {
  return useQuery({
    queryKey: queryKeys.institutions(query),
    queryFn: () => api.getInstitutions({ query: query || null, limit: 300, offset: 0 }),
    staleTime: 5 * 60 * 1000,
    select: (data) => data.institutions || [],
  });
}

// ---------------------------------------------------------------------------
// Institution ranking
// ---------------------------------------------------------------------------
export function useInstitutionRanking(institutionId) {
  return useQuery({
    queryKey: queryKeys.institutionRanking(institutionId),
    queryFn: () => api.getInstitutionRanking(institutionId, null, 100, 0, null, null, false),
    enabled: !!institutionId,
  });
}

// ---------------------------------------------------------------------------
// Admin: analytics
// ---------------------------------------------------------------------------
export function useAdminAnalytics(days = 30, { enabled = true } = {}) {
  return useQuery({
    queryKey: queryKeys.adminAnalytics(days),
    queryFn: () => api.getAdminAnalytics(days),
    staleTime: 1 * 60 * 1000,
    enabled,
  });
}

// ---------------------------------------------------------------------------
// Admin: crawl targets
// ---------------------------------------------------------------------------
export function useAdminCrawlTargets({ enabled = true } = {}) {
  return useQuery({
    queryKey: queryKeys.adminCrawlTargets,
    queryFn: () => api.getCrawlTargets(),
    enabled,
  });
}

// ---------------------------------------------------------------------------
// Admin: crawl status
// ---------------------------------------------------------------------------
export function useAdminCrawlStatus({ enabled = true } = {}) {
  return useQuery({
    queryKey: queryKeys.adminCrawlStatus,
    queryFn: () => api.getAdminCrawlStatus(),
    refetchInterval: 30 * 1000,
    enabled,
  });
}

// ---------------------------------------------------------------------------
// Admin mutations
// ---------------------------------------------------------------------------
export function useStartCrawl() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.triggerAdminCrawl(),
    onSuccess: () => {
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlStatus });
      }, 2000);
    },
  });
}

export function useAddCrawlTarget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ institutionId, institutionName }) =>
      api.addCrawlTarget(institutionId, institutionName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlTargets });
    },
  });
}

export function useDeleteCrawlTarget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (institutionId) => api.deleteCrawlTarget(institutionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlTargets });
    },
  });
}

export function useInitCrawlTargets() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.initCrawlTargets(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlTargets });
    },
  });
}
