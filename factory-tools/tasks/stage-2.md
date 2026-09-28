# Stage 2 task

Copy `stage-1/` forward into `stage-2/` (no `.git` inside it) and extend it to the spec pasted in full below: stage 1's requirements still apply and stage 1 must still pass. Add the browser UI.

## Stage-2-specific traps (in addition to the common list above)

- Race between two searches: if search A starts before search B but resolves after it, the UI must show B's result, not A's: guard against out-of-order response arrival, not just request order.
- Lost response after a booking may still have committed server-side: show `booking-uncertain` (not `booking-error`, not a new confirmation), keep the form and its inputs unchanged, and retry with the **same** idempotency key and body. A successful retry must recover the original reference.
- A confirmed `409 table_unavailable` shows `booking-error` and refreshes availability, but must preserve the diner's selected inputs.
- Submitting the booking form again unchanged must return the same reference, not a new booking; changing a field starts a new request.
- Combinable pairs are declared explicitly and are **not transitive**: `[t1,t2]` and `[t2,t3]` combinable does not make `{t1,t3}` bookable. Only pairs, never 3+.
- `table_id` in the response is present only when the resulting set has exactly one member; omit it otherwise. Sending both `table_id` and `table_ids` in a request is `422 validation_failed`.
- A stage-2 service must accept an export produced by the team's own stage-1 service, and a browser session signed in before that import must remain signed in after: including a pending lost-response retry surviving the upgrade.
- No background polling, live updates or cross-tab sync is required or wanted: don't build it; the server is the sole source of truth and the browser must never manufacture success from cached data.

## Ambiguity rule

If anything below is ambiguous, resolve it by the most conservative reading (the one least likely to violate a hard constraint: no double-booking, no 5xx, no data loss on export/import, no leaked private data). Record the ambiguity and your resolution in `decisions-log.md` at the repo root (append, do not overwrite). Never ask a human, never pause for approval: proceed on your own reading and move on.

## Traps that apply to every stage

- Overlap is a half-open interval `[starts_at, starts_at + duration)`. A booking ending exactly when another starts does not overlap it.
- Idempotency is resolved *before* endpoint-specific validation: a reused `Idempotency-Key` with a different body is `409 idempotency_key_reuse` even if that new body would itself be invalid.
- Unknown JSON fields and unknown query parameters are ignored, never an error.
- IDs (including ones supplied in reset fixtures) are opaque strings, at most 64 characters.
- No 5xx responses under any circumstance, including 50 concurrent in-flight requests within a 5 s per-request timeout (10 s for `POST /_test/reset` and other test-control endpoints).
- The container has **no outbound network at runtime**: bundle a full IANA tz database in the image; do not fetch it at startup.
- Password hashing (bcrypt/scrypt/Argon2 or equivalent) must complete fast enough that 50 concurrent signups/logins each still finish inside their 5 s timeout: do not pick cost parameters that blow the budget under load.
- `GET /_test/export` and `POST /_test/import` must round-trip tokens, hashed passwords, and the stored original response of every completed idempotent request (so a replay after import still returns byte-identical JSON). Import is atomic replacement, not merge.
- Query-parameter integers must be plain decimal digits: `1e9`, `4.0`, `+4` are `422 validation_failed` regardless of numeric value.

## Full specification (verbatim)

```markdown
# Tablekeeper — Stage 2: online booking and combined tables

The stage-1 requirements continue to apply, with the additions below. Numbered section
references such as §5 and §7 refer to `stage-1.md`.

Diners can search, book and manage reservations in a browser. Restaurants can offer
approved pairs of tables for larger parties.

The following screens must be reachable by URL. Other screens must be reachable through
the UI. Server-side and client-side rendering are both permitted.

| Route | Screen |
|---|---|
| `/` | Search and availability grid |
| `/signup` | Signup |
| `/login` | Login |
| `/lookup` | Look up a reservation by reference |

A screen route returns HTML; §3.4's `application/json` convention is about the API, and does
not govern the routes in the table above.

## Competing clients and uncertain outcomes

The UI must handle responses arriving out of order and connections failing after submission.

- If search A starts before search B but finishes after it, the grid, table labels and
  booking form must describe B. A late response must not restore A's results.
- If another client takes a table after the form opens, a `409 table_unavailable` response
  shows `booking-error` and refreshes availability. Preserve the selected form and its
  inputs so the diner can change their choice. Do not show a confirmation for that attempt.
- If a booking response is lost, including after the booking commits, show nonempty
  `booking-uncertain` text, without `booking-error` or a new confirmation. The unchanged
  form must retry with the same idempotency key and body. A successful retry removes the
  uncertainty/error elements and shows the original reference. A confirmed rejection
  uses `booking-error`.

These rules apply to combination bookings too. No background polling, live updates,
cross-tab storage synchronization, or recovery across a page reload is required. The server
remains authoritative; the browser must not manufacture a successful result from cached data.

The UI must expose the `data-testid` attributes listed below for integration testing.
Additional elements are permitted, and the visual implementation is the team's choice subject
to the product-quality requirements below.

## Product and visual direction

The browser experience must feel like a coherent, presentation-ready restaurant product, not a
test harness with controls attached. Aim for a warm, confident hospitality character. The search,
availability and booking flow should have an obvious visual hierarchy; a diner should be able to
scan dates, times, party size and table choices without having to interpret raw API data. Combined
tables should read as intentional seating options, not as concatenated technical identifiers.

Use a consistent visual system for typography, spacing, colour, controls and feedback. Primary
actions must be easy to identify. Available, unavailable, selected, loading, successful, refused
and uncertain states must be visually distinct as well as satisfying the behavioural requirements
below. Use human-readable restaurant and table labels prominently; expose technical identifiers
only where they help the user.

The required flows must remain clear and usable at a 375 CSS-pixel viewport and at conventional
desktop widths, without horizontal page scrolling. Inputs need visible labels, keyboard focus must
be apparent, and text and controls need sufficient contrast. Provide considered empty, loading and
error states, and keep navigation consistent across the required routes. A custom illustration,
brand asset or exact visual match to a reference is not required.

## Signup and login

| `data-testid` | Element |
|---|---|
| `signup-email`, `signup-password`, `signup-display-name` | Inputs |
| `signup-submit` | Button |
| `login-email`, `login-password`, `login-submit` | Inputs and button |
| `auth-error` | Error message. Present only when there is one |
| `current-user` | Visible on every screen when signed in. Text contains the display name |
| `logout-button` | Button |

## Search and availability grid — `/`

| `data-testid` | Element |
|---|---|
| `restaurant-select` | Selects a restaurant. Option values are restaurant ids |
| `date-input` | Date, value `YYYY-MM-DD` |
| `party-size-input` | Number |
| `search-button` | Runs the search |
| `availability-grid` | Container for the results |
| `slot-{table_id}-{HH:MM}` | One cell per table per slot, e.g. `slot-t_2-19:00` |
| `no-slots` | Shown instead of the grid when the day has no slots |

Each cell carries `data-available="true"` or `data-available="false"`. A cell is `true` exactly
when its `table_id` is in that slot's `available_table_ids` from `GET /availability` for the party
size that was searched, and `false` otherwise. Clicking an available cell
opens the booking form for that table and slot. Clicking an unavailable cell does nothing.
Booking requires a signed-in user: clicking an available cell while signed out shows `auth-error`
or navigates to `/login`, your choice.

## Booking form

| `data-testid` | Element |
|---|---|
| `booking-form` | Container |
| `booking-summary` | Text contains the table label and the local start time |
| `booking-party-size` | Number input, pre-filled from the search |
| `booking-submit` | Button |
| `booking-error` | Error message, when the booking fails |

Keep the booking form on screen after success. Submitting it again without changing a
field must return the same `confirmation-reference`, without `booking-error` or another
booking. Changing a field makes the next submission a new booking request. Retries follow §7.

## Confirmation

Shown after a successful booking.

| `data-testid` | Element |
|---|---|
| `confirmation` | Container |
| `confirmation-reference` | Text is exactly the reference, no surrounding words |
| `confirmation-details` | Text contains the restaurant name, table label and local start time |

## Lookup — `/lookup`

| `data-testid` | Element |
|---|---|
| `lookup-reference-input`, `lookup-submit` | Input and button |
| `reservation-detail` | Container, shown when found |
| `reservation-status` | Text is exactly `confirmed` or `cancelled` |
| `reservation-cancel-button` | Cancels. Absent once cancelled |
| `reservation-error` | Shown when not found, or when a cancel is refused |

## Existing clients after an upgrade

A stage-2 service must accept an export produced by the same team's stage-1 service. A
browser signed in before that export/import upgrade must remain signed in afterwards.
A retained booking reference still works through the lookup screen. A booking whose response
was lost before export remains retryable after import with the same body and key; the UI
must recover the original confirmation. These requirements apply when import completes
between browser requests; migration during an in-flight request is not required. No page
reload or new screen is required. The form and pending retry identity must survive the upgrade.

## Combined tables

A party may book two tables that the restaurant has declared combinable. The booking
occupies both tables for its full duration.
Existing single-table request formats remain supported.

## Model

The restaurant fixture gains one field:

```json
{
  "id": "r_anker",
  "combinable": [ ["t_1", "t_2"], ["t_2", "t_3"] ],
  ...
}
```

Each entry is an unordered pair of table ids in that restaurant. **Pairs only** — never three or
more. A pair not listed cannot be combined, whatever the table sizes are. Combining is not
transitive: `[t_1,t_2]` and `[t_2,t_3]` do not make `{t_1,t_3}` bookable.

A combination's capacity is the sum of its tables' capacities.

Seeded `reservations` are `confirmed` unless they carry a `status` of `cancelled`, and may hold
either `table_id` or `table_ids`.

## API

### `GET /availability`

Slots gain `available_options`. `available_table_ids` stays exactly as it was — single tables
only.

```json
{
  "slots": [
    {
      "starts_at_local": "2026-09-24T19:00",
      "starts_at": "2026-09-24T19:00:00+02:00",
      "available_table_ids": ["t_3"],
      "available_options": [
        { "table_ids": ["t_3"], "capacity": 4 },
        { "table_ids": ["t_1", "t_2"], "capacity": 6 }
      ]
    }
  ]
}
```

`available_options` lists every single table and every declared pair with
`capacity >= party_size` and no overlapping confirmed reservation on any member. Singles first in
fixture order, then pairs in `combinable` order. `table_ids` within a pair is in `combinable`
order.

### `POST /reservations`

The body takes `table_ids` instead of `table_id`:

```json
{ "restaurant_id": "r_anker", "table_ids": ["t_1", "t_2"],
  "starts_at_local": "2026-09-24T19:00", "party_size": 6 }
```

`table_id` is still accepted and means a set of one. Sending both is 422 `validation_failed`.

Responses always carry `table_ids`. They also carry `table_id` **when the set has exactly one
member**, and omit it otherwise.

| Case | Response |
|---|---|
| The pair is not in `combinable` | 422 `combination_not_allowed` |
| More than two tables | 422 `combination_not_allowed` |
| Any table in the set is taken for an overlapping interval | 409 `table_unavailable` |
| `party_size` exceeds the combination's summed capacity | 422 `party_exceeds_capacity` |
| Duplicate table id in the set | 422 `validation_failed` |

`PATCH /reservations/{reference}` accepts `table_ids` under the same rules. Cancelling frees every
table in the set.

## UI

The availability grid gains combination cells, shown when a declared pair is available for the
searched party size:

| `data-testid` | Element |
|---|---|
| `slot-{t_a}+{t_b}-{HH:MM}` | A combination cell, e.g. `slot-t_1+t_2-19:00`. Ids in `combinable` order. Carries `data-available` like a single cell |
| `confirmation-tables` | Text contains every table label in the reservation |
| `reservation-tables` | On the lookup screen. Same |

`booking-summary` must name every table in the selection. A single-table booking's cell testid,
confirmation and lookup are unchanged.

Atomic reservation moves from stage 1 also accept `table_ids` per move. No table may
belong to overlapping resulting bookings. The existing browser recovery and original-receipt
requirements also apply to combined-table bookings.

## Concurrent bookings and amendments

Concurrent requests must produce the same results as executing them one at a time in some
order, and the requirements above hold at every read.
```
