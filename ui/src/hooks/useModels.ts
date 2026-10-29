import { useEffect, useState } from "react";
import { listModels } from "../lib/api";
import type { ModelInfo } from "../lib/types";

const POLL_MS = 10_000;

/** Poll the gateway so engines started or stopped later show up without a reload. */
export function useModels() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [defaultModel, setDefaultModel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const refresh = async () => {
      try {
        const list = await listModels(controller.signal);
        setModels(list.models);
        setDefaultModel(list.defaultModel);
        setError(null);
      } catch (e) {
        if (!controller.signal.aborted) {
          setError(e instanceof Error ? e.message : "Gateway unreachable");
        }
      } finally {
        setLoaded(true);
      }
    };
    void refresh();
    const timer = setInterval(() => void refresh(), POLL_MS);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, []);

  return { models, defaultModel, error, loaded };
}
