#!/usr/bin/env python3
"""Fix the project: replace data_store.py with clean version and clean up unwanted files."""

import os
import shutil
from pathlib import Path

# Get the current directory
project_dir = Path(".")

# 1. Copy data_store_new.py to data_store.py
print("✅ Replacing data_store.py with clean PostgreSQL version...")
if (project_dir / "data_store_new.py").exists():
    shutil.copy2("data_store_new.py", "data_store.py")
    print("   ✓ data_store.py updated")
    # Delete data_store_new.py
    os.remove("data_store_new.py")
    print("   ✓ data_store_new.py deleted")

# 2. Delete unwanted .md files (keep only README.md)
unwanted_md_files = [
    "START_HERE.md",
    "MIGRATION_GUIDE.md",
    "DEPLOYMENT_NOTES.md",
    "MIGRATION_SUMMARY.md",
    "VERIFICATION_CHECKLIST.md",
    "DOCUMENTATION_INDEX.md",
    "PROJECT_COMPLETE.md",
    "TODO.md",
    "suggestions.md"
]

print("\n✅ Removing unwanted .md files...")
for filename in unwanted_md_files:
    filepath = project_dir / filename
    if filepath.exists():
        os.remove(filepath)
        print(f"   ✓ Deleted {filename}")

# 3. Delete MongoDB-related files
print("\n✅ Removing MongoDB-related files...")
mongo_files = [
    "database/mongo_indexes.py",
    "database/mongo_connection.py",
    "database/__init__.py"
]

for filename in mongo_files:
    filepath = project_dir / filename
    if filepath.exists():
        os.remove(filepath)
        print(f"   ✓ Deleted {filename}")

# Try to remove __pycache__ in database folder
pycache_dir = project_dir / "database/__pycache__"
if pycache_dir.exists():
    shutil.rmtree(pycache_dir)
    print(f"   ✓ Deleted database/__pycache__/")

# Try to remove the database folder itself if empty
db_dir = project_dir / "database"
if db_dir.exists() and len(list(db_dir.iterdir())) == 0:
    os.rmdir(db_dir)
    print(f"   ✓ Deleted empty database/ folder")

# Delete __pycache__ in current dir
pycache_cur = project_dir / "__pycache__"
if pycache_cur.exists():
    shutil.rmtree(pycache_cur)
    print(f"   ✓ Deleted __pycache__/ in current directory")

print("\n✅ Cleanup Complete!")
print("\nRemaining files in project:")
for f in sorted(project_dir.glob("*")):
    if f.is_file():
        print(f"   - {f.name}")
    elif f.is_dir() and f.name not in ["__pycache__", ".git"]:
        print(f"   📁 {f.name}/")
