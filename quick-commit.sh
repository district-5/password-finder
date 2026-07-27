#!/bin/bash
set -e

# Check remote for changes and block if conflicts exist
current_branch=$(git symbolic-ref --short HEAD)
git fetch origin "$current_branch" 2>/dev/null || true

if git rev-parse --verify "origin/$current_branch" >/dev/null 2>&1; then
  remote_ahead=$(git rev-list "HEAD..origin/$current_branch" --count)
  if [ "$remote_ahead" -gt 0 ]; then
    echo "Remote has $remote_ahead new commit(s). Checking for conflicts..."
    merge_base=$(git merge-base HEAD "origin/$current_branch")
    conflict_check=$(git merge-tree "$merge_base" HEAD "origin/$current_branch")
    if echo "$conflict_check" | grep -q "^<<<<<<"; then
      echo "Error: merge conflicts detected with remote. Resolve before committing."
      exit 1
    fi
    echo "No conflicts. Proceeding."
  fi
fi

git add -A

# List the full path of every changed file
folder_list=$(git diff --cached --name-only | sort -u | sed 's/^/- /')

git commit -m "Quick commit, read more..." -m "Changed folders/files:
$folder_list"
git push
