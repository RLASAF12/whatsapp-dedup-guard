import argparse
import os
import sys
from datetime import datetime

# --- Constants ---
HEADER_PREFIXES = {
    "MESSAGE_ID": "Message ID:",
    "SAVED_AT": "Saved At:",
    "AGENT_ROUTE": "Agent Route:",
    "DUPLICATE_STATUS": "Duplicate:"
}
# ISO 8601 format with milliseconds and 'Z' for UTC
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

# --- Data Structures ---
class FileInfo:
    """
    Represents parsed information from a WhatsApp bot inbox file.
    Stores the extracted header data along with file path and filename.
    """
    def __init__(self, message_id: str, saved_at: datetime, agent_route: str, filepath: str):
        self.message_id = message_id
        self.saved_at = saved_at  # Stored as a datetime object for easy sorting
        self.agent_route = agent_route
        self.filepath = filepath
        self.filename = os.path.basename(filepath)

    def __repr__(self):
        """Provides a developer-friendly string representation."""
        return (f"FileInfo(id='{self.message_id}', saved_at='{self.saved_at.isoformat()}', "
                f"route='{self.agent_route}', path='{self.filepath}')")

    def __lt__(self, other):
        """
        Enables sorting FileInfo objects primarily by 'saved_at' timestamp.
        This is crucial for identifying the 'original' file in a duplicate group.
        """
        return self.saved_at < other.saved_at

# --- Helper Functions ---

def detect_llm_source(filename: str) -> str:
    """
    Detects the LLM source based on predefined keywords found in the filename.
    Keywords are case-insensitive.
    """
    filename_lower = filename.lower()
    if "gemini" in filename_lower:
        return "gemini"
    if "gpt" in filename_lower:
        return "gpt"
    if "openai" in filename_lower:
        return "openai"
    if "local" in filename_lower:
        return "local"
    return "unknown"

def parse_file(filepath: str) -> FileInfo | None:
    """
    Parses the header of a markdown file to extract Message ID, Saved At, and Agent Route.
    It reads only the first few lines to optimize performance.
    Returns a FileInfo object if successful, otherwise None.
    """
    message_id = None
    saved_at_str = None
    agent_route = None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Read only the first few lines, as headers are expected at the top
            for line_num, line in enumerate(f):
                if line_num >= 15: # Headers should typically be within the first 5 lines
                    break
                line = line.strip()
                if line.startswith(HEADER_PREFIXES["MESSAGE_ID"]):
                    message_id = line.split(HEADER_PREFIXES["MESSAGE_ID"], 1)[1].strip()
                elif line.startswith(HEADER_PREFIXES["SAVED_AT"]):
                    saved_at_str = line.split(HEADER_PREFIXES["SAVED_AT"], 1)[1].strip()
                elif line.startswith(HEADER_PREFIXES["AGENT_ROUTE"]):
                    agent_route = line.split(HEADER_PREFIXES["AGENT_ROUTE"], 1)[1].strip()

                # If all required headers are found, no need to read further
                if message_id and saved_at_str and agent_route:
                    break

        # Check if all necessary header information was extracted
        if not (message_id and saved_at_str and agent_route):
            # print(f"Warning: Could not parse all header info from {filepath}", file=sys.stderr)
            return None

        # Convert the 'Saved At' string to a datetime object
        try:
            saved_at = datetime.strptime(saved_at_str, DATETIME_FORMAT)
        except ValueError:
            print(f"Error: Invalid 'Saved At' format in {filepath}: '{saved_at_str}'. Expected '{DATETIME_FORMAT}'", file=sys.stderr)
            return None

        return FileInfo(message_id, saved_at, agent_route, filepath)

    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error parsing file {filepath}: {e}", file=sys.stderr)
        return None

def find_all_files(directory: str) -> list[FileInfo]:
    """
    Walks the given directory, finds all .md files, and parses their headers.
    Returns a list of FileInfo objects for all successfully parsed files.
    Exits with code 2 if the directory is not found.
    """
    if not os.path.isdir(directory):
        print(f"Error: Directory not found: {directory}", file=sys.stderr)
        sys.exit(2)

    all_file_infos = []
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith(".md"):
                filepath = os.path.join(root, filename)
                file_info = parse_file(filepath)
                if file_info: # Only add successfully parsed files
                    all_file_infos.append(file_info)
    return all_file_infos

def group_by_message_id(file_infos: list[FileInfo]) -> dict[str, list[FileInfo]]:
    """
    Groups FileInfo objects by their Message ID.
    Each list of FileInfo objects within a group is sorted by 'saved_at' (earliest first).
    """
    grouped_files = {}
    for info in file_infos:
        grouped_files.setdefault(info.message_id, []).append(info)

    # Sort each group by saved_at to ensure the earliest file is always first
    for message_id in grouped_files:
        grouped_files[message_id].sort() # Uses FileInfo.__lt__ for sorting
    return grouped_files

# --- CLI Commands ---

def scan_command(args):
    """
    Scans the specified directory for duplicate Message IDs.
    Prints a summary of any duplicates found.
    Exits with code 0 if no duplicates, 1 if duplicates are found.
    """
    print(f"Scanning directory: {args.directory}")
    file_infos = find_all_files(args.directory)
    grouped_files = group_by_message_id(file_infos)

    duplicate_groups = {mid: files for mid, files in grouped_files.items() if len(files) > 1}

    if duplicate_groups:
        print("\n--- DUPLICATES FOUND ---")
        for message_id, files in duplicate_groups.items():
            print(f"Message ID: {message_id} ({len(files)} instances)")
            for file_info in files:
                print(f"  - {file_info.filepath} (Saved At: {file_info.saved_at.isoformat()})")
        print(f"\nTotal duplicate groups: {len(duplicate_groups)}")
        print("Please run 'report' for more details or 'mark' to tag duplicates.")
        sys.exit(1) # Exit code 1 indicates duplicates were found
    else:
        print("No duplicate Message IDs found. Directory is clean.")
        sys.exit(0) # Exit code 0 indicates no duplicates

def report_command(args):
    """
    Generates a detailed report of all duplicate Message ID groups.
    For each group, it lists the original and duplicate files, sorted by 'Saved At',
    and includes LLM source detection.
    """
    print(f"Generating report for directory: {args.directory}")
    file_infos = find_all_files(args.directory)
    grouped_files = group_by_message_id(file_infos)

    duplicate_groups = {mid: files for mid, files in grouped_files.items() if len(files) > 1}

    if not duplicate_groups:
        print("No duplicate Message IDs found. Nothing to report.")
        sys.exit(0)

    print("\n--- DUPLICATE REPORT ---")
    for message_id, files in duplicate_groups.items():
        print(f"\nMessage ID: {message_id}")
        print(f"  Total instances: {len(files)}")
        for i, file_info in enumerate(files):
            status = "ORIGINAL" if i == 0 else "DUPLICATE" # Earliest file is the original
            llm_source = detect_llm_source(file_info.filename)
            print(f"  [{status}]")
            print(f"    File: {file_info.filepath}")
            print(f"    Saved At: {file_info.saved_at.isoformat()}")
            print(f"    Agent Route: {file_info.agent_route}")
            print(f"    LLM Source: {llm_source}")
    sys.exit(0)

def mark_command(args):
    """
    Adds the line "Duplicate: true" after the "Agent Route:" line in all but the
    earliest file in each duplicate group.
    Supports a --dry-run mode to preview changes without modifying files.
    Exits with code 2 on file modification errors.
    """
    print(f"Marking duplicates in directory: {args.directory}")
    if args.dry_run:
        print("--- DRY RUN MODE: No files will be modified ---")

    file_infos = find_all_files(args.directory)
    grouped_files = group_by_message_id(file_infos)

    duplicate_groups = {mid: files for mid, files in grouped_files.items() if len(files) > 1}

    if not duplicate_groups:
        print("No duplicate Message IDs found. Nothing to mark.")
        sys.exit(0)

    marked_count = 0
    for message_id, files in duplicate_groups.items():
        # The first file in the sorted list is considered the original
        original_file = files[0]
        duplicates_to_mark = files[1:]

        print(f"\nProcessing Message ID: {message_id}")
        print(f"  Original (earliest): {original_file.filepath} (Saved At: {original_file.saved_at.isoformat()})")

        for dup_file_info in duplicates_to_mark:
            print(f"  Marking duplicate: {dup_file_info.filepath} (Saved At: {dup_file_info.saved_at.isoformat()})")
            if not args.dry_run:
                try:
                    with open(dup_file_info.filepath, 'r', encoding='utf-8') as f:
                        lines = f.readlines()

                    modified_lines = []
                    inserted = False
                    duplicate_tag_already_present = False

                    for line in lines:
                        modified_lines.append(line)
                        if line.strip().startswith(HEADER_PREFIXES["AGENT_ROUTE"]):
                            # Insert "Duplicate: true" after "Agent Route:" line
                            # only if it hasn't been inserted yet and isn't already present
                            if not inserted and not duplicate_tag_already_present:
                                modified_lines.append(f"{HEADER_PREFIXES['DUPLICATE_STATUS']} true\n")
                                inserted = True
                        elif line.strip().startswith(HEADER_PREFIXES["DUPLICATE_STATUS"]):
                            # If a duplicate tag is already present, we don't need to insert a new one
                            duplicate_tag_already_present = True

                    if not inserted and not duplicate_tag_already_present:
                        print(f"Warning: Could not find '{HEADER_PREFIXES['AGENT_ROUTE']}' in {dup_file_info.filepath} "
                              f"to insert duplicate status, and no existing '{HEADER_PREFIXES['DUPLICATE_STATUS']}' tag was found. Skipping.", file=sys.stderr)
                        continue # Skip this file if header structure is unexpected or tag already exists

                    if inserted: # Only count if we actually inserted a new tag
                        with open(dup_file_info.filepath, 'w', encoding='utf-8') as f:
                            f.writelines(modified_lines)
                        marked_count += 1
                    else:
                        print(f"  Note: '{dup_file_info.filepath}' already contains a '{HEADER_PREFIXES['DUPLICATE_STATUS']}' tag. Skipping modification.", file=sys.stderr)

                except Exception as e:
                    print(f"Error modifying file {dup_file_info.filepath}: {e}", file=sys.stderr)
                    sys.exit(2) # Exit with error code 2 on I/O or other modification issues
            else:
                # In dry-run, we still count files that *would* be marked
                # We need to simulate the check for existing tag to be accurate
                try:
                    with open(dup_file_info.filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if f"{HEADER_PREFIXES['AGENT_ROUTE']}" in content and f"{HEADER_PREFIXES['DUPLICATE_STATUS']}" not in content:
                            marked_count += 1
                        elif f"{HEADER_PREFIXES['DUPLICATE_STATUS']}" in content:
                            print(f"  Note (dry-run): '{dup_file_info.filepath}' already contains a '{HEADER_PREFIXES['DUPLICATE_STATUS']}' tag. Would skip modification.", file=sys.stderr)
                        else:
                            print(f"Warning (dry-run): Could not find '{HEADER_PREFIXES['AGENT_ROUTE']}' in {dup_file_info.filepath} to insert duplicate status. Would skip.", file=sys.stderr)
                except Exception as e:
                    print(f"Error reading file {dup_file_info.filepath} during dry-run: {e}", file=sys.stderr)
                    sys.exit(2)


    print(f"\n--- Mark Summary ---")
    print(f"Total duplicate files identified for marking: {marked_count}")
    if args.dry_run:
        print("DRY RUN: No files were actually modified.")
    else:
        print(f"Successfully marked {marked_count} files.")
    sys.exit(0)

def stats_command(args):
    """
    Calculates and prints statistics about the files in the directory,
    including total files, unique Message IDs, duplicate file count, and duplicate rate.
    """
    print(f"Generating statistics for directory: {args.directory}")
    file_infos = find_all_files(args.directory)
    grouped_files = group_by_message_id(file_infos)

    total_files = len(file_infos)
    unique_ids = len(grouped_files)
    duplicate_files_count = 0 # This counts files that are *additional* instances of a message ID

    for message_id, files in grouped_files.items():
        if len(files) > 1:
            duplicate_files_count += (len(files) - 1) # Subtract 1 for the original file

    duplicate_rate_percentage = 0.0
    if total_files > 0:
        duplicate_rate_percentage = (duplicate_files_count / total_files) * 100

    print("\n--- Statistics ---")
    print(f"Total files processed: {total_files}")
    print(f"Unique Message IDs: {unique_ids}")
    print(f"Duplicate files found (beyond the first instance): {duplicate_files_count}")
    print(f"Duplicate rate: {duplicate_rate_percentage:.2f}%")
    sys.exit(0)

# --- Main CLI Setup ---

def main():
    """
    Main function to set up the argparse CLI and dispatch commands.
    Handles top-level error catching for unexpected issues.
    """
    parser = argparse.ArgumentParser(
        prog="whatsapp_dedup_guard.py",
        description="WhatsApp Dedup Guard: Detects and manages duplicate WhatsApp bot inbox files.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    # Setup subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Scan command parser
    scan_parser = subparsers.add_parser(
        "scan",
        help="Finds all .md files, groups by Message ID, prints duplicates, exits 1 if any found.",
        description="Scans the specified directory for duplicate WhatsApp bot inbox files.\n"
                    "Exits with code 0 if no duplicates are found, 1 if duplicates are present."
    )
    scan_parser.add_argument(
        "directory",
        help="The directory to scan for .md files."
    )
    scan_parser.set_defaults(func=scan_command)

    # Report command parser
    report_parser = subparsers.add_parser(
        "report",
        help="Provides a detailed output of each duplicate group.",
        description="Generates a detailed report for all duplicate Message ID groups found in the directory.\n"
                    "Shows ORIGINAL vs DUPLICATE files, sorted by 'Saved At', and includes LLM source detection."
    )
    report_parser.add_argument(
        "directory",
        help="The directory to report on."
    )
    report_parser.set_defaults(func=report_command)

    # Mark command parser
    mark_parser = subparsers.add_parser(
        "mark",
        help="Adds 'Duplicate: true' to all but the earliest file in each duplicate group.",
        description="Modifies duplicate files by adding 'Duplicate: true' after the 'Agent Route:' line.\n"
                    "The earliest saved file in each group is considered the original and is not marked."
    )
    mark_parser.add_argument(
        "directory",
        help="The directory containing files to mark."
    )
    mark_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without actually modifying any files."
    )
    mark_parser.set_defaults(func=mark_command)

    # Stats command parser
    stats_parser = subparsers.add_parser(
        "stats",
        help="Prints statistics about files, unique IDs, and duplicate counts/rates.",
        description="Calculates and displays statistics for the specified directory, including:\n"
                    "- Total files processed\n"
                    "- Total unique Message IDs\n"
                    "- Count of duplicate files (files beyond the first instance in a group)\n"
                    "- Duplicate rate percentage"
    )
    stats_parser.add_argument(
        "directory",
        help="The directory to gather statistics from."
    )
    stats_parser.set_defaults(func=stats_command)

    args = parser.parse_args()

    # If no subcommand is provided, print help and exit
    if not args.command:
        parser.print_help()
        sys.exit(2)

    # Execute the function associated with the chosen subcommand
    try:
        args.func(args)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(2) # General error exit code

if __name__ == "__main__":
    main()