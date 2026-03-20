# Permissions Flow — Generic Implementation Plan

## Instructions for the Implementing Agent

**Before implementing any phase**, you MUST:

1. Search the entire codebase for existing implementations of the concepts described in that phase (auth helpers, middleware, context providers, Redis usage, session management, route protection, etc.)
2. Read every file you find. Understand the naming conventions, folder structure, import patterns, and state management approach already in use.
3. Identify what already exists that can be reused or extended — do NOT create new files or abstractions when the codebase already has equivalent functionality.
4. Only then design the implementation to fit the patterns you found.

**Do NOT copy code from this plan or from any reference project.** This plan describes concepts and architecture. The implementation must be derived from the target codebase's existing patterns.

---

## Context: The Problem This Solves

The app uses Microsoft Entra ID (via Better Auth) for login. Entra ID returns a JWT containing the user's Active Directory **group membership GUIDs**. These group GUIDs are raw identity data — they don't mean anything to the application by themselves.

This plan adds a **permission resolution layer** that:
- Maps AD group GUIDs to application-specific permission strings
- Enforces permissions on every backend API endpoint
- Enforces permissions on every frontend route via middleware
- Dynamically shows, hides, or locks UI elements based on the current user's permissions
- Coexists with the existing chat session system without interfering with it

---

## Core Architecture: Two-Tier Sessions

The app has two session concepts that are **hierarchical, not competing**:

### Tier 1 — Auth Session (Identity + Permissions)
- Created at login via Better Auth + Entra ID
- Contains: user identity, AD group GUIDs, resolved application permissions
- Stored in: httpOnly cookie (for middleware) and available to the frontend context
- Lifetime: matches the auth session TTL
- Answers the question: **"Who is this user and what are they allowed to do?"**

### Tier 2 — Chat Session (Conversation Context)
- Created on demand when the user starts a new chat
- Contains: a UUID identifier used as the Redis key for that conversation's short-term memory
- Stored in: Redis, namespaced by the user's identity
- Lifetime: ephemeral, governed by Redis TTL or explicit deletion
- Answers the question: **"Which conversation are we in right now?"**

These never conflict because they answer different questions. Every chat API request carries BOTH: the auth token (Tier 1, in the Authorization header) proving who you are, and the chat ID (Tier 2, in the URL) saying which conversation to operate on.

---

## Permission Namespace Design

Permissions are flat strings following a `namespace:resource` convention:

| Namespace | Controls | Examples |
|---|---|---|
| `page:` | Route/page access | `page:dashboard`, `page:chat`, `page:admin-panel` |
| `tool:` | AI tool availability within chat | `tool:basic-search`, `tool:sql-query`, `tool:data-analyzer` |
| `action:` | CRUD operations (future) | `action:reports:delete`, `action:users:invite` |

A single dictionary maps each AD group GUID to its granted permissions. A user in multiple groups gets the **union** of all permissions across all their groups.

---

## The Two-Gate Model

Security is enforced at two independent layers. Both must pass for data access.

**Gate 1 — Frontend Middleware (UX boundary)**
- Runs on every page navigation, server-side, before React renders
- Reads the httpOnly cookie containing the app JWT
- Decodes the JWT payload (base64 only — does NOT verify the signature)
- Checks if the user's permissions include the required permission for that route
- On failure: redirects to a safe page (like dashboard) — no error shown, just a smooth redirect
- Purpose: prevents loading pages that would immediately fail at the API level

**Gate 2 — Backend API Dependency (Security boundary)**
- Runs on every API call
- Reads the Authorization header, verifies the JWT signature
- Re-derives permissions from the groups claim using the current permission map (does NOT trust the permissions array in the JWT)
- Checks if the required permission is present
- On failure: returns HTTP 403
- Purpose: the real security enforcement — even if Gate 1 is bypassed, no data is exposed

Gate 2 recalculating permissions from groups (rather than trusting the JWT) means you can update the permission map and changes take effect immediately on all API calls without invalidating any tokens.

---

## UI Visibility Strategies

The frontend sidebar uses three visibility modes per navigation item:

| Mode | Behavior | Use for |
|---|---|---|
| `"always"` | Always visible in sidebar, regardless of permission | Core pages every user is expected to have (dashboard, settings, chat) |
| `"permission"` | Completely hidden if the user lacks the permission — no trace in the DOM | Department-specific pages where showing existence adds no value |
| `"locked"` | Visible to everyone, but shows a lock icon and is non-clickable without permission | Admin features users may want to request access to |

The same `hasPermission()` helper used for sidebar visibility can conditionally render any UI element: buttons, panels, tool palettes, form fields, etc.

---

## Phase 1: Backend Permission Foundation

> **Before starting**: Search the backend codebase for any existing auth dependencies, middleware, permission checks, or group-handling code. Read the existing FastAPI app structure, router organization, and dependency injection patterns.

**Goal**: Create the permission resolution engine — the single source of truth mapping AD groups to application permissions.

**What to build:**
1. A permission map — a dictionary keyed by Entra ID group GUIDs, with values being lists of permission strings. This is the one file you edit to change access for any group.
2. A resolution function — takes a list of group IDs, returns the sorted, deduplicated union of all their permissions.
3. A FastAPI dependency that extracts the Bearer token, verifies its signature, reads the groups claim, and calls the resolution function to build a user claims object with live permissions.
4. A permission-checking dependency factory — takes one or more required permission strings and returns a FastAPI dependency that asserts all are present, raising 403 if any are missing. The dependency chain is: extract token → verify + resolve → check required permissions → pass user claims to handler.
5. Pydantic models for the user claims object (used internally) and user response object (returned to frontend).

**Verify**: Call the resolution function with known group IDs and confirm the correct permissions are returned.

---

## Phase 2: Token Exchange Endpoint

> **Before starting**: Search the backend for existing auth/login endpoints. Read how Better Auth's session data currently reaches the backend. Understand what token or user info is already available after login.

**Goal**: Create the endpoint that receives Entra ID identity data (from Better Auth) and returns an app-specific JWT containing resolved permissions.

**What to build:**
1. An exchange endpoint that receives the Entra ID token or user info from Better Auth's authentication flow.
2. The endpoint extracts the groups claim, resolves permissions, and signs an app JWT containing: email, name, oid (stable user identifier), groups, and permissions.
3. A "me" endpoint that accepts the app JWT and returns the current user's info — used by the frontend to rehydrate on page refresh.

**Design decision**: Since Better Auth already validates the Entra ID token, the exchange endpoint can either (a) trust Better Auth's validation and accept plain user info, or (b) re-validate the raw id_token against Microsoft's JWKS. Option (a) is simpler and fine if the exchange is only called server-side.

**Verify**: POST to the exchange endpoint with test data → receive a JWT → decode it → see the permissions array.

---

## Phase 3: Better Auth ↔ Backend Integration

> **Before starting**: Read how Better Auth is configured in the frontend. Find the auth client setup, any existing callbacks, and how the session is currently stored and accessed. Search for existing API routes under `/api/auth/`.

**Goal**: Wire the token exchange into the login flow so it happens automatically, and the app JWT is stored where both the middleware and frontend can access it.

**What to build:**
1. A Better Auth callback (or Next.js API route) that fires after successful Entra ID authentication and calls the backend exchange endpoint server-side.
2. A session cookie API route — POST sets the app JWT as an httpOnly cookie (for the middleware to read), DELETE clears it on logout.
3. The frontend needs the app JWT stored in two places: the httpOnly cookie (for middleware, inaccessible to JavaScript) and available to the auth context (for API calls and permission checks).

**Verify**: Complete login flow → confirm the httpOnly cookie is set → confirm the frontend auth context has the permissions array.

---

## Phase 4: Frontend Auth Context + Middleware

> **Before starting**: Search the frontend for existing context providers, auth state management, and any middleware files. Read the app's routing structure (App Router layout groups, protected vs public routes). Understand how the existing session state is managed.

**Goal**: Build (or extend) the auth context to expose permissions and the middleware to protect routes.

**What to build:**

**Auth Context:**
1. A provider that holds the current user, their permissions array, the app JWT, and loading state.
2. A `hasPermission(permissionString)` function exposed through the context — returns true/false.
3. Session hydration on mount: check for existing session, call the "me" endpoint to validate and refresh user data.
4. Login function: triggers Better Auth sign-in, which flows through the exchange (Phase 3).
5. Logout function: clears local state and the httpOnly cookie.

**Middleware:**
1. A route permission map — each protected route path mapped to its required permission string.
2. On every request: check for the cookie → decode the JWT payload (base64 only) → check the required permission → redirect if missing.
3. Public routes (login, static files, API routes) pass through without checks.
4. Authenticated but unauthorized users redirect to a safe default page (not back to login).

**Verify**: Log in as different users → middleware blocks unauthorized routes → context correctly reports permissions via `hasPermission()`.

---

## Phase 5: Dynamic Sidebar + Page Protection

> **Before starting**: Search the frontend for existing navigation/sidebar components, route definitions, and any existing page config arrays. Read how icons and navigation state are currently handled.

**Goal**: Make the sidebar dynamically reflect permissions and protect each backend page endpoint.

**What to build:**

**Frontend:**
1. A central page definitions array — each entry has: path, label, icon identifier, required permission string, and visibility mode (always/permission/locked).
2. The sidebar filters this array based on the current user's permissions and the visibility rules.
3. Navigation items render in one of three states: clickable link (has access), locked div with lock icon (visible but denied), or not rendered at all (hidden).

**Backend:**
1. Each page data endpoint uses the permission-checking dependency from Phase 1 with the appropriate permission string.

**Verify**: Log in as each user tier → sidebar shows the correct items in the correct states → backend returns 403 for unauthorized endpoint calls.

---

## Phase 6: Chat Session Layer

> **Before starting**: Read ALL existing chat-related code — routes, Redis usage, session creation, message handling, any existing chat context or state management. Understand the current Redis key schema and how chat UUIDs are generated and tracked.

**Goal**: Integrate the permission system with the existing chat sessions without breaking the current flow.

**What to build:**

**Backend:**
1. Protect all chat endpoints with the permission-checking dependency requiring `page:chat` (or whatever permission string you choose for chat access).
2. Namespace Redis keys by user identity — include the user's stable identifier (oid) in the key prefix. This enforces ownership at the data layer: the backend only reads/writes keys that start with the authenticated user's ID.
3. Add ownership verification: before any chat operation, confirm the chat belongs to the requesting user by checking the key prefix matches their identity.

**Frontend:**
1. A chat context (or extend the existing one) that manages: active chat ID, chat list, create/switch/delete operations.
2. The chat context uses the app JWT from the auth context for all API calls.
3. The chat context has NO concept of permissions — it delegates that entirely to the auth context. If the user can see the chat page, they can use the chat context.

**State hierarchy:**
- AuthProvider wraps the entire app (provides permissions, identity, token)
- ChatProvider wraps only the chat-related pages (provides active chat, chat list)
- Chat components read from both contexts: AuthContext for "can I do this?" and ChatContext for "which conversation?"

**Verify**: Create chats → switch between them → verify Redis keys include the user identifier → verify one user cannot access another user's chats via direct API calls.

---

## Phase 7: Tool-Level Permissions in Chat

> **Before starting**: Read how AI tools/functions are currently defined and passed to the LLM. Search for tool registration, tool lists, or function definitions. Understand the message handling pipeline.

**Goal**: Filter which AI tools are available to each user based on their AD group permissions.

**What to build:**

**Backend:**
1. Each AI tool should have a corresponding permission string (e.g., `tool:sql-query`).
2. In the chat message handler, after authenticating the user, filter the tool list to include only tools whose permission string appears in the user's resolved permissions.
3. Pass only the filtered tool list to the LLM — users never even see responses from tools they lack permission for.

**Frontend:**
1. In the chat UI, use `hasPermission()` to conditionally render tool buttons, tool palettes, or tool selection UI. If a user doesn't have `tool:sql-query`, the SQL query button simply doesn't appear.
2. This is a UX convenience — the backend filtering (above) is the security boundary.

**Verify**: Log in as different users → confirm different tools are available in the chat UI → confirm the backend only passes permitted tools to the LLM → confirm a direct API call with a non-permitted tool is rejected or ignored.

---

## How Permission Changes Propagate

| What changed | Effect | When it takes effect |
|---|---|---|
| Edit the permission map (add/remove permission for a group) | All new API calls use the updated map (Gate 2 recalculates) | Immediately for API calls. Gate 1 (middleware) uses the JWT cache until token expires. |
| User added to / removed from an AD group | New group memberships reflected in next login (new JWT issued) | Next login |
| Need instant revocation | Implement a token blocklist (checked in the auth dependency) | Immediately if blocklist is checked on every request |
| Shorten token TTL | Reduces the window where stale permissions persist at Gate 1 | Only affects newly issued tokens |

---

## Checklist Summary

- [ ] Phase 1: Permission map + resolution function + auth dependency + RBAC dependency
- [ ] Phase 2: Token exchange endpoint + "me" endpoint
- [ ] Phase 3: Better Auth callback wired to exchange + httpOnly cookie management
- [ ] Phase 4: Auth context with `hasPermission()` + route-protecting middleware
- [ ] Phase 5: Sidebar with dynamic visibility + backend endpoint protection
- [ ] Phase 6: Chat endpoints permission-gated + Redis keys namespaced by user + chat context
- [ ] Phase 7: Tool filtering by permission in chat message handler + conditional tool UI
