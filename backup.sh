#!/bin/bash

# Configuration - use absolute paths to avoid errors
PROJECT_DIR="$(pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"
# --- MODIFIED LINE ---
# Construct backup root relative to the parent directory of the project
BACKUP_ROOT="$(dirname "$PROJECT_DIR")/backups/$PROJECT_NAME"
# --- END MODIFIED LINE ---
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"
MASTER_LOG="$BACKUP_ROOT/backup_history.log"

# Debug information
echo "Project name detected as: $PROJECT_NAME"
echo "Backing up from directory: $PROJECT_DIR"
# Calculate relative backup path for user clarity
RELATIVE_BACKUP_ROOT="../backups/$PROJECT_NAME"
echo "Backing up TO directory structure like: $RELATIVE_BACKUP_ROOT"
echo "Actual backup root: $BACKUP_ROOT"
echo "Number of files to backup: $(find "$PROJECT_DIR" -type f | wc -l)"

# Ensure backup root exists
mkdir -p "$BACKUP_ROOT"

# Create the timestamped backup directory within the new root
mkdir -p "$BACKUP_DIR"

# Copy the project with permissions preserved
echo "Creating directory backup..."
# Use rsync for potentially better handling and future options (like exclude)
rsync -a --delete "$PROJECT_DIR/" "$BACKUP_DIR/"
# Alternative using cp: cp -rp "$PROJECT_DIR"/. "$BACKUP_DIR/"

# Verify the backup (using find to count files, might differ slightly from rsync count)
ORIGINAL_FILE_COUNT=$(find "$PROJECT_DIR" -type f | wc -l)
BACKUP_FILE_COUNT=$(find "$BACKUP_DIR" -type f | wc -l)
echo "Original files: $ORIGINAL_FILE_COUNT"
echo "Backed up files: $BACKUP_FILE_COUNT"

# Simple check, rsync might skip empty dirs etc. Focus on command success.
if [ $? -ne 0 ]; then
  echo "ERROR: Backup copy/rsync command failed!"
  exit 1
fi
# Relaxing the strict file count check as it can be brittle
# if [ "$BACKUP_FILE_COUNT" -lt "$ORIGINAL_FILE_COUNT" ]; then
#   echo "WARNING: Backup file count seems lower than original. Check backup integrity."
# fi

# Create a compressed archive for long-term storage
# The archive is placed in BACKUP_ROOT (e.g., ../backups/simple_rl/)
ARCHIVE_FILENAME="$BACKUP_ROOT/${PROJECT_NAME}_$TIMESTAMP.tar.gz"
echo "Creating compressed archive at $ARCHIVE_FILENAME ..."
tar -czvf "$ARCHIVE_FILENAME" -C "$(dirname "$PROJECT_DIR")" "$(basename "$PROJECT_DIR")" > /dev/null 2>&1

# Verify the archive creation
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create tar archive!"
    # Consider cleanup? rm -f "$ARCHIVE_FILENAME"
    exit 1
fi
echo "Verifying archive content listing..."
ARCHIVE_FILE_COUNT=$(tar -tvf "$ARCHIVE_FILENAME" | wc -l)
# Note: tar lists directories too, so count isn't directly comparable to find -type f
echo "Entries listed in archive: $ARCHIVE_FILE_COUNT"


# Prompt for backup notes
echo "Enter notes for this backup (press Ctrl+D when finished):"
NOTES=$(cat)

# Save notes to timestamped backup directory
echo "$NOTES" > "$BACKUP_DIR/BACKUP_NOTES.txt"

# Append to master log in the main backup root
echo "=== BACKUP: $TIMESTAMP ===" >> "$MASTER_LOG"
echo "Source: $PROJECT_DIR" >> "$MASTER_LOG"
echo "Directory Backup: $BACKUP_DIR" >> "$MASTER_LOG"
echo "Archive: $ARCHIVE_FILENAME" >> "$MASTER_LOG"
echo "Original files (find): $ORIGINAL_FILE_COUNT" >> "$MASTER_LOG"
echo "Backed up files (find): $BACKUP_FILE_COUNT" >> "$MASTER_LOG"
echo "Archive entries (tar): $ARCHIVE_FILE_COUNT" >> "$MASTER_LOG"
echo "Notes:" >> "$MASTER_LOG"
echo "$NOTES" >> "$MASTER_LOG"
echo "=========================================" >> "$MASTER_LOG"
echo "" >> "$MASTER_LOG"

echo "Backup complete!"
echo "Directory backup created at: $BACKUP_DIR"
echo "Compressed archive created at: $ARCHIVE_FILENAME"
echo "Details logged in: $MASTER_LOG"

exit 0
