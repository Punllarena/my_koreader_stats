# Updating reading stats on RanobeDB (guide for my_koreader_stats)

Base URL: `https://ranobedb.org/api/v0`
Full reference: `https://ranobedb.org/api/docs/v0`

This guide covers only what a KOReader stats sync needs: authenticate, find the book on RanobeDB, then set its reading status, dates and score.

## 1. Authentication

Create a personal access token in your RanobeDB account settings (`/settings`). Send it on every `/user` request:

```
Authorization: Bearer <token>
```

| Status | Cause |
| --- | --- |
| 400 | Malformed `Authorization` header (not `Bearer <token>`). Body: `{"message":"Invalid authorization header format"}` |
| 401 | Missing or invalid token. Body: `{"message":"unauthorized"}` |

Check the token works:

```sh
curl https://ranobedb.org/api/v0/user/me -H "Authorization: Bearer <token>"
```

It returns the user (`id`, `username`, `id_numeric`, `role`, `display_prefs`, `behavior_settings`, ...). Use this as a "test connection" button.

Rate limit: no hard limit, but stay at or below 60 requests per minute. Sync with a short delay between books.

## 2. Finding the RanobeDB book id

The `/user` endpoints are keyed by RanobeDB **book id** (the number in `https://ranobedb.org/book/48857`). KOReader does not know it, so map it once and cache it locally (e.g. keyed by the KOReader document hash or title).

Search (public, no token needed):

```sh
curl "https://ranobedb.org/api/v0/books?q=seishun+buta+yarou&limit=5"
```

- Use `q` for the title, `limit` for the page size and `page` to paginate.
- Take `books[].id` from the result. Let the user confirm the match the first time; do not guess silently.
- Look up one book with `GET /book/{id}`. It returns the book and its `series` list, which gives you the series id.

## 3. Updating a book: `PUT /user/book/{id}`

One call adds the book to the list, or edits it if already there. The response says which: `{"success": true, "action": "add" | "edit"}`.

Body (JSON, `Content-Type: application/json`):

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `readingStatus` | `'Reading' \| 'Finished' \| 'Plan to read' \| 'Stalled' \| 'Dropped' \| 'Other'` | yes | |
| `selectedCustLabels` | `number[]` | yes | Ids of the user's custom labels. Send `[]` for none. Any id that is not one of the user's own labels returns 400. |
| `started` | `'YYYY-MM-DD' \| '' \| null` | no | |
| `finished` | `'YYYY-MM-DD' \| '' \| null` | no | |
| `score` | `number \| null` | no | 1 to 10 in steps of 0.1. |
| `notes` | `string \| null` | no | Max 2000 characters. |

### Mapping KOReader stats to fields

| KOReader state | Send |
| --- | --- |
| Opened, progress under 100% | `readingStatus: "Reading"`, `started` = date of first read (from stats DB) |
| Progress reached 100% / marked finished | `readingStatus: "Finished"`, `started`, `finished` = date of last read |
| Marked on hold / abandoned | `"Stalled"` / `"Dropped"` |

Example:

```sh
curl -X PUT "https://ranobedb.org/api/v0/user/book/48857" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"readingStatus":"Finished","selectedCustLabels":[],"started":"2026-10-02","finished":"2026-10-19"}'
```

Response: `{"success":true,"action":"add"}`

### Important: edits replace the whole entry

When the book is already in the list, the PUT **overwrites** every field. Anything you omit is reset, not kept:

- `notes` omitted -> notes become empty.
- `started` / `finished` omitted -> dates cleared.
- `score` omitted -> score cleared.
- `selectedCustLabels` is set to exactly what you send.

There is no read endpoint for a single list entry through the bearer token, so you cannot fetch-then-merge. Either:

1. Only let my_koreader_stats own the fields it syncs and tell users it overwrites notes/score/labels, or
2. Store the last values you sent (status, dates, score, notes, labels) locally and re-send them all on each update.

Option 2 is safer. Note that the user's `behavior_settings.reading_dates` (visible from `/user/me`) controls site-side auto-filling and clearing of dates on status changes. Don't rely on it for API calls; send dates explicitly.

## 4. Optional: series progress, `PUT /user/series/{id}`

If you also want to record how many volumes have been read, update the series entry. It uses the same adding/editing behavior and the same overwrite rule.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `readingStatus` | status enum | yes | |
| `selectedCustLabels` | `number[]` | yes | |
| `langs` | `Language[]` | yes | e.g. `["en"]`. Languages tracked for upcoming books. |
| `formats` | `('digital' \| 'print' \| 'audio')[]` | yes | |
| `volumes_read` | `number \| null` | no | |
| `notify_book` | boolean | no | default `true` |
| `notify_when_released` | boolean | no | default `false` |
| `show_upcoming` | boolean | no | default `true` |
| `score`, `started`, `finished`, `notes` | as for books | no | |

```sh
curl -X PUT "https://ranobedb.org/api/v0/user/series/1" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"readingStatus":"Reading","selectedCustLabels":[],"langs":["en"],"formats":["digital"],"volumes_read":4}'
```

Because `langs`/`formats` also drive upcoming-book tracking, avoid silently changing them. Ask the user for their preference once and store it.

## 5. Removing: `DELETE /user/book/{id}`

Removes the book from the list. Returns `{"success": true}`. If the book is not in the list it returns 400 (`Book is not in the list`).

## 6. Error handling

| Status | Meaning | What to do |
| --- | --- | --- |
| 200 | Success | Mark the book as synced. |
| 400 | Bad JSON, invalid field, unknown book id, unknown custom label id, or deleting an entry that is not in the list | Read the body, do not retry unchanged. Validation errors come back as a zod tree describing the bad field. |
| 401 | Bad or missing token | Prompt the user to re-enter the token. |
| 404 (HTML page, not JSON) | `{id}` in the path is not an integer | Fix the id. |
| 5xx / network | Server or connection problem | Retry later with backoff and keep the update queued. |

Note that a missing book is a `400`, not a `404`.

## 7. Suggested sync flow

1. On setup, call `GET /user/me` to validate the token and store the token.
2. For each KOReader book with new reading activity:
   1. Resolve the RanobeDB id (cached mapping, otherwise `GET /books?q=...` and ask the user to confirm).
   2. Compute `readingStatus`, `started`, `finished` from the stats DB.
   3. Skip if it matches the last payload you sent for this book (avoids needless requests and keeps you under 60 per minute).
   4. `PUT /user/book/{id}` with the full payload, including previously stored `score`, `notes` and `selectedCustLabels`.
   5. Store the payload on success.
3. Space requests out (about 1 per second is well under the limit).

## 8. Minimal TypeScript client

```ts
const BASE = 'https://ranobedb.org/api/v0';

type ReadingStatus = 'Reading' | 'Finished' | 'Plan to read' | 'Stalled' | 'Dropped' | 'Other';

interface BookListPayload {
	readingStatus: ReadingStatus;
	selectedCustLabels: number[];
	started?: string | null; // YYYY-MM-DD
	finished?: string | null;
	score?: number | null; // 1-10, step 0.1
	notes?: string | null; // max 2000 chars
}

async function putUserBook(token: string, bookId: number, payload: BookListPayload) {
	const res = await fetch(`${BASE}/user/book/${bookId}`, {
		method: 'PUT',
		headers: {
			Authorization: `Bearer ${token}`,
			'Content-Type': 'application/json',
		},
		body: JSON.stringify(payload),
	});
	if (!res.ok) throw new Error(`RanobeDB ${res.status}: ${await res.text()}`);
	return (await res.json()) as { success: true; action: 'add' | 'edit' };
}
```
