import { useQuery } from "@tanstack/react-query";
import {
  fetchMem7Health,
  fetchMem7Info,
  fetchMemories,
  fetchMemoryDetail,
  searchMemories,
} from "@/lib/api/mem7";

export function useMem7Health() {
  return useQuery({
    queryKey: ["mem7", "health"],
    queryFn: fetchMem7Health,
    refetchInterval: 15000,
    retry: 1,
  });
}

export function useMem7Info() {
  return useQuery({
    queryKey: ["mem7", "info"],
    queryFn: fetchMem7Info,
    staleTime: 60000,
    retry: 1,
  });
}

export function useMemories(opts?: { tags?: string[]; agent?: string }) {
  return useQuery({
    queryKey: ["mem7", "memories", opts],
    queryFn: () => fetchMemories(opts),
    refetchInterval: 10000,
  });
}

export function useMemoryDetail(key: string | null) {
  return useQuery({
    queryKey: ["mem7", "memory", key],
    queryFn: () => fetchMemoryDetail(key!),
    enabled: !!key,
  });
}

export function useMemorySearch(query: string, opts?: { agent?: string; tags?: string[]; limit?: number }) {
  return useQuery({
    queryKey: ["mem7", "search", query, opts],
    queryFn: () => searchMemories({ query, ...opts }),
    enabled: query.length >= 2,
  });
}
