# Coach Chat v1

Coach Chat adds persistent, user-owned conversations around the existing
read-only Coach Agent. It does not add a second training decision engine.

```text
Coach Chat UI
  -> Conversation API
  -> Conversation Service (storage, idempotency, context window)
  -> existing Coach Agent (tools, RAG, Evidence, Validator)
  -> safe assistant message persistence
```

## Data boundary

`coach_conversations` belongs directly to one `user_account`.
`coach_messages` belongs to one conversation and has a stable `sequence_no`.
The `(conversation_id, client_turn_id)` uniqueness constraint makes retrying a
browser request idempotent. The service permits only one generating turn per
conversation, but different conversations may generate independently. Each
generation also has a server-side lease token: a late result from an expired or
superseded request cannot overwrite a newer reply or clear its processing lock.

Only the user message and the safe final Coach response are stored. Raw tool
payloads, provider reasoning, prompts, credentials and Garmin tokens are never
stored in this layer. Deleting a conversation cascades to its messages; a late
provider result is discarded if the conversation no longer exists.

## Context and freshness

Recent completed messages are selected under both a message-count window and a
conservative token budget. They help resolve words such as “那次” and “周四”,
but are never treated as verified training facts. Every Coach turn continues to
use the existing authenticated, read-only tools to obtain current plan, logs,
synced activities, Runner State and knowledge references.

The default window is controlled by:

```env
COACH_CONVERSATION_HISTORY_MESSAGES=16
COACH_CONVERSATION_HISTORY_TOKEN_BUDGET=1800
COACH_CONVERSATION_TURN_TIMEOUT_SECONDS=180
```

There is no automatic long-term memory, cross-conversation semantic retrieval,
history vector store, token streaming or plan-writing tool in v1.

If a process stops during an external model call, its pending turn remains
visible. After `COACH_CONVERSATION_TURN_TIMEOUT_SECONDS`, a retry using the same
`client_turn_id` safely reuses the stored user message rather than duplicating it.
The stale assistant placeholder is marked failed and can be retried; no request
holds a database transaction while waiting for the model.

## Database upgrade

Back up the MySQL database first, then run in the deployed backend directory:

```powershell
python scripts/upgrade_v0165_coach_chat.py upgrade
```

The forward upgrade only creates `coach_conversations` and `coach_messages`.
Rollback is intentionally destructive because it deletes chat data; restore a
database backup, or explicitly run the script’s guarded downgrade only after
exporting the intended data.

For a real MySQL acceptance test, create an empty *local* database whose name
starts with `gaitlogic_test_`, then supply it explicitly (never point this at a
development or production database):

```powershell
$env:GAITLOGIC_COACH_CHAT_TEST_DATABASE_URL = "mysql+pymysql://test_user:test_password@127.0.0.1:3306/gaitlogic_test_coach_chat"
python -m pytest tests/test_coach_chat_mysql_integration.py -m mysql_integration -q
```

The test refuses non-local hosts and database names outside that prefix, runs
the upgrade twice, checks its foreign keys/indexes/unique constraint and checks
message cascade deletion. It drops only its three synthetic tables afterwards.

## API

- `POST /api/coach/conversations`
- `GET /api/coach/conversations`
- `GET /api/coach/conversations/{conversation_id}`
- `GET /api/coach/conversations/{conversation_id}/messages`
- `POST /api/coach/conversations/{conversation_id}/messages`
- `PATCH /api/coach/conversations/{conversation_id}`
- `DELETE /api/coach/conversations/{conversation_id}`

All endpoints derive identity from the JWT context. They never accept a client
`user_id` and check ownership again for optional business references.

Message history is paginated and bounded. Page 1 contains the newest page while
remaining chronological within that page; requesting page 2 and beyond returns
older messages without overlap.

## Observability

The existing `SafeTracer` records conversation lifecycle spans only with safe,
low-cardinality metadata: `conversation.message.submit`,
`conversation.context.build` and `conversation.coach.execute`. Chat body,
history, raw training data and provider reasoning do not enter traces or metric
labels.
