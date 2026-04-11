import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchTraces,
  fetchApprovals,
  fetchApprovalDetail,
  fetchHealth,
  resolveApproval,
  fetchOtelTraces,
} from "@/lib/api/mesh";

export function useHealth() {
  return useQuery({
    queryKey: ["mesh", "health"],
    queryFn: fetchHealth,
    refetchInterval: 10000,
  });
}

export function useTraces(opts?: {
  agent?: string;
  tool?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["mesh", "traces", opts],
    queryFn: () => fetchTraces(opts),
    refetchInterval: 5000,
  });
}

export function useOtelTraces(opts?: {
  agent?: string;
  tool?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["mesh", "otel-traces", opts],
    queryFn: () => fetchOtelTraces(opts),
    refetchInterval: 5000,
  });
}

export function useApprovals(opts?: { status?: string; tool?: string }) {
  return useQuery({
    queryKey: ["mesh", "approvals", opts],
    queryFn: () => fetchApprovals(opts),
    refetchInterval: 3000,
  });
}

export function useApprovalDetail(id: string | null) {
  return useQuery({
    queryKey: ["mesh", "approval", id],
    queryFn: () => fetchApprovalDetail(id!),
    enabled: !!id,
  });
}

export function useResolveApproval() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      decision,
      reasoning,
    }: {
      id: string;
      decision: "approve" | "deny";
      reasoning?: string;
    }) => resolveApproval(id, decision, reasoning),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mesh", "approvals"] });
      qc.invalidateQueries({ queryKey: ["mesh", "traces"] });
    },
  });
}
