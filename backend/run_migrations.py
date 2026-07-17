#!/usr/bin/env python3
"""
run_migrations.py — Execute all database migrations in order.

Runs each migration script in backend/migrations/ sequentially.
Safe to re-run: all migrations are idempotent.

Usage:
    cd backend
    python3 run_migrations.py
    python3 run_migrations.py --only 001   # run only migration 001
    python3 run_migrations.py --dry-run    # show what would run
"""

import argparse
import asyncio
import importlib.util
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")


def load_migration(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def main(only: str = None, dry_run: bool = False):
    migrations_dir = ROOT / "migrations"
    migration_files = sorted(
        f for f in migrations_dir.glob("0*.py")
        if f.name != "__init__.py"
    )

    if not migration_files:
        print("No migration files found in backend/migrations/")
        return

    print(f"Found {len(migration_files)} migration(s):\n")

    for mf in migration_files:
        num = mf.stem.split("_")[0]

        # Filter by --only flag
        if only and not mf.stem.startswith(only):
            print(f"  ⏭  [{mf.name}] — skipped (--only {only})")
            continue

        print(f"  ▶  Running [{mf.name}]...")

        if dry_run:
            print(f"     [DRY RUN] would execute {mf.name}")
            continue

        try:
            mod = load_migration(mf)
            if hasattr(mod, "run"):
                await mod.run()
            elif hasattr(mod, "main"):
                # Support sync main() too
                result = mod.main()
                if asyncio.iscoroutine(result):
                    await result
            else:
                print(f"     ⚠️  No run() or main() found in {mf.name} — skipping")
                continue
            print(f"     ✅ [{mf.name}] complete\n")
        except Exception as e:
            print(f"     ❌ [{mf.name}] FAILED: {e}")
            sys.exit(1)

    print("\n✅ All migrations complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument("--only", type=str, default=None,
                        help="Run only migrations starting with this prefix (e.g. '001')")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would run without executing")
    args = parser.parse_args()
    asyncio.run(main(only=args.only, dry_run=args.dry_run))
