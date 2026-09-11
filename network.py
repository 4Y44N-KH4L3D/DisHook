import base64
import mimetypes
import os
import time

import requests


MAX_AVATAR_BYTES = 8 * 1024 * 1024
IMAGE_MIMES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
REQUEST_ERRORS = (requests.RequestException, OSError, ValueError)


def image_data_url(path):
    try:
        mime = mimetypes.guess_type(path)[0]
        if mime not in IMAGE_MIMES or os.path.getsize(path) > MAX_AVATAR_BYTES:
            return None
        with open(path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode()
        return f"data:{mime};base64,{encoded}"
    except (OSError, TypeError):
        return None


def _retry_after(response):
    value = None
    try:
        body = response.json()
        if isinstance(body, dict):
            value = body.get("retry_after")
    except (ValueError, TypeError, AttributeError):
        pass
    if value is None:
        try:
            value = response.headers.get("Retry-After", 1)
        except AttributeError:
            value = 1
    try:
        return max(0.0, min(float(value), 120.0))
    except (TypeError, ValueError):
        return 1.0


def _wait(seconds, should_continue):
    end = time.monotonic() + seconds
    while should_continue() and time.monotonic() < end:
        time.sleep(min(0.1, end - time.monotonic()))
    return should_continue()


def _request_with_retries(
    method, url, *, json, timeout, session=None, max_retries=3, should_continue=lambda: True
):
    session=session or requests
    attempts = 0
    try:
        retries = max(0, min(int(max_retries), 5))
    except (TypeError, ValueError):
        retries = 3
    while should_continue():
        try:
            response = getattr(session, method)(url, json=json, timeout=timeout)
        except REQUEST_ERRORS as error:
            return None, error
        if response.status_code != 429 or attempts >= retries:
            return response, None
        attempts += 1
        if not _wait(_retry_after(response), should_continue):
            return None, InterruptedError("Request interrupted.")
    return None, InterruptedError("Request interrupted.")


def update_avatar(url, path, session=None, should_continue=lambda: True):
    data = image_data_url(path)
    if not data:
        return False, "Unsupported or unreadable image."
    response, error = _request_with_retries(
        "patch", url, json={"avatar": data}, timeout=15,
        session=session, should_continue=should_continue,
    )
    if error:
        return False, "Request interrupted." if isinstance(error, InterruptedError) else "Could not contact Discord while updating the avatar."
    return (True, None) if response.ok else (False, f"Discord returned HTTP {response.status_code}.")


def send_request(url, payload, avatar_path="", max_retries=3, should_continue=lambda: True, session=None):
    if avatar_path:
        ok, error = update_avatar(url, avatar_path, session=session, should_continue=should_continue)
        if not ok:
            return {"kind": "avatar", "error": error}
    response, error = _request_with_retries(
        "post", url, json=payload, timeout=20, max_retries=max_retries,
        session=session, should_continue=should_continue,
    )
    if error:
        return {"kind": "connection", "error": "Request interrupted." if isinstance(error, InterruptedError) else "Could not contact Discord."}
    return {"kind": "response", "response": response}


def broadcast_requests(
    urls, payload=None, avatar_path="", payload_factory=None, should_continue=lambda: True,
    max_retries=3, session=None
):
    results = []
    for url in urls:
        if not should_continue():
            break
        current_payload = payload_factory() if payload_factory else payload
        result = send_request(
            url, current_payload, avatar_path, max_retries=max_retries,
            should_continue=should_continue, session=session,
        )
        response = result.get("response")
        if result["kind"] == "response" and response.status_code in (200, 204):
            results.append({"ok": True, "status": response.status_code})
        elif result["kind"] == "response":
            results.append({"ok": False, "status": response.status_code})
        else:
            results.append({"ok": False, "error": result.get("error", "Request failed.")})
    return results
