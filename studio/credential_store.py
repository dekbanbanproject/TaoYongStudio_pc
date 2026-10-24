"""Store the Gemini key for the current Windows user with DPAPI."""
import ctypes
import os
from ctypes import wintypes
from pathlib import Path

from .config import ROOT

KEY_FILE = ROOT / "secrets" / "gemini_api_key.dpapi"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _crypt(data, protect):
    if os.name != "nt":
        raise RuntimeError("การบันทึกคีย์ในเครื่องรองรับ Windows เท่านั้น")
    source = ctypes.create_string_buffer(data)
    src = _Blob(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_byte)))
    dst = _Blob()
    func = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    flags = 0x01  # CRYPTPROTECT_UI_FORBIDDEN
    if not func(ctypes.byref(src), None, None, None, None, flags, ctypes.byref(dst)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(dst.pbData, dst.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(dst.pbData)


def save_key(key, path=KEY_FILE):
    key = key.strip()
    if not key:
        raise ValueError("กรุณาใส่ Gemini API key")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_crypt(key.encode("utf-8"), True))


def load_key(path=KEY_FILE):
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    path = Path(path)
    return _crypt(path.read_bytes(), False).decode("utf-8") if path.exists() else ""


def delete_key(path=KEY_FILE):
    Path(path).unlink(missing_ok=True)
