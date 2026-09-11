# DisHook

<p align="center">
  <img src="https://img.shields.io/badge/status-stable-2ea44f?style=flat-square" alt="Stable">
  <img src="https://img.shields.io/badge/platform-linux-1793d1?style=flat-square" alt="Linux">
  <img src="https://img.shields.io/badge/python-3.10%2B-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-mit-5865f2?style=flat-square" alt="MIT License">
</p>

**DisHook** is a Discord webhook sender built with **Python**. Create messages and embeds, preview them, and send them through a simple desktop interface.

## Features

- Send Discord webhook messages
- Customise usernames and avatars
- Create rich embeds
- Preview messages before sending
- Check Discord limits
- Show clear send status messages
- Disable `@everyone`, `@here`, and role/user mention parsing in webhook payloads
- Broadcast one payload to multiple webhook URLs (one per line), sequentially and with bounded rate-limit retries
- Save/load JSON templates and import/export safe payload JSON (webhook URLs are never included in templates)
- Use `{date}`, `{time}` (with milliseconds), and `{computer_name}` placeholders; these are expanded immediately before each webhook send
- Live Discord-style preview with three-column inline-field wrapping
- Hex colour picker with Discord decimal colour conversion
- Markdown quick actions, code blocks, spoilers, emoji insertion, and user/role mention helpers
- Delayed tooltips throughout the interface

## Requirements

- Python 3.10 or newer
- A Discord webhook URL
- Linux or Windows for source runs

The current release includes a Linux x86_64 executable. A Windows executable is planned.

## Download

Download the latest release from the [GitHub Releases page](https://github.com/4Y44N-KH4L3D/DisHook/releases/latest).

The release currently includes:

```text
DisHook-linux-x86_64
```

On Linux:

```bash
chmod +x DisHook-linux-x86_64
./DisHook-linux-x86_64
```

You may need to enable **Allow executing file as a program** in the file's properties.

## Release status

The current stable release is `v1.0.0` for Linux. The source version runs on Linux and Windows.

<u>This is an early release, so bugs may still occur.</u> Please report issues with your operating system and Python version.

<details>
<summary>Run from source</summary>

#### Linux

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

#### Windows

Open PowerShell in the project directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

There is currently no prebuilt Windows executable. Running from source requires Python to be installed.

</details>

<details>
<summary>Build a Linux executable</summary>

The repository includes the tracked `DisHook.spec` PyInstaller configuration. From an
activated virtual environment:

```bash
python -m pip install -r requirements.txt
python -m pip install pyinstaller
pyinstaller --clean --noconfirm DisHook.spec
./dist/DisHook
```

`build/` and `dist/` are generated outputs and are intentionally not committed.

</details>

<details>
<summary>Usage</summary>

1. Open DisHook and select **Enter**.
2. Enter one or more Discord webhook URLs (one per line).
3. Add a message or configure an embed.
4. Select **Live Preview**, then **Send Webhook**.

The **Clear** button resets the form. The **Back** button returns to the start screen without closing the application.
Template files intentionally omit webhook URLs and restore only valid local avatar paths.
Raw payload imports never change the webhook URL field and accept a single payload wrapped in
either a top-level array or `{"messages": [payload]}`. Invalid or unsafe payload structures
are rejected before changing the editor.
Rate-limited requests are retried sequentially up to three times; a final failure is reported
without exposing URLs. Closing the app during a request waits for the worker to stop cleanly.

When an avatar is selected, DisHook updates the webhook avatar before sending. Discord
stores that avatar on the webhook, so it remains the webhook's avatar for later sends
until it is changed again.

Supported placeholders:

| Placeholder | Replacement |
| --- | --- |
| `{date}` | Local date in `YYYY-MM-DD` format |
| `{time}` | Local time in `HH:MM:SS.mmm` format |
| `{computer_name}` | Local computer name |

Placeholders are expanded in the worker immediately before each webhook request and do not
modify the text shown in the editor.

</details>

<details>
<summary>Discord limits</summary>

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

</details>

<details>
<summary>Security</summary>

Treat a Discord webhook URL like a password. Do not include it in screenshots, issue reports, source files, or commit history.

If a webhook URL is exposed, delete or regenerate the webhook in Discord immediately.

</details>

<details>
<summary>Troubleshooting</summary>

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

</details>

<div align="center">

## Support

If you like DisHook, please leave a **star** on the repository.

</div>

<details>
<summary>Licence</summary>

DisHook is distributed under the [MIT licence](LICENSE).

</details>

<p align="center">Made with love by Ayaan</p>
