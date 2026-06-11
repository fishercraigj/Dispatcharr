# VOD-filter tooling (LOCAL — not for upstream merge)

Companion tooling for the patch in commit `fix(output): honor
M3UVODCategoryRelation.enabled in Xtream VOD endpoints`. These files
live on the parent branch for versioning only; the upstream PR is
filed from a tree that contains *just* the patch commit.

## Files

| File | Role |
|---|---|
| `vod_filter.yaml` | Keep-rule spec: `keep_prefixes` + `explicit_keep` per category type. |
| `reconcile_vod_filter.py` | Host-side reconciler. Reads the YAML, connects via `docker exec dispatcharr python manage.py shell`, flips `M3UVODCategoryRelation.enabled` to match. Dry-run by default; `--apply` to write. Idempotent. |
| `UPSTREAM-ISSUE.md` | Draft bug report for github.com/Dispatcharr/Dispatcharr. |
| `UPSTREAM-PR.md` | Draft PR body for the same. |

## Deploy (Craig's arr-stack)

These files are tracked here for history; the *running* copies live in
`~/arr-stack/dispatcharr/` on the server, with a systemd timer
(`reconcile-vod-filter.timer`, hourly) invoking the reconciler.
See `~/arr-stack/DISPATCHARR-SETUP.md` for the full picture.
