# fix(output): honor `M3UVODCategoryRelation.enabled` in Xtream VOD endpoints

Closes #<issue-number>

## Problem

The four Xtream VOD endpoints in `apps/output/views.py`
(`xc_get_vod_categories`, `xc_get_vod_streams`, `xc_get_series_categories`,
`xc_get_series`) filter only on `m3u_account__is_active=True` and never
reference `M3UVODCategoryRelation.enabled`. The model's `help_text` says
this flag is meant to deactivate the category for the M3U account, and the
UI lets users toggle it, but the API has been silently ignoring it. See
the linked issue for repro.

## Fix

Surgical addition to two category queries and two stream queries:

- **Category endpoints** (`xc_get_vod_categories`, `xc_get_series_categories`)
  add `m3u_relations__enabled=True` plus a redundant
  `m3u_relations__m3u_account__is_active=True`. The `.distinct()` already
  on the queryset prevents row multiplication when more than one
  enabled-relation joins to the same category.

- **Stream endpoints** (`xc_get_vod_streams`, `xc_get_series`) add a
  correlated filter:
  ```python
  category__m3u_relations__enabled=True,
  category__m3u_relations__m3u_account=F('m3u_account'),
  ```
  The `F('m3u_account')` correlation matters when more than one account
  syncs the same `VODCategory` row: it ensures a stream is only included
  when *its own* account has the category enabled — disabling a category
  on account A doesn't accidentally hide streams that account B serves
  from the same category, and an enabled stream from B doesn't leak when
  A has the category disabled.

Total diff: ~12 lines added including the `F` import. No migration. No
new fields. No change to any external contract beyond honoring the
existing flag.

## Before / after

Tested on a single production-ish XC account with 159 movie categories
+ 68 series categories synced. After disabling 121 movie + 64 series
relations via the UI:

| Endpoint | Before | After |
|---|---:|---:|
| `get_vod_categories`     | 158     | 38    |
| `get_series_categories`  | 67      | 4     |
| `get_vod_streams`        | 149,837 | 32,409 |
| `get_series`             | 47,121  | 15,020 |

(The "before" numbers reflect the DB after the disables were applied, with
the un-patched code still serving everything — proving the flag was being
ignored, not just that nothing was disabled.)

## Test plan

- [x] Disable a mix of categories per type on an XC account; verify all four
      endpoints respect the flag.
- [x] Verify `Xtream` get_vod_streams returns no streams from a disabled
      category (sampled by `category_id`).
- [x] Spot-check that streams from another (still-enabled) account are
      unaffected when a category is disabled on the first account — this
      is what the `F('m3u_account')` correlation guards.
- [x] Re-enable a category and confirm it returns in the next API call
      (no caching surprises).
- [ ] *(maintainer please verify)* Behavior under the explicit-VOD-permission
      path in `xc_get_vod_streams` / `xc_get_series` — I tested with the
      "all authenticated users" branch.

## Notes for reviewers

- The four affected functions were refactored for performance on
  `2026-05-30` (157c87ce4d / effa03b2a5) without touching this code path,
  so the regression is pre-existing rather than newly introduced.
- The patch keeps the existing perf-optimized structure: filters are added
  to the queryset at the source, not as a post-fetch loop, so the DB does
  the work.
- No changes to migrations or admin. The flag has been settable in the DB
  and UI for some time; this PR just makes the API read it.
