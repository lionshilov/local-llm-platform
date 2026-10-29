# 0002. Inference runs natively on the host; everything else may run in containers

## Context

On macOS, Docker containers run inside a Linux VM with no access to the Apple GPU
(Metal). An LLM in a container on a Mac runs on the CPU, several times slower. Production
deployments, meanwhile, usually separate model servers (on GPU nodes, with their own
lifecycle and scaling) from stateless application services.

## Decision

Inference servers (llama.cpp, MLX-LM, Ollama) run as native processes started by scripts
in `inference/scripts/`. The gateway, Prometheus and Grafana run either natively or in
Docker Compose and reach the engines over HTTP (`host.docker.internal` from containers).

## Consequences

- Full GPU speed on Apple Silicon, and the same topology as a GPU cluster: swap the host
  engines for vLLM on GPU nodes and nothing above them changes.
- Engines are not managed by Compose; `make serve-*` and `bench-all.sh` handle their
  lifecycle. On Linux with NVIDIA GPUs, engines could join the Compose file with GPU
  reservations instead.
- CI runs the end-to-end test on a CPU llama.cpp container, which is slow but proves the
  whole path without special hardware.
