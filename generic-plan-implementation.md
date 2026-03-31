# Generic Implementation Plan: Background Task Architecture with Real-Time Status Hub

## Instructions for the Implementing Agent

**Before implementing any phase**, you MUST:

1. Search the entire codebase for existing implementations of the concepts described in that phase — Redis connections, background task patterns, streaming endpoints, auth dependencies, middleware, permission checks, configuration management, frontend state management, API helpers, and component patterns.
2. Read every file you find. Understand the naming conventions, folder structure, import patterns, state management approach, styling conventions, and architectural patterns already in use.
3. Identify what already exists that can be reused or extended — do NOT create new files or abstractions when the codebase already has equivalent functionality.
4. Only then design the implementation to fit the patterns you found.

**Do NOT copy code from this plan or from any reference project.** This plan describes concepts, architecture, and behavioral requirements. The implementation must be derived from the target codebase's existing patterns, naming conventions, and file structure.

**When this plan says "find X in the codebase"**, it means: search for it, read it, understand how it works, and build on top of it. If it doesn't exist, create it following the conventions established by similar modules in the codebase.

---

## What This Plan Adds to an Existing Application

This plan assumes an existing application with:

- A **Python/FastAPI backend** with JWT-based authentication, permission checking, and protected API endpoints
- A **Next.js frontend** (App Router) with an auth context, route-protecting middleware, a navigation sidebar, and protected pages
- An **RBAC permission system** where the backend resolves user permissions from identity group memberships and enforces them on every endpoint
- A **two-gate security model**: Gate 1 (frontend middleware, UX boundary, base64-decodes JWT, does NOT verify signature) and Gate 2 (backend dependency, cryptographically verifies JWT, re-derives permissions from groups)
- Protected pages that currently **fetch and display data instantly** from backend endpoints

This plan replaces the instant-response pattern with a **background task architecture** where:

1. Protected pages become **submission forms** instead of data displays
2. Submissions create **background tasks** that run asynchronously and write results to **user-owned files** on the server
3. A new **hub page** shows all of a user's submitted requests with **live status updates via Server-Sent Events** and download links
4. **Redis** stores task records (surviving restarts, shared across workers) and provides **Pub/Sub** for cross-worker real-time notification
5. A **frontend proxy route** bridges the SSE stream between the backend and the browser, forwarding the httpOnly cookie as an Authorization header so the token is never exposed
6. Result files are scoped by user identity so no user can access another user's output

---

## Architecture: How the Pieces Connect

```
User submits request from a protected page
       │
       ▼
Backend Submit Endpoint (any worker)
  ├─ Verify JWT + check permission for the request type
  ├─ Create task record in Redis hash
  ├─ Add task ID to user's Redis set (index)
  ├─ Publish "task_created" to user's Redis Pub/Sub channel
  ├─ Schedule a BackgroundTask to run the work
  └─ Return 202 Accepted immediately
       │
       ▼  (runs after response is sent)
BackgroundTask executes (sync, in thread pool)
  ├─ Update Redis hash: status → "running" + publish notification
  ├─ Simulate or perform work
  ├─ Write result to: output/{user_id}/{task_id}.json
  ├─ Update Redis hash: status → "completed" + publish notification
  └─ On error: status → "failed" + error message + publish
       │
       ▼  (meanwhile, possibly on a different worker)
Backend SSE Endpoint (any worker)
  ├─ Authenticated via Authorization header (forwarded by frontend proxy)
  ├─ Subscribes to user's Redis Pub/Sub channel
  ├─ On notification: reads all tasks from Redis → yields as SSE event
  ├─ Sends keepalive comments every ~30s to prevent timeout
  └─ Cleans up Pub/Sub subscription on disconnect
       │
       ▼
Frontend Proxy Route (same-origin API route)
  ├─ Reads httpOnly cookie containing the auth token
  ├─ Opens fetch to backend SSE endpoint with Authorization header
  ├─ Pipes the streaming response body through to the browser
  └─ Token never exposed in URL or to client JavaScript
       │
       ▼
Frontend EventSource Hook
  ├─ Connects to the proxy route (same origin, cookie sent automatically)
  ├─ Parses SSE events into task state array
  └─ Components re-render on every update
       │
       ▼
Hub Page displays live task table
  ├─ Status badges update in real time
  └─ Download button appears when task completes
       │
       ▼
Backend Download Endpoint
  ├─ Verify JWT + verify task ownership via Redis + re-check permission
  └─ Serve file from user's output directory
```

### Why Redis (not in-memory state)

In production, multiple backend workers (e.g., gunicorn) handle requests. A request may be submitted on Worker A but the SSE stream may be served by Worker B. In-memory state (dicts, asyncio.Event) cannot communicate across workers. Redis solves this:

- **Hash per task**: shared state accessible from any worker
- **Set per user**: efficient lookup of all tasks for a user
- **Pub/Sub per user channel**: Worker A publishes, Worker B's subscription receives — cross-worker notification with zero polling

### Why SSE (not WebSocket or Polling)

- **SSE**: ~0ms latency (server push), built-in EventSource auto-reconnect, standard HTTP (no sticky sessions), minimal backend code
- **WebSocket**: ~0ms but requires manual reconnect logic, sticky sessions for load balancers, ConnectionManager class
- **Polling**: 2-15s latency, hundreds of req/s wasted at scale, simplest but wasteful

SSE is the right choice for unidirectional real-time updates (server → client). The browser's EventSource API handles reconnection with exponential backoff automatically.

---

## Redis Data Model

### Task record (one Redis hash per task)

Key pattern: `task:{task_id}`

| Field | Type | Description |
|---|---|---|
| id | string (UUID) | Unique task identifier |
| user_id | string | Authenticated user's stable identity (from JWT) |
| request_type | string | Which type of request was submitted |
| status | string | One of: `pending`, `running`, `completed`, `failed` |
| created_at | ISO 8601 string | When the task was created |
| updated_at | ISO 8601 string | Last status change timestamp |
| file_path | string (or empty) | Server-side path to result file (empty until completed) |
| error | string (or empty) | Error message (empty unless failed) |
| parameters | JSON string | Serialized dict of submission parameters |

### User task index (one Redis set per user)

Key pattern: `user_tasks:{user_id}`
Members: task ID strings

This set enables efficient lookup of all tasks for a user without scanning all Redis keys. When listing tasks: read the set members, then pipeline HGETALL for each task hash in a single round trip.

### Pub/Sub channel (one channel per user)

Channel pattern: `user:{user_id}:task_updates`
Message: JSON signal with event type and task ID

The SSE endpoint subscribes to this channel. When a message arrives, it reads the **full task list from Redis** and pushes it to the client. The Pub/Sub message is just a notification signal — the Redis hashes are always the source of truth.

---

## Security Model

| Check | Where | What it prevents |
|---|---|---|
| JWT signature verification | Backend auth dependency | Forged/tampered tokens |
| Permission check on submit | Submit endpoint | Users submitting request types they lack access to |
| Permission re-check on download | Download endpoint | Downloading results after permission was revoked |
| Ownership check via Redis | Task service (get_task compares user_id) | Cross-user task access |
| File path constructed from verified identity | Download endpoint builds path from JWT, never user input | Path traversal attacks |
| SSE auth via httpOnly cookie | Frontend proxy reads cookie, forwards as Bearer header | Token never in URL, never in client JS |
| Redis key isolation | User task set keyed by user_id | Users can only query their own task index |

---

## Phase 1: Redis Infrastructure + Configuration

> **Before starting**: Search the backend for any existing Redis usage, connection management, configuration modules, app startup/shutdown lifecycle hooks, and dependency management files.

### Goal

Establish the Redis connection infrastructure and configuration that all subsequent phases depend on. After this phase, the app connects to Redis on startup, creates an output directory for result files, and shuts down cleanly.

### What to build

1. **Add the Redis client library** to the project's dependency file. Use the async-capable Redis library for Python with the optional C protocol parser for better performance.

2. **Add configuration settings** to the existing backend config module (find the settings class that reads from environment variables):
   - A Redis connection URL setting with a sensible local default
   - An output directory path setting — this is where result files will be written, organized by user identity subdirectories

3. **Create a Redis client module** that provides two types of connections:
   - An **async client** for use in FastAPI async endpoints (task CRUD, SSE streaming, Pub/Sub subscriptions). This client uses a connection pool initialized once at startup.
   - A **sync client** for use in background task runners. Background tasks that perform blocking operations (like simulated work with sleep) run in a thread pool where async clients won't work — there's no event loop in the thread. The sync client solves this cleanly.
   - Provide functions to initialize, retrieve, and close the async client. Provide a function to create sync clients on demand.

4. **Add app lifecycle management**: Find the FastAPI app initialization (look for the lifespan pattern or startup/shutdown events). On startup:
   - Initialize the async Redis connection pool
   - Ping Redis to verify connectivity — if this fails, the app should not start
   - Create the output directory if it doesn't exist
   - On shutdown: close the Redis connection pool cleanly

5. **Exclude the output directory from version control** by adding it to the appropriate gitignore file.

### Critical details

- **Why two Redis clients**: FastAPI async endpoints use the async Redis library which is non-blocking and works with the event loop. Background tasks that use blocking operations run in a thread pool where the async library cannot function (no event loop in the thread). A separate sync client solves this cleanly.
- **decode_responses=True**: Both clients should decode Redis responses as strings (not bytes). This avoids manual `.decode()` calls throughout the codebase.
- **Connection URL format**: `redis://[:password@]host:port/db` — the standard Redis URI scheme. Default to localhost, no password, database 0.

### Verify

- Start the app — no Redis connection errors in logs
- Output directory is created automatically
- Redis responds to ping
- Clean shutdown with no warnings

---

## Phase 2: Task Data Models + Task Service

> **Before starting**: Search the backend for existing Pydantic model patterns, service class patterns, and how dependencies are injected into endpoints. Read the existing auth models for naming and style conventions.

### Goal

Build the data models that define task records and the service class that manages all Redis operations — creating tasks, updating status, listing tasks per user, ownership verification, and Pub/Sub subscriptions for the SSE stream.

### What to build

#### Data models

1. **Task status type**: A string enum with four values: `pending`, `running`, `completed`, `failed`. Use the same enum pattern established in the codebase.

2. **Task creation model** (request body): Contains the request type string and an optional parameters dict. Add validation that the request type is one of a known set of valid types — these correspond to the protected pages that will be converted to submission forms.

3. **Internal task record model**: The full task record stored in Redis. Fields: id (UUID string), user identity string, request type, status, created_at (ISO timestamp), updated_at (ISO timestamp), file_path (empty until completed), error message (empty unless failed), parameters dict.

4. **API response model**: The view returned to the frontend. Same as the internal record but **excludes** the server file path (the frontend downloads via a task ID, not a file path) and excludes the user identity (the frontend already knows who the user is). This prevents leaking internal server paths to the client.

#### Task service class

A single class that all Redis operations go through. It takes the async Redis client in its constructor.

5. **Create task**: Generate a UUID, build the record with "pending" status, store it as a Redis hash (`HSET`), add the task ID to the user's Redis set (`SADD`), publish a creation notification to the user's Pub/Sub channel (`PUBLISH`). **Important**: The parameters field is a dict but Redis hash values must be strings — serialize it to JSON before storing.

6. **Update status**: Update specific fields on the task hash (always: status and updated_at timestamp, plus optional kwargs like file_path or error). Read the user identity from the existing hash to determine which Pub/Sub channel to publish to. Publish the notification.

7. **List user tasks**: Read all task IDs from the user's Redis set (`SMEMBERS`). Use a **Redis pipeline** to fetch all task hashes in a single network round trip (without a pipeline, listing 20 tasks would require 20 separate calls). Deserialize the parameters field from JSON. Return sorted by creation time, newest first.

8. **Get single task with ownership check**: Fetch the task hash. If it doesn't exist OR the user identity doesn't match, return None. **Do not distinguish** between "doesn't exist" and "belongs to another user" — this prevents information leakage.

9. **Subscribe to user channel**: Create a **new** Pub/Sub instance per call and subscribe to the user's channel. Return the Pub/Sub object for the caller to iterate over. **Critical**: Each SSE connection must get its own Pub/Sub instance. Pub/Sub objects are not shareable across concurrent connections — if two streams share one, messages are consumed by one and lost to the other.

#### Service lifecycle

10. **Make the service a singleton**: Instantiate it once during app startup (after Redis is initialized) and make it available to endpoints via the framework's dependency injection. Store it on the app's state object or use a module-level singleton pattern — follow whatever pattern the codebase already uses for shared services.

#### Sync operations for background runners

11. **Provide a way for sync background tasks to update status**: The background runners (Phase 3) are sync functions in a thread pool — they cannot call async methods. Create either standalone sync helper functions that use the sync Redis client directly, or a lightweight sync wrapper class. The operations needed are: HSET (update fields), HGET (read user_id for Pub/Sub channel), PUBLISH (send notification). Keep it simple — three lines of Redis code, no need for a full abstraction.

### Critical details

- **Redis pipeline**: Batches multiple commands into one network round trip. Essential for the list operation — without it, performance degrades linearly with task count.
- **JSON serialization of parameters**: Redis hash values are strings. The parameters dict must be `json.dumps()`'d before HSET and `json.loads()`'d after HGETALL.
- **Pub/Sub is a signal, not the source of truth**: When a notification arrives, the SSE endpoint reads the full task list fresh from Redis. The notification just says "something changed" — the hashes are always authoritative.

### Verify

- Create a task via the service — confirm it appears in Redis (HGETALL)
- Confirm it appears in the user's task set (SMEMBERS)
- Update status — confirm the hash changes
- List tasks — confirm pipeline retrieval works
- Ownership check — confirm a different user_id returns None
- Pub/Sub — confirm a subscriber receives notifications when status changes

---

## Phase 3: Background Task Runners

> **Before starting**: Search the backend for any existing background task patterns, worker functions, or job processing. Read how the existing protected page endpoints generate their response data — the runners will produce the same data shapes as output files.

### Goal

Create sync background task functions that simulate work, write result files to the user's output directory, and update task status in Redis (triggering Pub/Sub notifications to SSE streams).

### What to build

1. **One runner function per request type**: Each corresponds to a protected page that will be converted from instant data to background processing. The runner simulates the work that would produce that page's data.

2. **Common runner signature**: Every runner receives: the task ID, the user's identity string, and the submitted parameters dict.

3. **Common runner flow**:
   - Create a sync Redis connection
   - Update status to "running" (this triggers a Pub/Sub notification → SSE streams see the status change)
   - Simulate work with a blocking sleep (vary the duration per type to make the demo visually interesting — e.g., 3-10 seconds)
   - Generate mock result data as a dict (matching the shape that the old instant endpoint returned)
   - Create the user's output subdirectory if it doesn't exist
   - Write the result dict as a JSON file: `{output_dir}/{user_id}/{task_id}.json`
   - Update status to "completed" with the file path
   - Close the Redis connection

4. **Error handling**: Wrap the entire runner body in try/except. On any exception: update status to "failed" with the error message, close Redis in a finally block. Do NOT re-raise — the framework's background task system swallows exceptions silently, so log the error explicitly.

5. **Runner dispatch map**: Create a dict mapping request type strings to their runner functions. The submit endpoint (Phase 4) uses this map to look up the correct runner.

### Critical details — sync constraint

Background tasks that use blocking sleep **must** be regular sync functions (not async). The framework automatically runs sync background tasks in a thread pool, which prevents the sleep from blocking the event loop. Since they run in a thread (not the async event loop), they **cannot** use `await` or async Redis. They must use the sync Redis client for all status updates and Pub/Sub publishing.

If the runners were async functions that called blocking sleep, they would block the entire event loop and freeze all other request handling. This is a subtle but critical correctness requirement.

### Verify

- Call a runner manually with a test task ID and user identity
- Confirm the result file exists on disk with valid JSON
- Confirm Redis hash status is "completed" with the file path set
- Confirm a Pub/Sub subscriber received both the "running" and "completed" notifications
- Test error handling by deliberately causing an error — status should be "failed" with the error message

---

## Phase 4: Backend Request Endpoints

> **Before starting**: Search the backend for existing router patterns, how endpoints are organized, how auth dependencies are injected, and how the framework's background task system is used. Read the existing protected page endpoints to understand how permissions are checked.

### Goal

Build the backend router with four endpoints: submit a request, list user tasks, stream live updates via SSE, and download completed result files.

### What to build

#### Endpoint 1: Submit (POST)

Accepts a request submission, creates a task record, starts a background task, returns 202 Accepted immediately.

- **Auth**: Standard JWT auth dependency
- **Validate**: The request type must exist in the runner dispatch map — return 400 if unknown
- **Permission check**: The user must have the permission corresponding to the request type (e.g., if the request type maps to a page, require that page's permission). **This check must happen inside the handler, not as a static dependency**, because the required permission is dynamic — it depends on the request body, which isn't known until the handler runs.
- **Create**: Use the task service to create the record in Redis (this also publishes the Pub/Sub notification)
- **Queue**: Add the appropriate runner from the dispatch map as a background task
- **Return**: 202 Accepted with the task response (API-facing model, no internal fields)

#### Endpoint 2: List (GET)

Returns all tasks belonging to the authenticated user. Used for initial page load and as a fallback if SSE disconnects.

- **Auth**: Standard JWT auth dependency
- **Return**: The task service's list method, converted to API response models

#### Endpoint 3: SSE Stream (GET)

Server-Sent Events stream that pushes task list updates to the client in real time. This is the most complex endpoint.

- **Auth**: Standard JWT auth dependency (Authorization header forwarded by the frontend proxy)
- **Generator**:
  1. Yield the current task list immediately as the first SSE event (initial state on connect)
  2. Subscribe to the user's Pub/Sub channel (one subscription per SSE connection)
  3. Enter a loop:
     - Wait for a Pub/Sub message with a ~30 second timeout
     - **On message**: Read the full task list from Redis and yield it as an SSE event
     - **On timeout**: Yield a keepalive comment (`:` prefix in SSE spec — ignored by EventSource but keeps TCP alive)
     - **On client disconnect**: Break the loop
  4. In a `finally` block: unsubscribe and close the Pub/Sub instance
- **Response**: Streaming response with `text/event-stream` media type
- **Required headers**: `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`

**SSE format**: Each data event follows the protocol: `data: {JSON}\n\n` — note the `data: ` prefix and the double newline terminator. Serialize JSON as a single line.

**Critical SSE details**:
- `X-Accel-Buffering: no` tells Nginx (if present) not to buffer the response — without this, events arrive in batches instead of real-time
- Keepalive comments prevent proxies and browsers from closing idle connections
- The first message after subscribing to Redis Pub/Sub is a confirmation, not data — skip it with `ignore_subscribe_messages=True`
- **Disconnect detection**: Check the framework's disconnect signal at the start of each loop iteration. Without this, the generator runs forever for ghost connections.
- Each SSE connection gets its own Pub/Sub instance — they are NOT shareable

#### Endpoint 4: Download (GET)

Serves the result file for a completed task with ownership and permission verification.

- **Auth**: Standard JWT auth dependency
- **Look up**: Use the task service's get method with the user identity — this returns None if the task doesn't exist OR belongs to another user (ownership check)
- **404 if not found**: Do not distinguish between "doesn't exist" and "belongs to another user" — both return 404 to prevent information leakage
- **Re-check permission**: Verify the user still has the permission for the task's request type. This prevents downloading results after access was revoked since submission.
- **Check completion**: Return 400 if status is not "completed". Return 500 if file_path is empty or file doesn't exist on disk.
- **Serve file**: Use the framework's file response with an appropriate content type and a meaningful filename in the Content-Disposition header (so the browser downloads with a useful name, not a UUID)

#### Register the router

Add the new router to the main application alongside existing router registrations.

### Verify

- Submit a request → get 202 with task ID
- Submit with insufficient permissions → get 403
- Submit unknown request type → get 400
- List tasks → get the submitted task
- Connect to SSE stream → see events arrive when a new task is submitted
- Wait for completion → download the file
- Try downloading another user's task → get 404
- Try downloading before completion → get 400

---

## Phase 5: Frontend SSE Proxy Route

> **Before starting**: Search the frontend for existing API routes, how the httpOnly cookie is set and read, and how server-side fetch is used. Read the auth session cookie route — it establishes the pattern for reading cookies and forwarding tokens.

### Goal

Create a frontend API route that proxies the backend SSE stream. The browser's EventSource connects to this same-origin route. The route reads the httpOnly auth cookie, forwards it as an Authorization Bearer header to the backend, and pipes the streaming response through. The JWT is never exposed in a URL or to client-side JavaScript.

### What to build

1. **Create a GET API route** at a path like `/api/requests/stream` (follow the project's existing API route naming conventions):
   - Read the httpOnly session cookie using the framework's cookie API
   - If no cookie exists, return 401
   - Open a fetch to the backend SSE endpoint with `Authorization: Bearer {token}` header
   - If the backend returns non-200 (e.g., 401 for expired token), return the same status to the browser
   - Create a new Response using the fetch response's ReadableStream body — this creates a passthrough pipe where the server reads chunks from the backend as they arrive and forwards them immediately

2. **Set streaming headers** on the response:
   - `Content-Type: text/event-stream`
   - `Cache-Control: no-cache, no-transform`
   - `Connection: keep-alive`
   - `X-Accel-Buffering: no`

3. **Ensure no buffering**: The framework may buffer responses by default. If events arrive in bursts instead of one-by-one, force dynamic rendering (disable static optimization) or use the edge runtime.

### Why this proxy is necessary

The EventSource API does not support custom headers. You cannot pass an Authorization header with EventSource. The only alternatives are:
- **Token in URL query parameter**: Insecure — tokens appear in server logs, browser history, and referrer headers
- **Same-origin proxy**: The browser sends cookies automatically to same-origin routes. The proxy reads the httpOnly cookie (inaccessible to JavaScript) and forwards it as a standard Authorization header to the backend. Clean, secure, and simple.

### Cleanup chain

When the browser closes the EventSource, the cleanup cascades automatically:
1. Browser closes the SSE connection
2. Frontend server detects the client disconnect
3. The ReadableStream pipe breaks
4. The fetch connection to the backend is aborted
5. The backend's disconnect detection returns True
6. The SSE generator's finally block cleans up the Redis Pub/Sub subscription

No explicit cleanup code needed — it's a natural consequence of the streaming pipe pattern.

### Verify

- Use curl with a cookie to connect to the proxy route — SSE events should stream through
- Remove the cookie → get 401
- Events should arrive one-by-one (not buffered)
- Closing the connection should propagate cleanly to the backend

---

## Phase 6: Frontend Types + API Helpers + EventSource Hook

> **Before starting**: Search the frontend for existing type definitions, API helper functions, custom hooks, and how the auth context provides tokens. Read the existing patterns to understand naming conventions, error handling, and how API calls are structured.

### Goal

Build the client-side infrastructure: TypeScript interfaces for task data, API helper functions for submitting requests and downloading results, and an EventSource hook that connects to the SSE proxy and provides live task state.

### What to build

#### Type definitions

Add to the existing types file (do not remove existing interfaces):

1. **Task status type**: A union of the four status strings: "pending", "running", "completed", "failed"
2. **Task record interface**: Matches the backend's API response model — id, request_type, status, created_at, updated_at, error, parameters
3. **Submit request body interface**: request_type string and parameters record
4. **SSE event payload interface**: Contains an array of task records (this is the shape of each SSE data event)

#### API helpers

Add to the existing API helpers file alongside the existing functions:

5. **Submit request function**: Takes an auth token, request type, and parameters. POSTs to the backend submit endpoint. Handles specific error codes:
   - 202: parse and return the task record
   - 403: throw a clear "permission denied" error
   - 400: parse the error detail and throw
   - Other: throw a generic error

6. **Download result function**: Takes an auth token and task ID. Triggers a file download in the browser by:
   - Fetching from the backend download endpoint with the auth header
   - Handling specific error codes (404 not found, 403 access denied, 400 not yet completed)
   - Extracting the filename from the Content-Disposition header (fall back to a sensible default)
   - Converting the response to a Blob
   - Creating a temporary object URL and anchor element
   - Programmatically clicking the anchor to trigger the download
   - Cleaning up the object URL and element
   - This pattern works in all modern browsers without opening a new tab

#### EventSource hook

7. **Create a custom React hook** that manages the EventSource connection lifecycle:
   - **No token parameter** — the SSE proxy reads the httpOnly cookie automatically
   - **Returns**: `{ tasks: TaskRecord[], isConnected: boolean }`
   - **On mount** (useEffect with empty dependency array): Create a new EventSource connecting to the proxy route (same origin, cookies sent automatically)
   - **onopen handler**: Set isConnected to true
   - **onmessage handler**: Parse the SSE event data as JSON, extract the tasks array, update state
   - **onerror handler**: Set isConnected to false. **Do NOT close the EventSource** — the browser's EventSource API automatically reconnects with exponential backoff. Closing it here would stop reconnection permanently.
   - **Cleanup function** (returned from useEffect): Close the EventSource when the component unmounts
   - **Dependency array**: Empty — the EventSource is created once on mount, not dependent on any token or state

### Automatic edge case handling

The hook handles these scenarios without extra code:
- **Page refresh**: useEffect creates a new EventSource, initial task list arrives immediately
- **Network interruption**: EventSource auto-reconnects, onerror fires during the gap, onopen fires when reconnected
- **Token expiry**: The proxy returns 401, EventSource errors. The app's main auth flow should detect this.
- **Component unmount**: Cleanup closes the EventSource, cascading through the proxy to clean up the backend Pub/Sub subscription

### Verify

- Import the hook in a test component, render the tasks as JSON
- Confirm the EventSource connection appears in browser DevTools Network tab (type: eventsource)
- Submit a request via curl — task should appear in the rendered JSON
- Watch status transitions happen in real time
- Block the connection in DevTools — isConnected should become false, then recover when unblocked

---

## Phase 7: Task Hub Page

> **Before starting**: Search the frontend for existing page components, table patterns, the page definitions array, the route permission map, and the navigation icon map. Read the existing protected pages to understand the component structure, styling patterns, and how the sidebar renders navigation items.

### Goal

Build the hub page — a new frontend page that displays all of the user's submitted requests in a live-updating table with status badges, download buttons, and an empty state.

### What to build

#### Navigation integration

1. **Add a new icon** to the navigation component's icon map — choose an appropriate icon from the icon library already used in the project (something representing a list, clipboard, or inbox).

2. **Add the hub to the page definitions array** used by the sidebar. Place it in the "always visible" group (alongside dashboard/settings) since every authenticated user should see their request history. Set its required permission string and visibility mode accordingly.

3. **Add the route to the frontend middleware's permission map** so Gate 1 checks the hub's permission before allowing navigation.

#### Page component

4. **Create the page component** in the protected page directory (follow the existing directory structure for protected pages):
   - Use the EventSource hook for live task data
   - Use the auth context for the token (needed by the download helper)
   - Track which task is currently downloading (to show loading state on the button)

5. **Header**: Icon + title matching the style of existing pages. Include a **connection status indicator** — a small colored dot (green when connected, red when disconnected) with descriptive text. This gives users confidence that updates are live.

6. **Empty state**: When there are no tasks, show a centered card with a large icon, "No requests yet" message, and a hint to submit from another page.

7. **Task table** (when tasks exist): Render a table with columns for:
   - **Request Type**: The type string, capitalized for display
   - **Status**: A badge with color and icon per status:
     - Pending: warning color, clock icon
     - Running: info color, spinning loader icon (animated)
     - Completed: success color, checkmark icon
     - Failed: error color, alert icon
   - **Submitted**: created_at formatted as a locale-appropriate date/time
   - **Updated**: updated_at formatted as a locale-appropriate date/time
   - **Actions**: Conditional based on status:
     - Completed: "Download" button (with spinner when download is in progress)
     - Failed: Error message text (truncated, full text on hover)
     - Pending/Running: Placeholder or empty

8. **Sort tasks** by creation time descending (newest first) before rendering.

9. **Download handler**: Calls the download API helper, manages the downloading state to show/hide the button spinner. Catches and logs errors.

### Match existing patterns

Follow the table styling, card styling, badge patterns, and page layout conventions already established by the existing protected pages. Read at least two existing table-based pages to understand the styling approach before building this one.

### Verify

- Hub appears in the sidebar for all users
- Empty state displays when no tasks exist
- Connection indicator shows green "Live" when SSE is connected
- Submitting a request (via curl or another page) makes it appear in real time
- Status transitions update live: pending → running → completed
- Download button works for completed tasks
- Failed tasks show the error message
- Blocking the SSE connection shows red "Disconnected", unblocking recovers

## Phase 8: Permission Map Update

> **Before starting**: Read the permission map — the single file/config that maps identity groups to permission strings. Read how the permission resolution function works. Understand the two-gate propagation model.

### Goal

Add the hub page's permission to every group in the permission map so all authenticated users can access it. This is the final wiring step.

### What to build

1. **Add the hub page's permission string** to every group in the permission map. Every authenticated user should see the hub — it only shows their own tasks, so there's no security concern in universal access.

2. **The resolution function does NOT change** — it already handles any permission strings in the map. You are only changing the data it operates on.

### Permission model for the hub

The hub itself is universally accessible. The **gating happens at a different level**:
- "Can you see the hub?" → Always yes (hub permission in every group)
- "Can you submit this request type?" → Depends on the page-specific permission for that request type
- "Can you download this result?" → Depends on both ownership (Redis) AND the original request type permission (re-checked at download time)

This means: a user with basic access can see the hub and track their own tasks, but can only submit request types for pages they have permission to access.

### Two-gate propagation behavior

**Gate 2 (backend)**: Changes take effect immediately for all API calls, even for users with existing tokens. The backend recalculates permissions from the identity groups on every request using the current map.

**Gate 1 (frontend middleware)**: Uses the permissions cached in the JWT. Users who logged in before this change won't have the hub permission in their token. They need to log out and log back in to get a new token. This is expected — Gate 1 is a UX boundary with eventual consistency, not a security boundary. In production, short token TTLs mitigate this window.

### Verify

- Restart the backend so the updated map is loaded
- Log in as each user type — all should have the hub permission in their response
- All users should see the hub in the sidebar and access it without being redirected
- Users with limited permissions can access the hub but cannot submit request types they don't have access to
- Full end-to-end: log in → navigate to a converted page → submit → go to hub → watch status transition → download result → confirm another user can't access it

---

## Completion Checklist

After all phases are implemented:

- [ ] Redis connects on startup, output directory created
- [ ] Task service performs CRUD via Redis hashes and sets
- [ ] Runner functions write files, update Redis, trigger Pub/Sub notifications
- [ ] Submit endpoint returns 202, list endpoint returns tasks, SSE streams updates, download serves files
- [ ] Frontend proxy streams SSE without exposing the auth token
- [ ] EventSource hook receives live updates via the proxy
- [ ] Hub page renders live table with status badges, download buttons, and empty state
- [ ] All users see the hub; request type submission gated by existing page permissions
- [ ] Cross-user isolation: user A cannot see or download user B's tasks
- [ ] Multi-worker: submit on Worker A, SSE on Worker B → update still arrives via Redis Pub/Sub
- [ ] Permission revocation: removing a permission blocks both new submissions AND downloads of existing results
