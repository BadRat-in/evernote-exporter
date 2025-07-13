import json
import base64
import argparse
import mimetypes
from hashlib import md5
from pathlib import Path
import xml.etree.ElementTree as ET

from gdrive import upload_directory, authenticate_drive

def load_extraction_log(log_file: Path) -> dict:

    if not log_file.exists():
        log_file.write_text("{}")
        return {}

    try:
        return json.loads(log_file.read_text())
    except Exception:
        return {}

def list_enex_files(input_dir: Path) -> list[Path]:
    return [f for f in input_dir.iterdir() if f.suffix.lower() == ".enex"]

def process_enex_file(file: Path, output_dir: Path, logs: dict):
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
    title = note.findtext("title")
    if not title:
        return

    note_dir = output_dir / notebook_name / title
    note_dir.mkdir(parents=True, exist_ok=True)

    resources = note.findall("resource")
    if resources:
        handle_resources(resources, note_dir, title, file, notebook_name, logs)
    else:
        handle_text_content(note, note_dir, title, file, notebook_name, logs)

def handle_text_content(note, note_dir, title, file, notebook_name, logs):
    content_element = note.find("content")

    if content_element is None or content_element.text is None:
        logs[notebook_name].append({
            "file": file.name,
            "note": title,
            "success": False,
            "notebook": notebook_name,
            "error": "No content/resource found"
        })
        print(f"[WARN] No content found for note: {title}")
        return

    try:
        content_root = ET.fromstring(content_element.text.strip())
    except ET.ParseError:
        logs[notebook_name].append({
            "file": file.name,
            "note": title,
            "success": False,
            "notebook": notebook_name,
            "error": "Content XML parsing failed"
        })
        return

    text = "\n".join(content_root.itertext()).strip()

    if not text:
        logs[notebook_name].append({
            "file": file.name,
            "note": title,
            "success": False,
            "notebook": notebook_name,
            "error": "Note content is empty"
        })
        return

    file_path = note_dir / f"{title}.txt"
    content_bytes = text.encode()
    file_hash = md5(content_bytes).hexdigest()

    if logs.get("hash", {}).get(file_hash):
        # Skip writing if hash already exists
        file_path = Path(logs["hash"][file_hash])
    else:
        file_path.write_bytes(content_bytes)

    file_path.write_text(text)

    logs[notebook_name].append({
        "file": file.name,
        "note": title,
        "success": True,
        "file_path": str(file_path),
        "notebook": notebook_name,
        "file_hash": file_hash
    })

    # Update hash reference
    logs.setdefault("hash", {})[file_hash] = str(file_path)

def handle_resources(resources, note_dir, title, file, notebook_name, logs):
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

        file_hash = md5(binary_data).hexdigest()

        if logs.get("hash", {}).get(file_hash):
            file_path = Path(logs["hash"][file_hash])
        else:
            file_path.write_bytes(binary_data)

        logs[notebook_name].append({
            "file": file.name,
            "note": title,
            "success": True,
            "file_path": str(file_path),
            "notebook": notebook_name,
            "file_hash": file_hash
        })

        logs.setdefault("hash", {})[file_hash] = str(file_path)

def finalize_logs(logs_json: dict, log_file: Path):
    logs_json["hash"] = logs_json.pop("hash", {})
    log_file.write_text(json.dumps(logs_json, indent=4))

def process_files(output_directory: Path, dry_run: bool) -> None:
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

    if output_directory.exists() and any(output_directory.iterdir()):
        raise ValueError(f"Output directory '{output_directory}' already exists and is not empty.")
    else:
        output_directory.mkdir(parents=True, exist_ok=True)

    process_files(output_directory, dry_run)
