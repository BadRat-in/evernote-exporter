# Evernote to Google Drive Migrator

A super simple and bulletproof script to migrate your notes from **Evernote** (via `.enex` export files) to **Google Drive**, preserving notebook hierarchy and note content.

---

## 🚀 Features

- 🗂️ Recreates Evernote notebook structure as Drive folders
- 📝 Uploads notes as individual Google Docs
- 📦 Supports multiple `.enex` exports
- 🔐 Uses OAuth 2.0 to authorize your personal Google Drive
- 🧪 Minimal setup, runs locally

---

## 📁 How It Works

1. Export notebooks from Evernote as `.enex` files.
2. Run the script, and sign in with your Google account.
3. The tool will parse the `.enex` files and replicate your notebooks in Google Drive.

---

## 🛠️ Requirements

- Python 3.8+
- Google Cloud Project with **Drive API** enabled
- OAuth 2.0 credentials (`credentials.json`)
- Install dependencies:

```bash
pip install -r requirements.txt
```

---

## ⚙️ Usage

```bash
python main.py
```

---

## 🔐 OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project or use an existing one.
3. Enable the **Google Drive API**.
4. Under "APIs & Services" → "Credentials":
    - Create **OAuth 2.0 Client ID**
    - Application type: **Desktop App**
    - Download the `credentials.json` file

5. When you run the script, a browser will open to request access.
6. On first run, a `token.json` file will be generated and reused for future authentication.

> ✅ Make sure you authenticate with the same Google account where you want the notes to go!

---

## 📌 Notes

- Each `.enex` file maps to one notebook.
- Notes are converted into Google Docs.
- Notebook structure is recreated using Drive folders.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 🙌 Contributing

This is a focused utility tool, but PRs and bug reports are welcome!

---

## 🧠 Why This Exists

Evernote doesn’t provide a clean way to migrate content into Google Drive. This tool is a lightweight bridge — ideal for individuals or teams moving away from Evernote.
