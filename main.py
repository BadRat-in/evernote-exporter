import json
import base64
import mimetypes
from hashlib import md5
from pathlib import Path
import xml.etree.ElementTree as ET

from gdrive import upload_folder, authenticate_drive

input_folder: Path = Path("./input_data")
output_folder: Path = Path("./EverNote Notes")
extraction_log_file = Path("./extraction_log.json")

try:
    logs_json = json.loads(extraction_log_file.read_text())
except json.JSONDecodeError:
    logs_json = {}

assert input_folder.exists()

if not output_folder.exists():
  output_folder.mkdir(exist_ok=True)

files: list[Path] = [f for f in input_folder.iterdir() if f.is_file() and f.suffix.lower() == ".enex"]

if not len(files):
    print("No files found")
    exit(0)

for file in files:
    notebook_name = file.stem

    notes = []
    try:
        tree = ET.parse(file)
        root = tree.getroot()
        notes = root.findall("note")

        logs_json[notebook_name] = []
    except Exception as e:
        logs_json[notebook_name] = [{
            "file": file.name,
            "notebook": notebook_name,
            "error": str(e)
        }]

    for note in notes:
        title = note.find("title")

        if title is None:
            continue

        note_title = title.text

        if note_title is None:
            continue

        note_folder = output_folder / notebook_name / note_title
        note_folder.mkdir(parents=True, exist_ok=True)
        resources = note.findall("resource")

        if not len(resources):
            content = note.find("content")
            print(content)
            if content is None or content.text is None:
                logs_json[notebook_name].append({
                    "file": file.name,
                    "note": note_title,
                    "success": False,
                    "notebook": notebook_name,
                    "error": "No content/resource found"
                })
                print("No content/resource found")
                continue

            content_root = ET.fromstring(content.text.strip())

            if content_root is None:
                print("No content root found")
                logs_json[notebook_name].append({
                    "file": file.name,
                    "note": note_title,
                    "success": False,
                    "notebook": notebook_name,
                    "error": "No content root found"
                })
                continue
            else:
                text = ""
                for child in content_root:
                    text += "\n".join(child.itertext())
                if not text:
                    print("No document is empty")
                    logs_json[notebook_name].append({
                        "file": file.name,
                        "error": "No document is empty"
                    })
                    continue

                file_path = note_folder / (note_title + ".txt")
                file_hash = md5(text.encode()).hexdigest()
                print("Hash:", file_hash)

                if logs_json.get("hash", {}).get(file_hash):
                    file_path = Path(logs_json["hash"][file_hash])
                else:
                    file_path.write_bytes(text.encode())

                file_path.write_text(text.strip())

                logs_json[notebook_name].append({
                    "file": file.name,
                    "note": note_title,
                    "success": True,
                    "file_path": str(file_path),
                    "notebook": notebook_name,
                    "file_hash": file_hash
                })


        for idx, res in enumerate(resources):
            # resource
            data_element = res.find("data")
            # Resource Type
            mime_element = res.find("mime")

            if data_element is None or mime_element is None:
                continue

            mime_type = mime_element.text

            if mime_type is None:
                logs_json[notebook_name].append({
                    "file": file.name,
                    "error": "No mime type found"
                })
                continue

            if data_element.text is None:
                logs_json[notebook_name].append({
                    "file": file.name,
                    "error": "No data found"
                })
                continue

            print('mime_type', mime_type)

            # File extentsion
            extension = mimetypes.guess_extension(mime_type, strict=True)
            print('extention', extension)

            file_name = f"{note_title}_{idx + 1}{extension}" if len(resources) > 1 else f"{note_title}{extension}"
            print('file name',file_name)

            file_path = note_folder / file_name

            try:
                bytes = base64.b64decode(data_element.text)
                file_hash = md5(bytes).hexdigest()
                print("Hash:", file_hash)

                if logs_json.get("hash", {}).get(file_hash):
                    file_path = Path(logs_json["hash"][file_hash])
                else:
                    file_path.write_bytes(bytes)

                logs_json[notebook_name].append({
                    "file": file.name,
                    "note": note_title,
                    "success": True,
                    "file_path": str(file_path),
                    "notebook": notebook_name,
                    "file_hash": file_hash
                })

                if logs_json.get("hash") is None:
                    logs_json["hash"] = {}

                logs_json["hash"][file_hash] = str(file_path)
            except:
                pass

# Add the hash at the end of the file
hash = logs_json["hash"]
del logs_json["hash"]
logs_json["hash"] = hash

extraction_log_file.write_text(json.dumps(logs_json, indent=4))

# Authenticate with Google Drive API
service_account = authenticate_drive()

# Upload file to google drive
upload_folder(service_account, output_folder)
