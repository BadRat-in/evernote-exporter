from pathlib import Path

import pickle
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow

pickel_path = Path("token.pickle")

def authenticate_drive():
    SCOPES = ["https://www.googleapis.com/auth/drive"]
    creds = None
    if pickel_path.exists():
            creds = pickle.loads(pickel_path.read_bytes())
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh()
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
            pickel_path.write_bytes(pickle.dumps(creds))
    return build("drive", "v3", credentials=creds)


def create_drive_folder(service, name, parent_id=None):
    print("Creating folder:", name)
    file_metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        file_metadata["parents"] = [parent_id]
    folder = service.files().create(body=file_metadata, fields="id").execute()
    return folder["id"]


def upload_file(service, file_path: Path, parent_id: str):
    print("Uploading file:", file_path.name, "from the directory:", file_path.parent)
    file_name = file_path.name
    file_metadata = {"name": file_name, "parents": [parent_id]}
    media = MediaFileUpload(file_path, resumable=True)
    service.files().create(body=file_metadata, media_body=media, fields="id").execute()


def upload_folder(service, local_path: Path, parent_id: str | None =None):
    folder_name = local_path.name
    folder_id = create_drive_folder(service, folder_name, parent_id)
    for item in local_path.iterdir():
        if item.is_dir():
            upload_folder(service, item, folder_id)
        else:
            upload_file(service, item, folder_id)
