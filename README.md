# DisHook

DisHook is a PySide6 desktop application for creating and sending Discord webhook messages. It provides a graphical interface for regular messages, webhook appearance settings, rich embeds, previews, and basic Discord limit validation.

## Features

- Send messages through a Discord webhook
- Override the webhook username and avatar
- Create embeds with titles, descriptions, colors, authors, footers, images, thumbnails, timestamps, and fields
- Preview messages and embeds before sending
- Add common Markdown formatting to message text
- Validate message, field, embed, and avatar limits
- Display clear status messages for successful sends, errors, and rate limits
- Use the interface in smaller windows with scrollable panels

## Requirements

- Python 3.10 or newer
- A Discord webhook URL
- Linux or Windows when running from source

The current release includes a prebuilt Linux x86_64 executable. A Windows executable is planned for a future release.

## Download

The latest stable release is available on the [GitHub Releases page](https://github.com/4Y44N-KH4L3D/DisHook/releases/latest).

The release currently includes:

```text
DisHook-linux-x86_64
```

On Linux, download the file, open a terminal in its directory, and run:

```bash
chmod +x DisHook-linux-x86_64
./DisHook-linux-x86_64
```

Depending on your desktop environment, you may also need to enable **Allow executing file as a program** in the file's properties before opening it.

## Run from source

### Linux

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python3 main.py
```

For Fish shell:

```fish
python3 -m venv .venv
source .venv/bin/activate.fish
python -m pip install -r requirements.txt
python3 main.py
```

### Windows

Open PowerShell in the project directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

There is currently no prebuilt Windows executable. Running from source requires Python to be installed.

## Usage

1. Open DisHook and select **Enter**.
2. Enter a Discord webhook URL.
3. Add a message, or enable the embed section and configure an embed.
4. Use **Live Preview** to review the message.
5. Select **Send Webhook**.

The **Clear** button resets the form. The **Back** button returns to the start screen without closing the application.

## Discord limits

DisHook checks the main limits used by Discord webhooks:

| Item | Limit |
| --- | ---: |
| Message content | 2,000 characters |
| Embed fields | 25 |
| Embed content | 6,000 characters |
| Embed title | 256 characters |
| Embed description | 4,096 characters |
| Embed author name | 256 characters |
| Embed field name | 256 characters |
| Embed field value | 1,024 characters |
| Embed footer text | 2,048 characters |
| Avatar image | 8 MB |

## Security

Treat a Discord webhook URL like a password. Do not include it in screenshots, issue reports, source files, or commit history.

If a webhook URL is exposed, delete or regenerate the webhook in Discord immediately.

## Troubleshooting

### The application does not start

Make sure the virtual environment is active and the dependencies are installed:

```bash
python -m pip install -r requirements.txt
```

Then run:

```bash
python main.py
```

### The Linux executable does not open

Run it from a terminal so that any error message is visible:

```bash
./DisHook-linux-x86_64
```

If permission is denied, make the file executable:

```bash
chmod +x DisHook-linux-x86_64
```

### A webhook fails to send

Check that:

- The webhook URL belongs to Discord and has not been deleted.
- The message or embed contains content.
- The message and embed are within Discord's limits.
- Your network connection is available.

## Release status

The current stable release is `v1.0.0` for Linux. The source version can also be run on Linux and Windows. Windows packaging is planned for a future release.

## License

DisHook is distributed under the [MIT License](LICENSE).
