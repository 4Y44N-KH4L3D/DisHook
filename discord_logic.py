from datetime import datetime
import platform
import re
from urllib.parse import urlparse


MAX_CONTENT, MAX_FIELDS = 2000, 25
MAX_TITLE, MAX_DESCRIPTION = 256, 4096
MAX_AUTHOR, MAX_FIELD_NAME, MAX_FIELD_VALUE, MAX_FOOTER = 256, 256, 1024, 2048
MAX_EMBED_CONTENT = 6000
DEFAULT_COLOR = "#5865F2"
PLACEHOLDER_PATTERN = re.compile(r"\{(date|time|computer_name)\}")
PAYLOAD_KEYS = {"content", "username", "embeds", "allowed_mentions"}
EMBED_KEYS = {
    "title", "description", "url", "timestamp", "color", "author", "footer",
    "image", "thumbnail", "fields",
}


def valid_url(url):
    try:
        parsed = urlparse(url)
        return isinstance(url, str) and bool(url) and parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except (TypeError, ValueError):
        return False


def valid_webhook(url):
    try:
        parsed = urlparse(url)
        parts = parsed.path.split("/")
        return (
            isinstance(url, str)
            and parsed.scheme == "https"
            and parsed.netloc.lower() in {"discord.com", "discordapp.com"}
            and len(parts) == 5
            and parts[1:3] == ["api", "webhooks"]
            and parts[3].isdigit()
            and bool(parts[4])
        )
    except (TypeError, ValueError, AttributeError):
        return False


def color_values(color):
    value = str(color or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise ValueError("Colour must be a six-digit hexadecimal value.")
    value = value.upper()
    return f"#{value}", int(value, 16)


def replace_placeholders(value, now=None, computer_name=None):
    current = now or datetime.now()
    replacements = {
        "date": current.strftime("%Y-%m-%d"),
        "time": current.strftime("%H:%M:%S.%f")[:-3],
        "computer_name": computer_name or platform.node() or "Computer",
    }
    if isinstance(value, str):
        return PLACEHOLDER_PATTERN.sub(lambda match: replacements[match.group(1)], value)
    if isinstance(value, dict):
        return {key: replace_placeholders(item, current, computer_name) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_placeholders(item, current, computer_name) for item in value]
    return value


def _text(value, name, limit):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text.")
    if len(value) > limit:
        raise ValueError(f"{name} exceeds {limit:,} characters.")
    return value


def _optional_url(value, name):
    if not isinstance(value, str) or not valid_url(value):
        raise ValueError(f"{name} must be a valid HTTP or HTTPS URL.")
    return value


def _sanitize_author(author):
    if not isinstance(author, dict):
        raise ValueError("Embed author must be an object.")
    unknown = set(author) - {"name", "url", "icon_url"}
    if unknown:
        raise ValueError(f"Unsupported author key(s): {', '.join(sorted(unknown))}.")
    result = {"name": _text(author.get("name"), "Author name", MAX_AUTHOR)}
    if not result["name"]:
        raise ValueError("Author name must not be empty.")
    for key, label in (("url", "Author URL"), ("icon_url", "Author icon URL")):
        if key in author:
            result[key] = _optional_url(author[key], label)
    return result


def _sanitize_footer(footer):
    if not isinstance(footer, dict):
        raise ValueError("Embed footer must be an object.")
    unknown = set(footer) - {"text", "icon_url"}
    if unknown:
        raise ValueError(f"Unsupported footer key(s): {', '.join(sorted(unknown))}.")
    result = {"text": _text(footer.get("text"), "Footer text", MAX_FOOTER)}
    if not result["text"]:
        raise ValueError("Footer text must not be empty.")
    if "icon_url" in footer:
        result["icon_url"] = _optional_url(footer["icon_url"], "Footer icon URL")
    return result


def _sanitize_media(media, name):
    if not isinstance(media, dict):
        raise ValueError(f"Embed {name} must be an object.")
    if set(media) != {"url"}:
        raise ValueError(f"Embed {name} must contain only a URL.")
    return {"url": _optional_url(media["url"], f"Embed {name} URL")}


def sanitize_embed(embed):
    if not isinstance(embed, dict):
        raise ValueError("Embed must be a JSON object.")
    unknown = set(embed) - EMBED_KEYS
    if unknown:
        raise ValueError(f"Unsupported embed key(s): {', '.join(sorted(unknown))}.")
    result = {}
    for key, label, limit in (
        ("title", "Embed title", MAX_TITLE),
        ("description", "Embed description", MAX_DESCRIPTION),
        ("timestamp", "Embed timestamp", 64),
    ):
        if key in embed:
            result[key] = _text(embed[key], label, limit)
    if "timestamp" in result and result["timestamp"]:
        try:
            datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Embed timestamp must be ISO-8601 text.")
    if "url" in embed:
        result["url"] = _optional_url(embed["url"], "Embed URL")
    if "color" in embed:
        color = embed["color"]
        if not isinstance(color, int) or isinstance(color, bool) or not 0 <= color <= 0xFFFFFF:
            raise ValueError("Embed color must be an integer from 0 to 16777215.")
        result["color"] = color
    for key, sanitizer in (("author", _sanitize_author), ("footer", _sanitize_footer)):
        if key in embed:
            result[key] = sanitizer(embed[key])
    for key in ("image", "thumbnail"):
        if key in embed:
            result[key] = _sanitize_media(embed[key], key)
    if "fields" in embed:
        fields = embed["fields"]
        if not isinstance(fields, list) or len(fields) > MAX_FIELDS:
            raise ValueError("Embed fields must be a list containing at most 25 items.")
        result["fields"] = []
        for index, field in enumerate(fields, 1):
            if not isinstance(field, dict):
                raise ValueError(f"Embed field {index} must be an object.")
            if set(field) - {"name", "value", "inline"}:
                raise ValueError(f"Embed field {index} contains unsupported keys.")
            name = _text(field.get("name"), f"Embed field {index} name", MAX_FIELD_NAME)
            value = _text(field.get("value"), f"Embed field {index} value", MAX_FIELD_VALUE)
            if not name or not value:
                raise ValueError(f"Embed field {index} name and value must not be empty.")
            inline = field.get("inline", False)
            if not isinstance(inline, bool):
                raise ValueError(f"Embed field {index} inline must be boolean.")
            result["fields"].append({"name": name, "value": value, "inline": inline})
        if not result["fields"]:
            result.pop("fields")
    if not any(key in result for key in ("title", "description", "author", "footer", "image", "thumbnail", "fields")):
        raise ValueError("Embed must contain title, description, author, footer, media, or fields.")
    if embed_size(result) > MAX_EMBED_CONTENT:
        raise ValueError("Embed content exceeds 6,000 characters.")
    return result


def sanitize_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object.")
    unknown = set(payload) - PAYLOAD_KEYS
    if unknown:
        raise ValueError(f"Unsupported payload key(s): {', '.join(sorted(unknown))}.")
    result = {}
    if "content" in payload:
        result["content"] = _text(payload["content"], "Payload content", MAX_CONTENT)
    if "username" in payload:
        result["username"] = _text(payload["username"], "Payload username", 80)
    if "embeds" in payload:
        embeds = payload["embeds"]
        if not isinstance(embeds, list) or len(embeds) > 1:
            raise ValueError("Payload must contain zero or one embed.")
        if embeds:
            result["embeds"] = [sanitize_embed(embeds[0])]
    mentions = payload.get("allowed_mentions", {"parse": []})
    if mentions != {"parse": []}:
        raise ValueError("allowed_mentions must remain {'parse': []} for safety.")
    result["allowed_mentions"] = {"parse": []}
    if not result.get("content") and not result.get("embeds"):
        raise ValueError("Payload must contain message content or an embed.")
    return result


def validate_payload(payload):
    sanitize_payload(payload)
    return True


def unwrap_payload(data):
    if isinstance(data, list):
        if len(data) != 1:
            raise ValueError("JSON must contain exactly one webhook payload.")
        data = data[0]
    if isinstance(data, dict) and "messages" in data:
        messages = data["messages"]
        if not isinstance(messages, list) or len(messages) != 1:
            raise ValueError("The messages wrapper must contain exactly one payload.")
        data = messages[0]
    return data


def normalize_template(data):
    if not isinstance(data, dict):
        raise ValueError("Template must be a JSON object.")
    embed = data.get("embed", {})
    if not isinstance(embed, dict):
        raise ValueError("Template embed must be an object.")
    username = data.get("username", "")
    message = data.get("message", "")
    if not isinstance(username, str) or not isinstance(message, str):
        raise ValueError("Template username and message must be text.")
    if not isinstance(data.get("embed_enabled", False), bool):
        raise ValueError("Template embed_enabled must be boolean.")
    fields = embed.get("fields", [])
    if not isinstance(fields, list) or len(fields) > MAX_FIELDS:
        raise ValueError("Template fields must be a list containing at most 25 items.")
    normalized_fields = []
    for field in fields:
        if not isinstance(field, dict):
            raise ValueError("Template fields must contain objects.")
        name = _text(field.get("name", ""), "Template field name", MAX_FIELD_NAME)
        value = _text(field.get("value", ""), "Template field value", MAX_FIELD_VALUE)
        if name and value:
            inline = field.get("inline", False)
            if not isinstance(inline, bool):
                raise ValueError("Template field inline must be boolean.")
            normalized_fields.append({"name": name, "value": value, "inline": inline})
    color = embed.get("color", DEFAULT_COLOR)
    normalized_color, _ = color_values(color)
    timestamp = embed.get("timestamp", "")
    if not isinstance(timestamp, str):
        raise ValueError("Template timestamp must be text.")
    timestamp_enabled = embed.get("timestamp_enabled", False)
    if not isinstance(timestamp_enabled, bool):
        raise ValueError("Template timestamp_enabled must be boolean.")
    fields_data = {}
    for key, limit in (
        ("title", MAX_TITLE), ("description", MAX_DESCRIPTION), ("url", 2048),
        ("author", MAX_AUTHOR), ("author_url", 2048), ("author_icon", 2048),
        ("image", 2048), ("thumbnail", 2048), ("footer", MAX_FOOTER),
        ("footer_icon", 2048),
    ):
        value = embed.get(key, "")
        if not isinstance(value, str):
            raise ValueError(f"Template {key} must be text.")
        fields_data[key] = value[:limit]
    return {
        "username": username[:80],
        "message": message[:MAX_CONTENT],
        "embed_enabled": bool(data.get("embed_enabled", False)),
        "avatar_path": data.get("avatar_path", "") if isinstance(data.get("avatar_path", ""), str) else "",
        "embed": {
            **fields_data,
            "timestamp_enabled": timestamp_enabled,
            "timestamp": timestamp,
            "color": normalized_color,
            "fields": normalized_fields,
        },
    }


def build_embed(
    *, enabled, title="", description="", url="", author="", author_url="",
    author_icon="", footer="", footer_icon="", fields=(), image_url=None,
    thumbnail_url=None, timestamp=None, color=DEFAULT_COLOR,
):
    if not enabled:
        return None
    values = {
        "title": str(title).strip()[:MAX_TITLE],
        "description": str(description).strip()[:MAX_DESCRIPTION],
        "author": str(author).strip()[:MAX_AUTHOR],
        "footer": str(footer).strip()[:MAX_FOOTER],
    }
    embed = {key: values[key] for key in ("title", "description") if values[key]}
    if valid_url(str(url).strip()):
        embed["url"] = str(url).strip()
    if timestamp:
        embed["timestamp"] = str(timestamp)
    if values["author"]:
        embed["author"] = {"name": values["author"]}
        if valid_url(str(author_url).strip()):
            embed["author"]["url"] = str(author_url).strip()
        if valid_url(str(author_icon).strip()):
            embed["author"]["icon_url"] = str(author_icon).strip()
    if values["footer"]:
        embed["footer"] = {"text": values["footer"]}
        if valid_url(str(footer_icon).strip()):
            embed["footer"]["icon_url"] = str(footer_icon).strip()
    clean_fields = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name", "")).strip()[:MAX_FIELD_NAME]
        value = str(field.get("value", "")).strip()[:MAX_FIELD_VALUE]
        if name and value:
            clean_fields.append({"name": name, "value": value, "inline": bool(field.get("inline", False))})
    if clean_fields:
        embed["fields"] = clean_fields[:MAX_FIELDS]
    if valid_url(image_url):
        embed["image"] = {"url": image_url}
    if valid_url(thumbnail_url):
        embed["thumbnail"] = {"url": thumbnail_url}
    if not any(key in embed for key in ("title", "description", "author", "fields", "footer", "image", "thumbnail")):
        return None
    _, embed["color"] = color_values(color)
    return embed


def embed_size(embed):
    return (
        len(embed.get("title", ""))
        + len(embed.get("description", ""))
        + sum(len(field["name"]) + len(field["value"]) for field in embed.get("fields", []))
        + len(embed.get("footer", {}).get("text", ""))
        + len(embed.get("author", {}).get("name", ""))
    )


def payload_errors(content, embed):
    errors = []
    if len(content) > MAX_CONTENT:
        errors.append("Message content exceeds 2,000 characters.")
    if embed and embed_size(embed) > MAX_EMBED_CONTENT:
        errors.append("Embed content exceeds 6,000 characters.")
    return errors


def build_payload(content="", username="", embed=None):
    payload = {"allowed_mentions": {"parse": []}}
    if content:
        payload["content"] = content
    if username:
        payload["username"] = username
    if embed:
        payload["embeds"] = [embed]
    return payload
