# NGINX MCP Mission Control

A **demonstration lab** for securing and observing Model Context Protocol (MCP) traffic with **open-source NGINX**. A real MCP SDK server simulates Kubernetes pod and customer-record operations; a web dashboard compares direct access with requests routed through an NGINX gateway.

> **Demo only.** The API keys in this repository are intentionally public and fictional. The stack uses HTTP, exposes administrative/demo services, and has an in-browser NGINX configuration editor. **Do not expose this lab directly to the public internet or use these controls as production authentication.**

## What the demo shows

- **MCP tool discovery and invocation** using JSON-RPC (`tools/list`, `tools/call`).
- **Early JSON request-body inspection** using `client_body_early_read` and `json_set`.
- **Tool-level role-based access control** (Viewer, Operator, Admin) with NGINX maps and predicate locations.
- **Separate per-client-IP rate limits** for `list_pods` (10 req/s, burst 5), `create_pod` (3 req/s, burst 2), and `delete_pod` (1 req/s, burst 1).
- **HTTP and MCP-level observability** using NGINX OpenTelemetry, njs, Prometheus, and Grafana.
- **Live NGINX configuration editing** in Mission Control with validation, reload, and rollback on validation failure.
- A **Further Architectures** tab with *illustrative* configurations; those patterns are not active in this stack.

## Architecture

```text
                          +--------------------+
                          | Mission Control UI |  :3000
                          +---------+----------+
                                    |
                     +--------------+--------------+
                     |                             |
             Direct to MCP                 Through NGINX
                     |                             |
                     |                    +--------v---------+
                     |                    | NGINX gateway    | :8080
                     |                    | JSON / RBAC /    |
                     |                    | rate limits      |
                     |                    +--------+---------+
                     |                             |
                     +-------------+---------------+
                                   |
                          +--------v---------+
                          | MCP SDK simulator| :8001 (localhost only)
                          | container :3001  |
                          +------------------+

              NGINX / njs -> OpenTelemetry Collector -> Prometheus -> Grafana (:3002)
```

The MCP server is **a simulator**, not a connection to a real Kubernetes cluster. Its data lives in memory and resets on restart.

## Prerequisites

- Ubuntu/Linux host with Docker Engine and the Docker Compose v2 plugin (`docker compose version`).
- Internet access to pull the pinned container images and install Node dependencies when building.
- Available ports: 3000 (UI), 8080 (gateway), 3002 (Grafana), 9090 (Prometheus), 4317 (OTLP). Direct MCP is bound to **127.0.0.1:8001** on the Docker host.

## Quick start

```bash
# From the project directory
cp .env.example .env
nano .env                     # set a unique editor password, at least 5 characters
docker compose up -d --build
docker compose ps
```

Open:

| Service | URL |
|---|---|
| Mission Control | `http://YOUR-VM-IP:3000` |
| NGINX gateway health | `http://YOUR-VM-IP:8080/health` |
| Grafana | `http://YOUR-VM-IP:3002` |
| Prometheus | `http://YOUR-VM-IP:9090` |
| Direct MCP (from VM only) | `http://localhost:8001/mcp` |

## Demo credentials (fictional, intentionally public)

| API key | Role | `list_pods` | `create_pod` | `delete_pod` |
|---|---|---|---|---|
| `viewer-demo` | Viewer | Allowed | Denied (403) | Denied (403) |
| `operator-demo` | Operator | Allowed | Allowed | Denied (403) |
| `admin-demo` | Admin | Allowed | Allowed | Allowed |
| Missing / invalid | Anonymous | Denied (401) | Denied (401) | Denied (401) |

Keys are defined in `nginx/conf.d/demo-api-keys.conf`. These are **not secrets** and must never be reused outside the demo.

## Try it with curl

### Discover MCP tools directly (bypass NGINX)

```bash
curl -sS -i http://localhost:8001/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Call a read-only tool directly

```bash
curl -sS -i http://localhost:8001/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_pods","arguments":{}}}'
```

### Show RBAC: Viewer attempting to delete a nonexistent pod

```bash
curl -sS -i http://localhost:8080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'X-API-Key: viewer-demo' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"delete_pod","arguments":{"name":"demo-nonexistent-pod"}}}'
```

Expected: **HTTP 403 Forbidden**, rejected by NGINX before the MCP tool runs.

The demo MCP server uses a stateless Streamable HTTP transport, but some other MCP implementations require an `initialize` handshake and session header before `tools/list` or `tools/call`.

## Walk through the NGINX configuration

The main file is `nginx/nginx.conf`:

1. Check JSON content type and use **`client_body_early_read`** so the request body is available for policy routing.
2. Use **`json_set`** to extract the JSON-RPC `method` and `params.name` (tool name).
3. Map the fictional **`X-API-Key`** to an agent role; evaluate role + method + tool with **`map`**.
4. Reject unauthenticated requests with **401** and forbidden tools with **403** using predicate locations.
5. Select tool-specific **`limit_req`** locations; excess traffic receives **429**.
6. Proxy allowed traffic to the MCP backend via shared proxy settings.
7. Observe JSON-RPC responses with **njs** (including `isError: true` in HTTP 200) and export telemetry via **OpenTelemetry**.

NGINX `map` declarations are evaluated when their variables are used, rather than acting as an imperative top-to-bottom program.

## Live configuration editor

1. Open **Mission Control → NGINX Config**.
2. Change a safe setting, for example `limit_req zone=pod_read burst=5 nodelay;` to `burst=10`.
3. Enter the editor password configured in `.env` and click **Validate & Apply**.
4. The supervisor writes the candidate to the bind-mounted `nginx.conf`, runs `nginx -t`, and requests a reload on success. Invalid configurations are restored from the previous snapshot.
5. Return to Mission Control and rerun the **Burst: 25 HTTP requests** test.

The burst test issues 25 read-only `list_pods` HTTP POSTs; the admitted/rejected counts can vary with timing and existing rate-limit state. A green validation message indicates validation and a reload request, not a full end-to-end verification of all traffic.

## Common Docker commands

```bash
docker compose ps
docker compose logs -f nginx
docker compose logs -f ui
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload
docker compose up -d --build
docker compose down
```

For a UI-only code change:

```bash
docker compose build --no-cache ui
docker compose up -d --force-recreate ui
```

## Repository layout

```text
compose.yaml                 Docker Compose stack
nginx/nginx.conf            NGINX gateway configuration
nginx/conf.d/              Demo API keys and observability includes
nginx/snippets/            Shared NGINX proxy, njs, and OTel includes
nginx/editor-supervisor.sh  Validate/reload/rollback supervisor
nginx/control/              Runtime editor state (ignored by Git)
mcp-server/                 MCP SDK simulator
ui/                         Mission Control web app
grafana/                    Dashboard and provisioning
otel/                       Collector and Prometheus configuration
njs/                        MCP response observer
scripts/                    Demo helper script
```

## Limitations and security notes

- **Demo only:** public fake API keys, HTTP-only access, anonymous Grafana, and a configuration editor make this unsuitable for internet exposure.
- The MCP server simulates Kubernetes; no real cluster is modified.
- Per-tool rate limiting is **per client IP** for the configured tools, not a per-agent or globally shared quota. Other tools use the default proxy path.
- Illustrative configurations in **Further Architectures** are not deployed.
- A tool may return an MCP error (`isError: true`) with HTTP 200. Do not equate HTTP 2xx with tool success.
- This project has not been verified by running Docker in the environment used to package this repository. Test it on your own VM before sharing it.

## Licensing

`UPSTREAM-LICENSE` contains the upstream Apache 2.0 license notice included with this demo. Review ownership and licensing of the project as a whole before adding a top-level `LICENSE` file or presenting it as your own original work.
