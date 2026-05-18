#!/bin/bash

# Configuration
DIR="${1:-.}"                    # Directory to process (default: current directory)
HEAD_LINES="${2:-10}"            # Number of lines from head (default: 10)
TAIL_LINES="${3:-10}"            # Number of lines from tail (default: 10)

# Loop through each file in the directory
for file in "$DIR"/*; do
    # Skip if not a regular file
    if [ ! -f "$file" ]; then
        continue
    fi
    
    # Print file separator and name
    echo "================================"
    echo "File: $file"
    echo "================================"
    
    # Get total line count
    total_lines=$(wc -l < "$file")
    
    # If file is small enough, just display it all
    if [ "$total_lines" -le $((HEAD_LINES + TAIL_LINES)) ]; then
        cat "$file"
    else
        # Display head
        head -n "$HEAD_LINES" "$file"
        echo "..."
        # Display tail
        tail -n "$TAIL_LINES" "$file"
    fi
    
    echo ""
done