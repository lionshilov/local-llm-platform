import { useCallback, useEffect, useState } from "react";
import { listModels } from "../lib/api";
import type { ModelInfo } from "../lib/types";

const POLL_MS = 5_000;

export type GatewayStatus = "connecting" | "online" | "offline";

/**
 * Poll the gateway so engines started or stopped later show up without a reload. When the
 * gateway itself is unreachable every backend is reported offline: stale "online" dots
 * would invite requests that can only fail.
 */
export function useModels() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [defaultModel, setDefaultModel] = useState<string | null>(null);
  const [status, setStatus] = useState<GatewayStatus>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    const poll = async () => {
      const started = performance.now();
      try {
        const list = await listModels(controller.signal);
        setLatencyMs(performance.now() - started);
        setModels(list.models);
        setDefaultModel(list.defaultModel);
        setStatus("online");
        setError(null);
      } catch (e) {
        if (controller.signal.aborted) return;
        setStatus("offline");
        setLatencyMs(null);
        setError(e instanceof Error ? e.message : "Gateway unreachable");
        setModels((current) => current.map((m) => ({ ...m, available: false })));
      }
    };
    void poll();
    const timer = setInterval(() => void poll(), POLL_MS);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [tick]);

  return { models, defaultModel, status, error, latencyMs, refresh };
}
