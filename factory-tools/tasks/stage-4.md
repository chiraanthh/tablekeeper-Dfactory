# Stage 4 task

Copy `stage-3/` forward into `stage-4/` (no `.git` inside it) and extend it to the spec pasted in full below: stages 1, 2 and 3 still apply and must still pass. No new screens are required, but existing availability/confirmation/lookup screens must reflect an applied plan.

## Stage-4-specific traps (in addition to the common list above)

- Replans are two-phase: `POST .../replans` only *previews* a plan (no state change at all, not even a restaurant-revision bump); `POST .../replans/{id}/apply` is the only step that commits, and it needs its own idempotency key separate from the preview.
- An intervening restaurant-revision change between preview and apply invalidates the plan: `409 stale_plan`, changing nothing. Applying an already-applied plan under a different key is `409 plan_already_applied`; replaying the same successful key returns the original response with `200`.
- Planning has hard bounds: up to 6 tables, 4 declared pairs, 6 considered bookings; anything larger is `422 planning_limit` rather than attempting a bigger solve.
- Plan selection is a strict, ordered tie-break: (1) fewest bookings whose table set changes, (2) least total unused capacity across considered bookings, (3) lexicographically smallest option-rank vector in ascending reference order. Get the order of these three criteria exactly right: swapping two changes which plan is "correct."
- Diners' own cancellation cutoffs do **not** block an operator repair: a closure plan can move a booking a diner could no longer self-amend.
- Restaurant revision increments exactly once per successful plan *application* (not per moved booking, not on preview).
- Series amendment (`POST /series/{id}/amend`): `from_index` selects occurrences at-or-after that index, **excluding** already-cancelled and already-exception occurrences. `409 stale_revision` is checked before any occurrence's cutoff or booking validation. All-no-op or empty eligible sets must succeed without bumping any revision.
- Series amendments never mark exceptions (individual `PATCH` still does); a moved series occurrence from a seating repair keeps its existing exception flag, scheduled date and accepted terms.

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
# Tablekeeper — Stage 4: seating changes and recurring amendments

Extends all earlier stages, including stage-1 atomic reservation moves, stage-2 table
combinations and stage-3 policies and recurring agreements. All earlier requirements apply.

## Seating changes after a table closure

When a table becomes unavailable, a manager can review a proposed seating arrangement
before applying it. Customers must keep their booking times, party sizes and accepted terms.
No new screens are required. Existing availability, confirmation and lookup screens must
reflect an applied plan.

`POST /restaurants/{id}/replans` requires a manager and an idempotency key. Body:

```json
{"table_id": "t_2", "from": "2026-09-28T18:00:00+02:00",
 "to": "2026-09-28T23:00:00+02:00"}
```

The instants have explicit offsets and `from < to`; invalid interval is 422
`validation_failed`, unknown table 404. The proposed closure is the half-open interval
`[from,to)`. Consider every confirmed booking at this restaurant overlapping that interval.
Other bookings retain their assignments.
Planning must support up to 6 tables, 4 declared pairs and 6 considered bookings; larger
inputs may return 422 `planning_limit`. Each considered booking must retain its reference,
owner, party size, start, end and accepted terms. Assign it a single or a declared pair with
enough capacity under **its own accepted terms**, without conflicts with fixed bookings,
other assignments, previously applied closures or the proposed closure. Diners' cancellation
cutoffs do not prevent an operator repair. No booking may disappear or be cancelled.

Among feasible plans minimize, in order:

1. Number of bookings whose table set changes.
2. Total unused seats across all considered bookings (capacity minus party size).
3. The vector of option ranks in ascending reservation-reference order. Singles are ranked
   first in fixture order, then pairs in declared order, starting at 0.

Returns 201:

```json
{"plan_id": "opaque", "restaurant_revision": 4,
 "closure": {"table_id": "t_2", "from": "...", "to": "..."},
 "assignments": [{"reference": "ABC12345", "table_ids": ["t_1"], "changed": true}],
 "moved_count": 1, "unused_seats": 0}
```

Assignments include every considered booking in reference order. A restaurant revision starts
at 0 after reset and increments once for each successful new booking, real amendment,
cancellation, policy publication or plan application. No-op writes, failures, previews and
replays do not increment it. Preview stores only a plan: no closure, occupancy, reservation
revision or history changes. No feasible plan gives 409 `no_feasible_plan`, changing nothing.

`POST /restaurants/{id}/replans/{plan_id}/apply`, body `{}`, requires a manager and an
idempotency key. Return 201 with `{"plan_id": "...", "restaurant_revision": 5,
"reservations": [...]}`; reservations include every considered booking in reference order.
Unknown plan or one from another restaurant is 404. Any intervening restaurant revision
invalidates the plan: 409 `stale_plan`, changing nothing. A plan already applied under a
different key gives 409 `plan_already_applied`; replay of the successful key returns the
original response with 200, even after later changes. Application is atomic.

Application records the closure and all assignments together. Each moved booking increments
its revision once and gains one `reassigned` history entry with a `table_ids` change and
`plan_id`; accepted terms and times remain identical. Unmoved bookings gain nothing. The
restaurant revision increments once for the **whole plan**. Closures thereafter exclude
singles and pairs from availability and reject creates/amendments with 409 `table_unavailable`.
In explanations, `no_overlap` is false for a closure as for a conflicting booking.

Concurrent applications must not leave partially moved bookings. A closure at another
restaurant does not invalidate this plan.

## Amend recurring reservations

`POST /series/{series_id}/amend` is an owner-only idempotent write. Unknown or another owner's
series is 404; no token is 401. Body:

```json
{"expected_revision": 3, "from_index": 2, "local_time": "20:00"}
```

Revision must be a positive integer; from_index an integer in 0..count-1; local_time exactly
HH:MM in 00:00..23:59. Booleans are invalid integers. Invalid input gives 422
`validation_failed`; a mismatched series revision gives 409 `stale_revision` before any
occurrence's cutoff or booking validation. Unknown fields are ignored.

Consider indices at or after from_index, excluding cancelled occurrences and those marked
exception. Change their clock time on their original scheduled local dates, retaining each
reference, owner, party size and current table selection. A change with identical
resulting fields is a no-op and retains its terms. Each real change checks its old accepted
cutoff, then adopts the policy for its resulting start date, just like an individual PATCH.

The resulting occurrences must not conflict with unchanged occurrences, other bookings
or applied closures. On failure, histories, idempotency records and all revisions remain
unchanged. Non-occupancy errors take precedence in occurrence-index order; otherwise an
occupancy conflict returns `table_unavailable`.

On success return 201 with the current series response. Each changed occurrence gains one
ordinary changed history entry and one reservation revision. The series and restaurant
revisions each increase once for the entire operation if anything changed. Series amendments
do not mark exceptions. All-no-op or empty eligible sets succeed without changing revisions.
Replay returns the original response with 200 even after further edits or cancellations.

Seating repairs may move series occurrences. They preserve their exception flags, scheduled
dates, identities and accepted terms. Each affected series revision increases once per plan
application if at least one member moved.
Concurrent amendments from the same expected revision may not both make a real change.

A stage-4 service must accept exports produced by the same team's stages 1–3. These
operations must support imported series, including moved and cancelled occurrences.
Earlier booking and series receipts, histories and retries remain valid.
```
