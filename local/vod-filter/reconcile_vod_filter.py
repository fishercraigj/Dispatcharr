#!/usr/bin/env python3
"""
Reconcile Dispatcharr M3UVODCategoryRelation.enabled flags against
vod_filter.yaml. Dry-run by default; --apply to write.

Runs on the host (ubuntu); executes the actual ORM work inside the
dispatcharr container via `docker exec ... manage.py shell -c`.

Idempotent. Safe to re-run after every catalog refresh.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
YAML_PATH = HERE / "vod_filter.yaml"
SENTINEL = "===RECONCILER-OUTPUT==="


INNER_TEMPLATE = r'''
print({sentinel!r})
from apps.vod.models import M3UVODCategoryRelation

SPEC = {spec_json}
APPLY = {apply!r}

account_id = SPEC["account_id"]
buckets = {{"movie": SPEC["movies"], "series": SPEC["series"]}}

def _norm(s):
    # Provider data contains U+00A0 (NBSP) in some category names
    # (e.g. "VOD | MULTI-LANG 2020 AND BEYOND"). Normalize to a
    # regular space so the YAML can use plain ASCII spaces.
    return s.replace(" ", " ")

def should_keep(name, rules):
    n = _norm(name)
    if n in (_norm(x) for x in rules.get("explicit_keep") or []):
        return True
    for p in rules.get("keep_prefixes") or []:
        if n.startswith(_norm(p)):
            return True
    return False

qs = (M3UVODCategoryRelation.objects
      .filter(m3u_account_id=account_id)
      .select_related("category")
      .order_by("category__category_type", "category__name"))

if not qs.exists():
    print(f"ERROR: no M3UVODCategoryRelation rows for account_id={{account_id}}")
    raise SystemExit(2)

flips_on, flips_off = [], []
ok_on = ok_off = 0
for rel in qs:
    rules = buckets[rel.category.category_type]
    want = should_keep(rel.category.name, rules)
    if want == rel.enabled:
        if want: ok_on += 1
        else:    ok_off += 1
        continue
    rec = (rel.id, rel.category.category_type, rel.category.id, rel.category.name)
    (flips_on if want else flips_off).append(rec)

mode = "APPLY" if APPLY else "dry-run"
print("=" * 72)
print(f"  Account {{account_id}}   mode={{mode}}")
print("=" * 72)
total = qs.count()
print(f"  Total relations    : {{total}}")
print(f"  Already correct    : {{ok_on}} enabled, {{ok_off}} disabled")
print(f"  Will flip ON -> OFF: {{len(flips_off)}}")
print(f"  Will flip OFF -> ON: {{len(flips_on)}}")
post_on  = ok_on  + len(flips_on)
post_off = ok_off + len(flips_off)
print(f"  After this run     : {{post_on}} enabled, {{post_off}} disabled")
print()

def dump(title, rows):
    if not rows: return
    print(f"--- {{title}} ({{len(rows)}}) ---")
    for _, kind, cid, name in rows:
        print(f"  [{{kind:6}}] cat#{{cid:>4}}  {{name}}")
    print()

dump("WILL DISABLE", flips_off)
dump("WILL ENABLE",  flips_on)

if APPLY:
    off_ids = [r[0] for r in flips_off]
    on_ids  = [r[0] for r in flips_on]
    if off_ids:
        n = M3UVODCategoryRelation.objects.filter(id__in=off_ids).update(enabled=False)
        print(f"Disabled {{n}} relations.")
    if on_ids:
        n = M3UVODCategoryRelation.objects.filter(id__in=on_ids).update(enabled=True)
        print(f"Enabled  {{n}} relations.")
    if not (off_ids or on_ids):
        print("No changes (already in desired state).")
else:
    print("(dry-run; pass --apply to write)")
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="Actually write changes (default: dry-run).")
    ap.add_argument("--yaml", type=Path, default=YAML_PATH,
                    help=f"Spec file (default: {YAML_PATH})")
    args = ap.parse_args()

    with args.yaml.open() as f:
        spec = yaml.safe_load(f)

    inner = INNER_TEMPLATE.format(
        sentinel=SENTINEL,
        spec_json=json.dumps(spec),
        apply=args.apply,
    )

    proc = subprocess.run(
        ["docker", "exec", "-i", "dispatcharr",
         "python", "manage.py", "shell", "-c", inner],
        capture_output=True, text=True,
    )

    out = proc.stdout
    idx = out.find(SENTINEL)
    if idx == -1:
        # Inner script never ran (import/syntax error). Show everything.
        sys.stdout.write(out)
        sys.stderr.write(proc.stderr)
        sys.exit(proc.returncode or 1)

    sys.stdout.write(out[idx + len(SENTINEL):].lstrip("\n"))
    if proc.stderr.strip():
        sys.stderr.write(proc.stderr)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
