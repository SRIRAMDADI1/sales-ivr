"""Hold and dial a human agent when the caller asks for a person."""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import quote

# Live agent line. National form is what we say and show; E.164 is what we dial.
DEFAULT_HUMAN_AGENT_PHONE = "610-812-6519"

HOLD_MESSAGE = "Please hold while I connect you to an agent."

_HUMAN_REQUEST = re.compile(
    r"("
    r"\b(?:talk|speak|speaking|connect|transfer|route|reach|get|need|want|rather)\b"
    r"(?:\W+\w+){0,6}\W+\b(?:human|person|someone|somebody|agent|representative|operator)\b"
    r"|"
    r"\b(?:real|live|human|actual)\s+(?:person|human|agent|representative)\b"
    r"|"
    r"\b(?:customer service|live agent|human agent|real person)\b"
    r"|"
    r"\boperator\b"
    r"|"
    r"^\s*0\s*$"
    r")",
    re.IGNORECASE,
)


def human_agent_phone() -> str:
    """Configured agent number, falling back to the live line."""

    try:
        from sales_ivr.runtime import get_config

        configured = (get_config().runtime.human_agent_phone or "").strip()
    except Exception:
        configured = ""
    return configured or DEFAULT_HUMAN_AGENT_PHONE


def to_e164(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        digits = "1" + digits
    return f"+{digits}" if digits else ""


def display_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    national = digits[-10:] if len(digits) >= 10 else digits
    if len(national) == 10:
        return f"{national[:3]}-{national[3:6]}-{national[6:]}"
    return phone.strip()


def wants_human_agent(text: str) -> bool:
    """True when the caller is asking to leave the automated IVR for a person."""

    return bool(_HUMAN_REQUEST.search(text or ""))


def human_transfer_payload() -> dict[str, Any]:
    """Dial instructions for the voice client and the handoff record."""

    phone = human_agent_phone()
    e164 = to_e164(phone)
    return {
        "action": "connect_human",
        "status": "on_hold",
        "destination_e164": e164,
        "destination_display": display_phone(phone),
        # The visitor's browser opens these. The website server cannot dial a phone.
        "tel_url": f"tel:{e164}",
        "web_call_url": f"https://teams.microsoft.com/l/call/0/0?users=4:{quote(e164)}",
    }


def _teams_installed() -> bool:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return False
    return os.path.exists(os.path.join(local, "Microsoft", "WindowsApps", "ms-teams.exe"))


def dial_target() -> str:
    """Teams can place the call. tel: on this PC opens Skype for Business, which is not signed in."""

    number = human_transfer_payload()["destination_e164"]
    if _teams_installed():
        return f"msteams:https://teams.microsoft.com/l/call/0/0?users=4:{number}"
    return f"tel:{number}"


def _bring_call_window_forward() -> None:
    """The phone app was opening behind the browser, so the click looked dead."""

    if os.name != "nt":
        return
    import ctypes
    import time

    user32 = ctypes.windll.user32
    matches: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def _enum(hwnd, _lparam):  # type: ignore[no-untyped-def]
        length = user32.GetWindowTextLengthW(hwnd)
        if not length:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.lower()
        if any(part in title for part in ("teams", "skype", "pick an app")):
            matches.append(int(hwnd))
        return True

    time.sleep(0.8)
    user32.EnumWindows(_enum, 0)
    if not matches:
        return
    hwnd = matches[-1]
    user32.ShowWindow(hwnd, 9)
    user32.keybd_event(0x12, 0, 0, 0)
    user32.SetForegroundWindow(hwnd)
    user32.keybd_event(0x12, 0, 2, 0)


def launch_human_call() -> str:
    """Open the computer's phone app and dial the human agent line."""

    target = dial_target()
    if os.name != "nt" or not hasattr(os, "startfile"):
        raise OSError("This computer has no phone app the IVR can open.")
    os.startfile(target)  # noqa: S606 - registered call handler, not a shell command
    try:
        _bring_call_window_forward()
    except Exception:
        pass
    return target
