# [Bug]: Xtream API ignores `M3UVODCategoryRelation.enabled` flag

## Summary

The Xtream Codes API endpoints under `apps/output/views.py` do not honor the
`enabled` flag on `M3UVODCategoryRelation`, so a category disabled via the
web UI (or directly in the DB) still appears in the API output and its
movies/series still stream. The model docstring and `help_text` both say this
flag is meant to deactivate the category for the M3U account; the API simply
never reads it.

## Reproduce

1. Have at least one XC M3U account with VOD enabled and some categories synced.
2. In the Dispatcharr UI, disable any VOD category for that account (or set
   `M3UVODCategoryRelation.enabled = False` directly).
3. Log into the Xtream API as a Dispatcharr user that's allowed to reach VOD
   and call any of these:
   - `action=get_vod_categories`
   - `action=get_series_categories`
   - `action=get_vod_streams`
   - `action=get_series`
4. Observe that the disabled category and all of its movies/series are still
   returned.

## Expected

Per the model definition in `apps/vod/models.py`:

```python
class M3UVODCategoryRelation(models.Model):
    ...
    enabled = models.BooleanField(
        default=False,
        help_text="Set to false to deactivate this category for the M3U account",
    )
```

…disabling the relation should hide the category and its streams from the
Xtream API for that account.

## Actual

The four Xtream VOD endpoints in `apps/output/views.py` filter only on
`m3u_account__is_active=True` and never reference the `enabled` flag, so the
toggle is purely cosmetic at the API layer.

Affected functions (line numbers against current `main`,
[`0c36602`](https://github.com/Dispatcharr/Dispatcharr/blob/main/apps/output/views.py)):

| Function | Approx. line | Returns |
|---|---:|---|
| `xc_get_vod_categories` | 2549 | All movie categories from active accounts |
| `xc_get_vod_streams`    | 2576 | All movies for those categories |
| `xc_get_series_categories` | 2660 | All series categories from active accounts |
| `xc_get_series`         | 2687 | All series for those categories |

## Impact

For installs with large multilingual catalogs, this means the only way to
restrict the VOD client view is per-device client-side hiding. On a single
229-category catalog the API was returning ~150k movies / ~47k series until
this was patched locally; the desired English-only slice was a small fraction
of that.

## Proposed fix

PR follows: add `m3u_relations__enabled=True` to the category queries and
`category__m3u_relations__enabled=True` (correlated to the streaming
account) to the stream queries. ~12 lines including the `F` import. No
migration needed. No public API change beyond honoring the existing flag.
