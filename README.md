# DisHook

**DisHook** is a small desktop app for building and sending Discord webhooks without having to write JSON by hand.

Create a message, customize its appearance, add a rich embed, preview it, and send it from one simple interface.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/UI-PySide6-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-5865F2?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Stable-2EA44F?style=for-the-badge)

## ✨ What you can do

- 💬 Send regular Discord webhook messages
- 🎨 Override the webhook username and avatar
- 🧩 Build rich embeds with titles, descriptions, colors, authors, footers, media, timestamps, and fields
- 👀 Preview the message before sending it
- ✍️ Add common Discord Markdown formatting with quick buttons
- ✅ Validate Discord limits before making a request
- 🖥️ Use the app comfortably in a smaller window with built-in scrolling
- 🛡️ See clear status messages for success, errors, and rate limits

## 📸 Screenshots

Screenshots will be added soon.

## 📦 Download

The current release includes a ready-to-run **Linux x86_64 executable**:

1. Open the [v1.0.0 release](https://github.com/4Y44N-KH4L3D/Discord-Webhook-Sender/releases/tag/v1.0.0).
2. Download `DisHook-linux-x86_64` from the release assets.
3. Make it executable if needed:
   ```bash
   chmod +x DisHook-linux-x86_64
   ```
4. Run it:
   ```bash
   ./DisHook-linux-x86_64
   ```

> **Windows support is coming soon.** A Windows `.exe` is not included yet. Until it is available, Windows users can run DisHook from source with Python.

## 🚀 Run from source

### Requirements

- Python 3.10 or newer
- A Discord webhook URL

### Linux

From the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

If you use Fish shell:

```fish
python3 -m venv .venv
source .venv/bin/activate.fish
python -m pip install -r requirements.txt
python main.py
```

### Windows

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

## 🧭 How to use DisHook

1. Open the app and click **Enter**.
2. Paste your Discord webhook URL.
3. Write a message, or enable an embed and fill in its details.
4. Use **Live Preview** to check the result.
5. Click **Send Webhook**.

The **Clear** button resets the form, and **← Back** returns to the start screen.

## 📏 Discord limits

DisHook checks the main limits used by Discord webhooks:

| Item | Limit |
| --- | ---: |
| Message content | 2,000 characters |
| Embed fields | 25 |
| Embed content | 6,000 characters |
| Embed title | 256 characters |
| Embed description | 4,096 characters |
| Avatar image | 8 MB |

## 🔐 Keep your webhook private

A Discord webhook URL works like a password. Do not post it in screenshots, share it publicly, or commit it to Git.

If a webhook URL is exposed, delete or regenerate that webhook in Discord immediately.

## 🧪 Release status

DisHook is currently available as **v1.0.0 for Linux**. The core sending, embed, preview, validation, and error-handling flows have been tested on Linux. A Windows executable is planned for a future release.

If you find a bug, please open an issue with your operating system, Python version, and the steps needed to reproduce it. Never include a real webhook URL in an issue.

## 📄 License

DisHook is released under the [MIT License](LICENSE).
