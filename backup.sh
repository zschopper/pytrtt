#!/usr/bin/env bash

set -euo pipefail

# Timestamp in YYYYMMDD-HHMMSS format
datetime=$(date '+%Y%m%d-%H%M%S')

# Get repository name from the origin URL
repo_path=$(git config --get remote.origin.url)
git_name=$(basename "$repo_path")
repo=${git_name%.git}

archivename="${datetime}--${repo}.tgz"

# Save staged file names to a list.
# Disable Git path quoting so UTF-8 file names are written as-is.
git -c core.quotePath=false diff --cached --name-only > file_list.txt

# Create a gzip-compressed tar archive while preserving directory structure.
tar -czf "./${archivename}" -T file_list.txt

# Uncomment if you want to remove the temporary file afterward:
# rm -f file_list.txt
