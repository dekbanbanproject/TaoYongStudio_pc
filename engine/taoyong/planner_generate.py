"""Run a plan request through Gemini API now or with Windows Task Scheduler."""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import requests

from .credential_store import load_key
from .planner_handoff import import_response, request_prompt

MODEL = "gemini-3.8-flash"
URL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % MODEL


def generate_request(request_path, root=None, key=None, session=requests):
    path = Path(request_path)
    request = json.loads(path.read_text(encoding="utf-8"))
    root = Path(root or path.parents[2])
    result_path = root / "plans" / "results" / path.name
    result_path.parent.mkdir(parents=True, exist_ok=True)
    if result_path.exists() and json.loads(result_path.read_text(encoding="utf-8")).get("status") == "done":
        raise FileExistsError("คำขอนี้เขียนบทเสร็จแล้ว")
    result_path.write_text(json.dumps({"id": request["id"], "status": "in_progress"},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        key = key or load_key()
        if not key:
            raise ValueError("ยังไม่ได้ตั้ง Gemini API key")
        body = {"contents": [{"role": "user", "parts": [{"text": request_prompt(request)}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.5,
                                     "maxOutputTokens": 8192}}
        response = session.post(URL, headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                                json=body, timeout=(15, 240))
        if not response.ok:
            raise RuntimeError("Gemini API HTTP %s: %s" % (response.status_code, response.text[:250]))
        candidates = response.json().get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini ไม่ส่งบทกลับมา")
        text = "".join(part.get("text", "") for part in candidates[0].get("content", {}).get("parts", []))
        if not text:
            raise RuntimeError("Gemini ส่งบทว่างเปล่า")
        return import_response(text, request, root)
    except Exception as exc:
        result_path.write_text(json.dumps({"id": request["id"], "status": "failed",
                                           "message": str(exc)[:400]}, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        raise


def schedule_request(request_path, when, root=None, runner=subprocess.run):
    if os.name != "nt":
        raise RuntimeError("การตั้งเวลาในโปรแกรมรองรับ Windows เท่านั้น")
    path = Path(request_path).resolve()
    root = Path(root or path.parents[2]).resolve()
    if when <= dt.datetime.now() + dt.timedelta(minutes=1):
        raise ValueError("เวลาเริ่มต้องช้ากว่าตอนนี้อย่างน้อย 1 นาที")
    python = root / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        python = Path(sys.executable)
    name = "KidsStudio Plan " + path.stem
    env = dict(os.environ, KIDS_PLAN_NAME=name, KIDS_PLAN_WHEN=when.strftime("%Y-%m-%dT%H:%M"),
               KIDS_PLAN_EXE=str(python), KIDS_PLAN_ROOT=str(root),
               KIDS_PLAN_ARGS='-m studio plan-generate --request "%s"' % path)
    script = ("$ErrorActionPreference = 'Stop'; "
              "$at = [datetime]::ParseExact($env:KIDS_PLAN_WHEN, 'yyyy-MM-ddTHH:mm', "
              "[Globalization.CultureInfo]::InvariantCulture); "
              "$action = New-ScheduledTaskAction -Execute $env:KIDS_PLAN_EXE "
              "-Argument $env:KIDS_PLAN_ARGS -WorkingDirectory $env:KIDS_PLAN_ROOT; "
              "$trigger = New-ScheduledTaskTrigger -Once -At $at; "
              "Register-ScheduledTask -TaskName $env:KIDS_PLAN_NAME -Action $action "
              "-Trigger $trigger -Force -ErrorAction Stop | Out-Null")
    command = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
    result = runner(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    creationflags=0x08000000, env=env)
    if result.returncode:
        raise RuntimeError("ตั้งเวลาใน Windows ไม่สำเร็จ: " + (result.stderr or result.stdout)[-300:])
    return name


def cancel_scheduled_request(request, root):
    name = request.get("windows_task")
    if name:
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", name], capture_output=True,
                       creationflags=0x08000000 if os.name == "nt" else 0)
