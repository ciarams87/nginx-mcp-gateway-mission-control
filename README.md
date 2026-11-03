# NGINX MCP Mission Control

A hands-on demonstration of **MCP security, tool-level access control, rate limiting, and observability using open-source NGINX**.

This project runs a real MCP SDK server that simulates Kubernetes and customer-record operations. It places NGINX in front of the MCP server to inspect JSON-RPC requests and enforce policies based on the MCP tool being called.

Mission Control provides a web interface for comparing direct MCP access against access through NGINX, editing the live NGINX configuration, and exploring gateway behavior.

> **Demo environment only.** The API keys are intentionally fictional and publicly documented. The stack uses HTTP and includes a live configuration editor. Do not expose this lab directly to the public internet.

## What this project demonstrates

- MCP tool discovery using `tools/list`
- MCP tool execution using `tools/call`
- Native NGINX JSON request-body inspection
- Role-based access control for individual MCP tools
- Per-tool rate limiting
- HTTP 401, 403, and 429 enforcement
- MCP response inspection using njs
- OpenTelemetry, Prometheus, and Grafana observability
- Live NGINX configuration validation and reload
- Additional illustrative MCP gateway architectures

## Architecture

```text
                    MCP Client / curl / Mission Control
                                   |
                    +--------------+--------------+
                    |                             |
                    v                             v
             DIRECT ACCESS                 THROUGH NGINX
             localhost:8001                localhost:8080
                    |                             |
                    |                      +------v------+
                    |                      |   NGINX     |
                    |                      |             |
                    |                      | JSON body   |
                    |                      | inspection  |
                    |                      |             |
                    |                      | Auth / RBAC |
                    |                      | Rate limits |
                    |                      | Telemetry   |
                    |                      +------+------+
                    |                             |
                    +--------------+--------------+
                                   |
                                   v
                           MCP SDK Server
                           Kubernetes Simulator
                           Container port 3001
```

**The distinction is important:**

| Endpoint | Destination | NGINX involved? | Gateway policies? |
|---|---|---|---|
| `http://localhost:8001/mcp` | MCP server directly | No | No |
| `http://localhost:8080/mcp` | NGINX → MCP server | Yes | Yes |
| `http://YOUR-VM-IP:3000` | Mission Control UI | UI selectable | Depends on selected mode |

The direct MCP port (`8001`) is bound to `127.0.0.1`, so the curl examples should be run on the Ubuntu VM.

The MCP server is a simulator, not a connection to a real Kubernetes cluster. Its in-memory data resets when the server restarts.

---

## Prerequisites

- Ubuntu or another Linux host
- Docker Engine
- Docker Compose v2
- Git
- curl
- Internet access to download container images and build dependencies

Verify your installation:

```bash
docker --version
docker compose version
git --version
curl --version
```

## Quick start

Clone the repository:

```bash
git clone https://github.com/YOUR-USERNAME/nginx-mcp-mission-control.git
cd nginx-mcp-mission-control
```

Create your local environment file:

```bash
cp .env.example .env
nano .env
```

Set your own `NGINX_EDITOR_TOKEN` password, at least five characters long.

Start the complete stack:

```bash
docker compose up -d --build
```

Check that everything is running:

```bash
docker compose ps
```

### Access the services

| Service | URL |
|---|---|
| Mission Control | `http://YOUR-VM-IP:3000` |
| NGINX MCP gateway | `http://YOUR-VM-IP:8080/mcp` |
| NGINX health check | `http://YOUR-VM-IP:8080/health` |
| Direct MCP server | `http://localhost:8001/mcp` |
| Grafana | `http://YOUR-VM-IP:3002` |
| Prometheus | `http://YOUR-VM-IP:9090` |

---

# Try it with curl

This is the recommended starting point for the demonstration.

We'll first interact with the MCP server **directly**, bypassing NGINX entirely.

Then we'll send similar requests **through NGINX** and see how authentication, authorization, and rate limiting change the behavior.

All commands below run from the Ubuntu VM.

## 1. Discover the tools directly — bypass NGINX

**Destination:** MCP server, port `8001`

**NGINX involved:** No

```bash
curl -sS -i http://localhost:8001/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

This sends a standard MCP `tools/list` request.

The server responds with a list of available tools, including their names, descriptions, and input schemas.

The simulator includes operations such as:

- `list_pods`
- `create_pod`
- `update_pod`
- `delete_pod`
- Customer-record tools

**What this demonstrates:** An MCP client can discover the capabilities exposed by a server programmatically.

**Important:** This request goes directly to the MCP server. NGINX does not inspect it, authenticate it, authorize it, rate-limit it, or collect gateway telemetry for it.

## 2. Call `list_pods` directly — bypass NGINX

**Destination:** MCP server, port `8001`

**NGINX involved:** No

```bash
curl -sS -i http://localhost:8001/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "list_pods",
      "arguments": {}
    }
  }'
```

Notice two important fields:

```json
{
  "method": "tools/call",
  "params": {
    "name": "list_pods"
  }
}
```

The URL is still `/mcp`.

The actual operation is identified inside the JSON request body.

**What this demonstrates:** Once a client discovers a tool, invoking it is a straightforward JSON-RPC request.

## 3. Attempt `delete_pod` directly — bypass NGINX

**Destination:** MCP server, port `8001`

**NGINX involved:** No

Use a deliberately nonexistent pod name to avoid modifying the demo data.

```bash
curl -sS -i http://localhost:8001/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "delete_pod",
      "arguments": {
        "name": "demo-nonexistent-pod"
      }
    }
  }'
```

Compare this with the previous request.

Only the tool name and arguments changed.

The MCP server may return a tool-level error because the pod doesn't exist. That is expected.

**What this demonstrates:** Read-only and destructive MCP operations can use the same HTTP endpoint and nearly identical JSON-RPC structures.

**Security implication:** When clients bypass NGINX, NGINX cannot enforce any of its gateway policies.

## 4. Discover tools through NGINX — no API key

**Destination:** NGINX gateway, port `8080`

**NGINX involved:** Yes

```bash
curl -sS -i http://localhost:8080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/list",
    "params": {}
  }'
```

**Expected result:** HTTP `401 Unauthorized`.

NGINX receives the request but doesn't find a valid API key.

The gateway rejects the request before forwarding it to the MCP server.

**What this demonstrates:** We can require authentication even for MCP tool discovery.

## 5. Discover tools through NGINX — valid Viewer key

**Destination:** NGINX gateway, port `8080`

**NGINX involved:** Yes

```bash
curl -sS -i http://localhost:8080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'X-API-Key: viewer-demo' \
  -d '{
    "jsonrpc": "2.0",
    "id": 5,
    "method": "tools/list",
    "params": {}
  }'
```

This time we supply a valid demo API key.

NGINX maps the key to the Viewer role and permits the discovery request.

**What this demonstrates:** Authentication can be enforced centrally without changing the MCP server.

Note that this demo's tool discovery response is not filtered by role. A Viewer may discover a tool that NGINX will subsequently prevent them from executing.

## 6. Call `list_pods` through NGINX — allowed

**Destination:** NGINX gateway, port `8080`

**NGINX involved:** Yes

```bash
curl -sS -i http://localhost:8080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'X-API-Key: viewer-demo' \
  -d '{
    "jsonrpc": "2.0",
    "id": 6,
    "method": "tools/call",
    "params": {
      "name": "list_pods",
      "arguments": {}
    }
  }'
```

The Viewer role is permitted to call `list_pods`.

NGINX:

1. Receives the HTTP request.
2. Reads the JSON body.
3. Extracts `tools/call` and `list_pods`.
4. Identifies the Viewer role.
5. Checks authorization.
6. Applies the `list_pods` rate limit.
7. Forwards the permitted request to the MCP server.

**Expected result:** The request passes the gateway and the MCP server returns the tool result, assuming the rate limit hasn't been exceeded.

## 7. Call `delete_pod` through NGINX — blocked

**Destination:** NGINX gateway, port `8080`

**NGINX involved:** Yes

```bash
curl -sS -i http://localhost:8080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'X-API-Key: viewer-demo' \
  -d '{
    "jsonrpc": "2.0",
    "id": 7,
    "method": "tools/call",
    "params": {
      "name": "delete_pod",
      "arguments": {
        "name": "demo-nonexistent-pod"
      }
    }
  }'
```

**Expected result:**

```text
HTTP/1.1 403 Forbidden
```

NGINX identifies:

```text
Role:    viewer
Method:  tools/call
Tool:    delete_pod
```

That combination matches the RBAC deny rule.

The request is rejected by NGINX.

**The MCP server does not execute the delete operation.**

This is one of the most important demonstrations in the project.

## 8. Repeat with an Operator — still blocked

**Destination:** NGINX gateway, port `8080`

**NGINX involved:** Yes

```bash
curl -sS -i http://localhost:8080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'X-API-Key: operator-demo' \
  -d '{
    "jsonrpc": "2.0",
    "id": 8,
    "method": "tools/call",
    "params": {
      "name": "delete_pod",
      "arguments": {
        "name": "demo-nonexistent-pod"
      }
    }
  }'
```

**Expected result:** HTTP `403 Forbidden`.

The Operator role has more permissions than Viewer, but it is still not allowed to delete pods.

**What this demonstrates:** Access policies can distinguish between different levels of privilege.

## 9. Repeat with an Admin — allowed through NGINX

**Destination:** NGINX gateway, port `8080`

**NGINX involved:** Yes

```bash
curl -sS -i http://localhost:8080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'X-API-Key: admin-demo' \
  -d '{
    "jsonrpc": "2.0",
    "id": 9,
    "method": "tools/call",
    "params": {
      "name": "delete_pod",
      "arguments": {
        "name": "demo-nonexistent-pod"
      }
    }
  }'
```

The Admin role is permitted to call `delete_pod`.

NGINX applies the delete-tool rate limit and forwards the request if it is within the allowance.

The MCP server may return a not-found tool error because the pod doesn't exist.

That is different from an NGINX authorization failure.

**What this demonstrates:** NGINX decides whether the operation is permitted; the MCP server determines the outcome of the operation itself.

## 10. Compare direct access and NGINX access

| Test | Direct MCP `:8001` | Through NGINX `:8080` |
|---|---|---|
| Discover tools without a key | Allowed by the demo MCP server | 401 |
| Viewer calls `list_pods` | No gateway role check | Allowed |
| Viewer calls `delete_pod` | No gateway role check | 403 |
| Operator calls `delete_pod` | No gateway role check | 403 |
| Admin calls `delete_pod` | No gateway role check | Allowed subject to rate limit |
| Tool-specific rate limiting | Not applied by NGINX | Applied |
| NGINX gateway telemetry | Not collected | Collected |

The MCP server itself is unchanged in both cases.

**Note on MCP sessions:** This demo uses a stateless Streamable HTTP MCP transport, so these standalone curl requests are intended to work. Other MCP servers may require an `initialize` handshake and session headers.

---

# Explore Mission Control

Open:

```text
http://YOUR-VM-IP:3000
```

## Direct to MCP mode

Select **Direct to MCP**.

In this mode, Mission Control communicates directly with the MCP server.

NGINX is bypassed.

Use this mode to demonstrate tool discovery and execution without gateway enforcement.

## Through NGINX mode

Select **Through NGINX**.

Enter one of the demo API keys:

| Key | Role |
|---|---|
| `viewer-demo` | Viewer |
| `operator-demo` | Operator |
| `admin-demo` | Admin |

In this mode, requests travel through NGINX before reaching the MCP server.

Use this mode to demonstrate:

- Authentication failures
- Tool-level RBAC
- Authorized tool execution
- Rate limiting
- Gateway telemetry

---

# How NGINX processes an MCP request

Open the **NGINX Config** tab in Mission Control.

The main configuration file is:

```text
nginx/nginx.conf
```

## Step 1 — Receive the HTTP request

NGINX listens on port `8080`.

All MCP operations arrive at the same `/mcp` endpoint.

The URL alone doesn't identify which tool is being called.

## Step 2 — Read the JSON body early

NGINX uses:

```nginx
client_body_early_read
```

This makes the request body available early enough for policy and location-selection decisions.

## Step 3 — Extract JSON-RPC fields

NGINX uses native JSON extraction:

```nginx
json_set $mcp_body_method $request_body method;
json_set $mcp_body_tool   $request_body params.name;
```

For a delete request:

```text
$mcp_body_method = tools/call
$mcp_body_tool   = delete_pod
```

## Step 4 — Identify the caller

The fictional API keys are configured in:

```text
nginx/conf.d/demo-api-keys.conf
```

NGINX maps the supplied API key to a role.

## Step 5 — Enforce role-based access control

NGINX combines:

```text
Caller role + JSON-RPC method + MCP tool name
```

For example:

```text
viewer + tools/call + delete_pod
```

This combination is denied.

NGINX returns:

- `401` for missing or invalid credentials
- `403` for forbidden tool calls

Denied requests are not forwarded to the MCP server.

## Step 6 — Apply tool-specific rate limits

The demo configures:

| Tool | Rate | Burst |
|---|---|---|
| `list_pods` | 10 requests/sec | 5 |
| `create_pod` | 3 requests/sec | 2 |
| `delete_pod` | 1 request/sec | 1 |

Each configured tool category uses a separate rate-limit zone keyed by client IP address.

NGINX rejects excessive requests with HTTP `429 Too Many Requests`.

## Step 7 — Proxy allowed requests

Approved requests are forwarded to the MCP server:

```text
NGINX → mcp:3001
```

The shared proxy configuration also handles relevant MCP HTTP behavior, including response streaming.

## Step 8 — Observe the response

NGINX uses njs to inspect MCP response content.

This is important because an MCP tool can report a failure using:

```json
{
  "isError": true
}
```

even when the HTTP response status is `200 OK`.

OpenTelemetry, Prometheus, and Grafana provide visibility into gateway traffic and outcomes.

---

# Demonstrate rate limiting

The easiest approach is to use Mission Control.

1. Open **Mission Control**.
2. Select **Through NGINX**.
3. Enter a valid API key.
4. Click **Burst: 25 HTTP requests**.
5. Observe the allowed and rejected requests.

The burst test sends 25 HTTP requests to the read-only `list_pods` tool.

With the default configuration:

```nginx
limit_req zone=pod_read burst=5 nodelay;
```

NGINX may admit approximately six requests from an idle bucket and reject the remaining requests with HTTP `429`.

The exact results depend on timing and recent traffic.

## Change the policy live

Open **NGINX Config**.

Find:

```nginx
limit_req zone=pod_read burst=5 nodelay;
```

Change it to:

```nginx
limit_req zone=pod_read burst=10 nodelay;
```

Enter the editor password and click **Validate & Apply**.

The configuration editor:

1. Submits the updated configuration.
2. Writes the candidate into the NGINX container's bind-mounted configuration file.
3. Runs `nginx -t`.
4. Requests an NGINX reload if validation succeeds.
5. Restores the previous configuration if validation fails.

Run the 25-request burst again.

The larger burst allowance should permit more requests through the gateway when the rate-limit bucket is idle.

**The MCP server itself has not changed.**

The configuration editor modifies the host's `nginx/nginx.conf`, so review `git diff` after experimenting.

---

# Observability with Grafana

Open:

```text
http://YOUR-VM-IP:3002
```

The stack includes:

- NGINX OpenTelemetry instrumentation
- njs MCP response inspection
- OpenTelemetry Collector
- Prometheus
- Grafana dashboards

Use the dashboard to explore HTTP request outcomes, policy rejections, rate limiting, and MCP-specific error signals.

**Important distinction:** HTTP success and MCP tool success are not always the same thing.

---

# Repository structure

```text
nginx-mcp-mission-control/
├── compose.yaml
├── .env.example
├── .gitignore
├── README.md
├── nginx/
│   ├── nginx.conf
│   ├── conf.d/
│   ├── snippets/
│   ├── editor-supervisor.sh
│   └── control/
├── mcp-server/
│   ├── Dockerfile
│   ├── package.json
│   └── server.mjs
├── ui/
│   ├── Dockerfile
│   ├── package.json
│   ├── server.mjs
│   └── public/
├── njs/
├── otel/
├── grafana/
└── scripts/
```

## Useful Docker commands

Start everything:

```bash
docker compose up -d --build
```

Check service status:

```bash
docker compose ps
```

View NGINX logs:

```bash
docker compose logs -f nginx
```

View Mission Control logs:

```bash
docker compose logs -f ui
```

Validate the running NGINX configuration:

```bash
docker compose exec nginx nginx -t
```

Rebuild only the UI:

```bash
docker compose build --no-cache ui
docker compose up -d --force-recreate ui
```

Stop the stack:

```bash
docker compose down
```

## Troubleshooting

### Mission Control doesn't load

Check:

```bash
docker compose ps
docker compose logs --tail=100 ui
```

### NGINX doesn't start

Validate the configuration:

```bash
docker compose exec nginx nginx -t
```

If the container isn't running, inspect:

```bash
docker compose logs --tail=100 nginx
```

### curl returns 401

You're sending a request through NGINX without a valid demo API key.

Add:

```bash
-H 'X-API-Key: viewer-demo'
```

Direct requests to port `8001` don't require the NGINX demo API key.

### curl returns 403

NGINX has identified an authenticated caller attempting an operation forbidden by the configured RBAC policy.

Try an authorized read-only tool or use an appropriate demo role.

### curl returns 429

You've exceeded the applicable NGINX rate limit.

Wait briefly and retry, or inspect the configured tool-specific rate limit.

### curl returns an MCP tool error with HTTP 200

This can be normal MCP behavior.

Inspect the JSON-RPC response body, including any `isError` field.

A tool-level error does not necessarily indicate an NGINX failure.

### Changes to NGINX don't appear

Check the configuration editor's validation output and verify the running configuration.

The NGINX configuration is bind-mounted from the project directory.

### UI changes don't appear

Rebuild the UI and hard-refresh the browser:

```bash
docker compose build --no-cache ui
docker compose up -d --force-recreate ui
```

---

# Security and limitations

This project is intended for education and demonstrations.

- Demo API keys are intentionally public and must not be used in production.
- The live configuration editor is intended only for trusted environments.
- The stack uses HTTP and is not hardened for internet exposure.
- The MCP server simulates Kubernetes operations; it does not modify a real cluster.
- Rate limits are based on client IP address, not authenticated agent identity.
- The configured tool-specific rate limits apply to the selected tools; other tools use the default proxy path.
- The **Further Architectures** tab contains illustrative configurations that are not active in the deployed gateway.
- The demo does not implement a complete production identity, authorization, or circuit-breaker system.

## Licensing

See `UPSTREAM-LICENSE` for the included upstream license notice. Review the licensing and ownership of the project as a whole before adding a top-level project license.

---

**NGINX MCP Mission Control demonstrates how open-source NGINX can provide a centralized security, traffic-management, and observability layer for MCP tools — without requiring changes to the MCP server itself.**
