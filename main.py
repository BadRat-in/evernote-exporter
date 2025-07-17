import json
import base64
import argparse
import mimetypes
import urllib.parse
from pathlib import Path
import xml.etree.ElementTree as ET

from gdrive import upload_directory, authenticate_drive


def load_extraction_log(log_file: Path) -> dict:
    """
    Load the extraction log from a JSON file.
    If the log file doesn't exist, create an empty one.

    Args:
        log_file (Path): Path to the log file.

    Returns:
        dict: Parsed log content.
    """
    if not log_file.exists():
        log_file.write_text("{}")
        return {}

    try:
        return json.loads(log_file.read_text())
    except Exception:
        return {}


def list_enex_files(input_dir: Path) -> list[Path]:
    """
    List all .enex files in the input directory.

    Args:
        input_dir (Path): Directory to search for .enex files.

    Returns:
        list[Path]: List of .enex files.
    """
    return [f for f in input_dir.iterdir() if f.suffix.lower() == ".enex"]


def process_enex_file(file: Path, output_dir: Path, logs: dict):
    """
    Process a single ENEX file and extract its notes.

    Args:
        file (Path): Path to the ENEX file.
        output_dir (Path): Directory to store extracted notes.
        logs (dict): Log dictionary to store processing metadata.
    """
    notebook_name = file.stem
    logs[notebook_name] = []

    try:
        tree = ET.parse(file)
        notes = tree.getroot().findall("note")
    except Exception as e:
        logs[notebook_name].append({
            "file": file.name, "error": str(e), "notebook": notebook_name
        })
        return

    for note in notes:
        process_note(note, notebook_name, file, output_dir, logs)


def process_note(note, notebook_name, file, output_dir, logs):
    """
    Process a single note: extract text and resources.

    Args:
        note (Element): XML note element.
        notebook_name (str): Name of the notebook.
        file (Path): Source ENEX file.
        output_dir (Path): Target output directory.
        logs (dict): Log dictionary.
    """
    title = note.findtext("title")
    if not title:
        return

    # Encode the title to make it safe for the filesystem
    # title = urllib.parse.quote_plus(title).replace("+", " ")
    title = title.replace("/", "-").replace("--", "-")

    resources = note.findall("resource")
    content_element = note.find("content")
    text_content = None

    if content_element is not None and content_element.text is not None:
        try:
            content_root = ET.fromstring(content_element.text.strip())
            text_content = "\n".join(content_root.itertext()).strip()
        except ET.ParseError:
            pass

    # If there are resources, create a subfolder for the note
    if len(resources) > 0 and text_content:
        note_dir = output_dir / notebook_name / title
    else:
        note_dir = output_dir / notebook_name

    note_dir.mkdir(parents=True, exist_ok=True)

    if resources:
        handle_resources(resources, note_dir, title, file, notebook_name, logs)

    handle_text_content(text_content, note_dir, title, file, notebook_name, logs)


def handle_text_content(text_content, note_dir, title, file, notebook_name, logs):
    """
    Extract and save the plain text content from a note.

    Args:
        text_content (Text): XML note text content.
        note_dir (Path): Directory to save note content.
        title (str): Title of the note.
        file (Path): ENEX file source.
        notebook_name (str): Name of the notebook.
        logs (dict): Log dictionary.
    """

    if not text_content:
        return

    file_path = note_dir / f"{title}.txt"
    content_bytes = text_content.encode()

    if not file_path.exists():
        file_path.write_bytes(content_bytes)

    logs[notebook_name].append({
        "file": file.name,
        "note": title,
        "success": True,
        "file_path": str(file_path),
        "notebook": notebook_name,
    })


def handle_resources(resources, note_dir, title, file, notebook_name, logs):
    """
    Extract and save all resources (e.g., images, PDFs) from a note.

    Args:
        resources (list): List of resource elements.
        note_dir (Path): Directory to save resources.
        title (str): Note title.
        file (Path): ENEX source file.
        notebook_name (str): Name of the notebook.
        logs (dict): Log dictionary.
    """
    for idx, res in enumerate(resources):
        data_element = res.find("data")
        mime_element = res.find("mime")

        if data_element is None or mime_element is None:
            continue

        mime_type = mime_element.text
        if not mime_type or not data_element.text:
            logs[notebook_name].append({
                "file": file.name,
                "note": title,
                "success": False,
                "notebook": notebook_name,
                "error": "Missing mime type or resource data"
            })
            continue

        # Guess file extension from MIME type
        extension = mimetypes.guess_extension(mime_type, strict=True) or ""
        file_name = f"{title}_{idx + 1}{extension}" if len(resources) > 1 else f"{title}{extension}"
        file_path = note_dir / file_name

        try:
            binary_data = base64.b64decode(data_element.text)
        except Exception as e:
            logs[notebook_name].append({
                "file": file.name,
                "note": title,
                "success": False,
                "notebook": notebook_name,
                "error": f"Base64 decoding failed: {str(e)}"
            })
            continue

        if not file_path.exists():
            file_path.write_bytes(binary_data)

        logs[notebook_name].append({
            "file": file.name,
            "note": title,
            "success": True,
            "file_path": str(file_path),
            "notebook": notebook_name,
        })


def process_files(output_directory: Path, dry_run: bool) -> None:
    """
    Main driver function: Processes ENEX files and optionally uploads to Google Drive.

    Args:
        output_directory (Path): Directory where files will be extracted.
        dry_run (bool): If True, skip uploading to Drive.
    """
    print(f"[INFO] Processing notes into: {output_directory}")
    if dry_run:
        print("[INFO] Dry run mode enabled — Google Drive syncing will be skipped.")

    input_directory = Path("./input_data")
    extraction_log_file = Path("./extraction_log.json")
    logs_json = load_extraction_log(extraction_log_file)

    if not input_directory.exists():
        raise FileNotFoundError("Input directory does not exist")

    output_directory.mkdir(parents=True, exist_ok=True)
    files = list_enex_files(input_directory)

    if not files:
        print("No ENEX files found.")
        return

    for file in files:
        process_enex_file(file, output_directory, logs_json)

    finalize_logs(logs_json, extraction_log_file)

    if dry_run:
        print("Dry run complete. No files were uploaded.")
    else:
        service_account = authenticate_drive()
        upload_directory(service_account, output_directory)

def finalize_logs(logs_json: dict, log_file: Path):
    log_file.write_text(json.dumps(logs_json, indent=4))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Evernote-to-Drive Migrator",
        description=(
            "Exports and processes Evernote ENEX files, replicating notebook structure "
            "into Google Drive. Supports dry-run mode to skip actual upload."
        )
    )

    parser.add_argument(
        "-o", "--output-directory",
        type=Path,
        default=Path("./EverNote Notes"),
        help="Directory where the converted notes will be saved (default: ./EverNote Notes)"
    )

    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Run without uploading to Google Drive (for testing output structure only)"
    )

    args = parser.parse_args()
    output_directory: Path = args.output_directory
    dry_run: bool = args.dry_run

    output_directory.mkdir(parents=True, exist_ok=True)

    process_files(output_directory, dry_run)
