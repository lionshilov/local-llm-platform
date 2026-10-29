#!/usr/bin/env bash
# Benchmark every engine in isolation: start it, measure it, stop it, then merge the reports.
# One engine at a time, so they never compete for unified memory or GPU time.
#
#   ENGINES="llamacpp mlx" inference/scripts/bench-all.sh [extra llm-bench run args]
set -euo pipefail
cd "$(dirname "$0")/../.."

read -r -a engines <<< "${ENGINES:-llamacpp ollama-gguf mlx ollama-mlx}"
out="benchmarks/results/$(date -u +%Y%m%d-%H%M%S)"
logs="$(mktemp -d)"
mkdir -p "$out"

# Engine name in configs/bench.yaml -> server script that hosts it.
server_of() {
  case "$1" in
    llamacpp) echo llamacpp ;;
    mlx) echo mlx ;;
    ollama | ollama-*) echo ollama ;;
    *) echo "unknown engine: $1" >&2; return 1 ;;
  esac
}

port_of() {
  case "$1" in
    llamacpp) echo 8080 ;;
    mlx) echo 8081 ;;
    ollama) echo 11434 ;;
  esac
}

is_up() { curl -sf "http://127.0.0.1:$1/v1/models" >/dev/null; }

server_pid=""
stop_server() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
    server_pid=""
  fi
}
trap stop_server EXIT

for engine in "${engines[@]}"; do
  server="$(server_of "$engine")"
  port="$(port_of "$server")"
  if is_up "$port"; then
    echo "==> $server already running on :$port, using it as-is"
  else
    echo "==> starting $server for $engine (log: $logs/$engine.log)"
    "inference/scripts/serve-$server.sh" >"$logs/$engine.log" 2>&1 &
    server_pid=$!
    for _ in $(seq 1 300); do
      is_up "$port" && break
      kill -0 "$server_pid" 2>/dev/null || break
      sleep 1
    done
    if ! is_up "$port"; then
      echo "!! $engine did not become ready; last log lines:" >&2
      tail -n 20 "$logs/$engine.log" >&2
      stop_server
      continue
    fi
  fi

  uv run llm-bench run --engine "$engine" --output-dir "$out" --tag "$engine" "$@" || true
  stop_server
done

shopt -s nullglob
results=("$out"/*.json)
if (( ${#results[@]} == 0 )); then
  echo "No results were produced." >&2
  exit 1
fi
uv run llm-bench report "${results[@]}" --format markdown --output "$out/README.md"
echo "==> combined report: $out/README.md"
