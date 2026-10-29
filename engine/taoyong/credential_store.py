"""Store and retrieve the Gemini API key portably for TaoYongStudio across any machine."""
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path

from .config import ROOT

KEY_FILE = ROOT / "secrets" / "gemini_api_key.dpapi"
TXT_KEY_FILE = ROOT / "secrets" / "gemini_api_key.txt"
CONFIG_FILE = ROOT / "config.json"


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
    """Save key portably to config.json, secrets file, and Windows DPAPI."""
    key = str(key).strip()
    if not key:
        raise ValueError("กรุณาใส่ Gemini API key")

    # 1. Save in config.json for full portability across machines
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            cfg["gemini_key"] = key
            CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    # 2. Save in secrets/gemini_api_key.txt
    try:
        TXT_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        TXT_KEY_FILE.write_text(key, encoding="utf-8")
    except Exception:
        pass

    # 3. Save to DPAPI on Windows if available
    if os.name == "nt":
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(_crypt(key.encode("utf-8"), True))
        except Exception:
            pass


def load_key(path=KEY_FILE):
    """Load key from environment, config.json, secrets text file, or DPAPI."""
    # 1. Environment variable
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"].strip()

    # 2. config.json (portable)
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            k = cfg.get("gemini_key") or cfg.get("api_keys", {}).get("gemini")
            if k and str(k).strip():
                return str(k).strip()
        except Exception:
            pass

    # 3. Plaintext secret file in folder (portable)
    if TXT_KEY_FILE.exists():
        try:
            k = TXT_KEY_FILE.read_text(encoding="utf-8").strip()
            if k:
                return k
        except Exception:
            pass

    # 4. Windows DPAPI fallback
    p = Path(path)
    if p.exists() and os.name == "nt":
        try:
            return _crypt(p.read_bytes(), False).decode("utf-8").strip()
        except Exception:
            pass

    return ""


def delete_key(path=KEY_FILE):
    """Delete key from all locations (config.json, secrets, and DPAPI)."""
    Path(path).unlink(missing_ok=True)
    TXT_KEY_FILE.unlink(missing_ok=True)
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            changed = False
            if "gemini_key" in cfg:
                del cfg["gemini_key"]
                changed = True
            if "api_keys" in cfg and "gemini" in cfg["api_keys"]:
                del cfg["api_keys"]["gemini"]
                changed = True
            if changed:
                CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


def has_key():
    return bool(load_key())


# --------------------------------------------------------------------------
# Named secrets (Gemini, Azure Speech, ...)
#
# Stored encrypted with Windows DPAPI in secrets/<name>.dpapi and mirrored
# into config.json (git-ignored) so the value survives a restart. The plain
# text file fallback used for Gemini is NOT used for named secrets, so those
# never hit the disk unencrypted.
# --------------------------------------------------------------------------

SECRETS_DIR = ROOT / "secrets"


def _secret_paths(name: str):
    return (
        SECRETS_DIR / ("%s.dpapi" % name),
        SECRETS_DIR / ("%s.txt" % name),
    )


def save_secret(name: str, key: str) -> str:
    """Encrypt and store a named secret. Returns the stored name."""
    key = str(key).strip()
    if not key:
        raise ValueError("กรุณาใส่ค่า key")

    dpapi_path, txt_path = _secret_paths(name)
    dpapi_path.parent.mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        dpapi_path.write_bytes(_crypt(key.encode("utf-8"), True))
    else:
        # Non-Windows fallback: keep it out of the way but still recoverable.
        txt_path.write_text(key, encoding="utf-8")
        try:
            dpapi_path.unlink()
        except OSError:
            pass

    try:
        cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else {}
        cfg.setdefault("api_keys", {})[name] = key
        CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return name


def load_secret(name: str) -> str:
    dpapi_path, txt_path = _secret_paths(name)

    if dpapi_path.exists() and os.name == "nt":
        try:
            return _crypt(dpapi_path.read_bytes(), False).decode("utf-8").strip()
        except Exception:
            pass
    if txt_path.exists():
        try:
            return txt_path.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            v = (cfg.get("api_keys") or {}).get(name)
            if v and str(v).strip():
                return str(v).strip()
        except Exception:
            pass
    return ""


def delete_secret(name: str) -> bool:
    dpapi_path, txt_path = _secret_paths(name)
    removed = False
    for p in (dpapi_path, txt_path):
        try:
            if p.exists():
                p.unlink()
                removed = True
        except OSError:
            pass
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if "api_keys" in cfg and name in cfg["api_keys"]:
                del cfg["api_keys"][name]
                CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                removed = True
        except Exception:
            pass
    return removed


def has_secret(name: str) -> bool:
    return bool(load_secret(name))

