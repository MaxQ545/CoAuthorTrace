import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
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
  adminVisits: (limit, offset) => ['adminVisits', limit, offset],
  adminCrawlTargets: ['adminCrawlTargets'],
  adminCrawlStatus: ['adminCrawlStatus'],
  adminCrawlProgress: ['adminCrawlProgress'],
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

export function useAdminVisits(limit = 20, offset = 0) {
  return useQuery({
    queryKey: queryKeys.adminVisits(limit, offset),
    queryFn: () => api.getAdminVisits(limit, offset),
    keepPreviousData: true,
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
// Admin: crawl progress (adaptive polling)
// ---------------------------------------------------------------------------
export function useCrawlProgress({ enabled = true } = {}) {
  return useQuery({
    queryKey: queryKeys.adminCrawlProgress,
    queryFn: () => api.getCrawlProgress(),
    enabled,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.institutions?.some(i => ['running', 'pause_requested', 'stop_requested'].includes(i.status))) {
        return 3000;
      }
      return 30000;
    },
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
      toast.success('Crawl started');
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlStatus });
        queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlProgress });
      }, 2000);
    },
    onError: (error) => toast.error(`Failed to start crawl: ${error.message}`),
  });
}

export function useAddCrawlTarget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ institutionId, institutionName }) =>
      api.addCrawlTarget(institutionId, institutionName),
    onSuccess: () => {
      toast.success('Target added');
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlTargets });
    },
    onError: (error) => toast.error(`Failed to add target: ${error.message}`),
  });
}

export function useDeleteCrawlTarget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (institutionId) => api.deleteCrawlTarget(institutionId),
    onSuccess: () => {
      toast.success('Target deleted');
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlTargets });
    },
    onError: (error) => toast.error(`Failed to delete target: ${error.message}`),
  });
}

export function useInitCrawlTargets() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.initCrawlTargets(),
    onSuccess: () => {
      toast.success('Default targets imported');
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlTargets });
    },
    onError: (error) => toast.error(`Failed to import defaults: ${error.message}`),
  });
}

// ---------------------------------------------------------------------------
// Admin: new crawl control mutations
// ---------------------------------------------------------------------------
export function useStopCrawl() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.stopCrawl(),
    onSuccess: () => {
      toast.success('Stop signal sent to all crawls');
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlProgress });
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlStatus });
    },
    onError: (error) => toast.error(`Failed to stop crawl: ${error.message}`),
  });
}

export function useStopInstitution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id) => api.stopInstitution(id),
    onSuccess: () => {
      toast.success('Stop signal sent');
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlProgress });
    },
    onError: (error) => toast.error(`Failed to stop institution: ${error.message}`),
  });
}

export function usePauseCrawl() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id) => api.pauseCrawl(id),
    onSuccess: () => {
      toast.success('Pause signal sent');
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlProgress });
    },
    onError: (error) => toast.error(`Failed to pause crawl: ${error.message}`),
  });
}

export function useResumeCrawl() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id) => api.resumeCrawl(id),
    onSuccess: () => {
      toast.success('Crawl resumed');
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlProgress });
    },
    onError: (error) => toast.error(`Failed to resume crawl: ${error.message}`),
  });
}

export function useRetryCrawl() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id) => api.retryCrawl(id),
    onSuccess: () => {
      toast.success('Retry queued');
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlProgress });
    },
    onError: (error) => toast.error(`Failed to retry crawl: ${error.message}`),
  });
}

export function useReorderQueue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (orderedIds) => api.reorderQueue(orderedIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.adminCrawlProgress });
    },
    onError: (error) => toast.error(`Failed to reorder queue: ${error.message}`),
  });
}
