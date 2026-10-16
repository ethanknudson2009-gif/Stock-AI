"""Install (or --uninstall) the macOS launch agent that runs scripts/daily_job.py --trade on weekdays.

Fires at 16:35 New York time in both daylight-saving states (expressed in this Mac's local time); the job's
own time-of-day and already-done guards make the duplicate firing harmless.
"""

import plistlib
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
LABEL = "com.stockai.daily"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
ET = ZoneInfo("America/New_York")


def local_times() -> list[tuple[int, int]]:
    out = set()
    for month in (7, 1):  # summer (EDT) and winter (EST)
        local = datetime(2026, month, 15, 16, 35, tzinfo=ET).astimezone()
        out.add((local.hour, local.minute))
    return sorted(out)


def main() -> None:
    uid = subprocess.check_output(["id", "-u"], text=True).strip()
    if "--uninstall" in sys.argv:
        subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], check=False)
        PLIST.unlink(missing_ok=True)
        print("uninstalled")
        return
    (ROOT / "logs").mkdir(exist_ok=True)
    plist = {
        "Label": LABEL,
        "ProgramArguments": [str(ROOT / ".venv" / "bin" / "python"), str(ROOT / "scripts" / "daily_job.py"), "--trade"],
        "WorkingDirectory": str(ROOT),
        "EnvironmentVariables": {"PYTHONPATH": str(ROOT)},
        "StartCalendarInterval": [{"Weekday": d, "Hour": h, "Minute": m} for d in range(1, 6) for h, m in local_times()],
        "StandardOutPath": str(ROOT / "logs" / "launchd.out"),
        "StandardErrorPath": str(ROOT / "logs" / "launchd.err"),
    }
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_bytes(plistlib.dumps(plist))
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], check=False, capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST)], check=True)
    print(f"installed: weekdays at local {', '.join(f'{h:02d}:{m:02d}' for h, m in local_times())}")


if __name__ == "__main__":
    main()
