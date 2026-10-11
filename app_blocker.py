from datetime import datetime as dt, timedelta
from pathlib import Path
import json
import subprocess
import sys
import time
import psutil
if sys.platform != "darwin":
    print(
        f"ERROR: Operating system {sys.platform} is not supported.",
        file=sys.stderr,
        flush=True
    )
    sys.exit(1)


HOME = Path.home()

SCHEDULES_FILE = (
    HOME
    / "Library"
    / "Application Support"
    / "python-projects"
    / "schedules.json"
)

APP_ROOTS = [
    Path("/Applications"),
    Path("/System/Applications"),
    HOME / "Applications"
]


def parent_label(app_path):
    parent = app_path.parent.name

    if str(app_path).startswith("/System/Applications/"):
        if parent == "Applications":
            return "System Applications"

    if str(app_path).startswith(str(HOME / "Applications") + "/"):
        if parent == "Applications":
            return "User Applications"

    return parent


def scan_application_paths():
    """Find application bundles without depending on Spotlight."""

    found = set()

    def walk(folder, depth=0):
        try:
            entries = folder.iterdir()
        except (OSError, PermissionError):
            return

        for entry in entries:
            try:
                if entry.is_symlink() or not entry.is_dir():
                    continue

                if entry.name.endswith(".app"):
                    found.add(str(entry))
                    continue

                if (
                    depth < 5
                    and entry.name not in {"Contents", "Frameworks"}
                    and not entry.name.startswith(".")
                ):
                    walk(entry, depth + 1)

            except (OSError, PermissionError):
                continue

    for root in APP_ROOTS:
        walk(root)

    return found


def discover_application_paths():
    """Use folder scanning first, and Spotlight as an additional source."""

    paths = scan_application_paths()

    try:
        result = subprocess.run(
            [
                "/usr/bin/mdfind",
                "kMDItemContentType == 'com.apple.application-bundle'"
            ],
            capture_output=True,
            text=True,
            timeout=15
        )

        if result.returncode == 0:
            for line in result.stdout.splitlines():
                candidate = Path(line.strip())

                if (
                    candidate.name.endswith(".app")
                    and candidate.is_dir()
                ):
                    paths.add(str(candidate))

    except (OSError, subprocess.TimeoutExpired):
        pass

    return sorted(paths, key=str.casefold)


def list_applications():
    grouped = {}

    for app_path_text in discover_application_paths():
        app_path = Path(app_path_text)
        name = app_path.name[:-4]
        label = parent_label(app_path)

        grouped.setdefault(name, []).append(
            (label, str(app_path))
        )

    result = []

    for name, entries in sorted(
        grouped.items(),
        key=lambda item: item[0].casefold()
    ):
        entries.sort(key=lambda entry: entry[1].casefold())

        if len(entries) == 1:
            result.append(name)
            continue

        used_labels = set()

        for label, app_path in entries:
            if label in used_labels:
                parent = Path(app_path).parent.parent.name
                label = f"{parent} / {label}"

            used_labels.add(label)
            result.append([name, label])

    return result


def resolve_application_path(selected_app):
    """Resolve the same app name shown in the GUI dropdown."""

    app_name = selected_app
    requested_parent = None

    if " | " in selected_app:
        app_name, requested_parent = selected_app.split(" | ", 1)

    candidates = []

    for path_text in discover_application_paths():
        candidate = Path(path_text)

        if candidate.name != f"{app_name}.app":
            continue

        candidates.append(candidate)

    if requested_parent:
        for candidate in candidates:
            label = parent_label(candidate)

            if label == requested_parent:
                return str(candidate)

            # Handles labels such as "Folder / Applications".
            if requested_parent.endswith(" / " + label):
                if candidate.parent.parent.name in requested_parent:
                    return str(candidate)

        return None

    if not candidates:
        return None

    # Prefer the regular Applications folder when names are unique.
    candidates.sort(
        key=lambda candidate: (
            0 if str(candidate).startswith("/Applications/") else 1,
            str(candidate).casefold()
        )
    )

    return str(candidates[0])


def read_schedules():
    try:
        with SCHEDULES_FILE.open("r", encoding="utf-8") as file:
            schedules = json.load(file)

        return schedules if isinstance(schedules, list) else []

    except (OSError, json.JSONDecodeError):
        return []


def valid_schedule(schedule):
    if not isinstance(schedule, dict):
        return False

    required = {"app", "start", "end", "type", "days"}

    if not required.issubset(schedule):
        return False

    if (
        not isinstance(schedule["app"], str)
        or not schedule["app"].strip()
    ):
        return False

    if schedule["type"] not in {
        "today",
        "specific_date",
        "every_day",
        "selected_days"
    }:
        return False

    if not isinstance(schedule["days"], list):
        return False

    try:
        start = dt.strptime(schedule["start"], "%H:%M").time()
        end = dt.strptime(schedule["end"], "%H:%M").time()

        if start == end:
            return False

        if schedule["type"] in {"today", "specific_date"}:
            dt.strptime(schedule["date"], "%d/%m/%Y")

    except (KeyError, TypeError, ValueError):
        return False

    return True


def schedules_start_on(schedule, date):
    if schedule.get("enabled", True) is False:
        return False

    kind = schedule["type"]

    if kind == "every_day":
        return True

    if kind in {"today", "specific_date"}:
        return (
            schedule.get("date")
            == date.strftime("%d/%m/%Y")
        )

    if kind == "selected_days":
        return date.strftime("%A") in schedule["days"]

    return False


def schedule_is_active(schedule, now):
    if not valid_schedule(schedule):
        return False

    if schedule.get("enabled", True) is False:
        return False

    start = dt.strptime(schedule["start"], "%H:%M").time()
    end = dt.strptime(schedule["end"], "%H:%M").time()

    today = now.date()
    current_time = now.time()

    if start < end:
        return (
            schedules_start_on(schedule, today)
            and start <= current_time < end
        )

    # An overnight schedule can continue from yesterday.
    yesterday = today - timedelta(days=1)

    return (
        (
            schedules_start_on(schedule, today)
            and current_time >= start
        )
        or (
            schedules_start_on(schedule, yesterday)
            and current_time < end
        )
    )


def terminate_application(selected_app):
    app_path = resolve_application_path(selected_app)

    if not app_path:
        print(
            f"ERROR: Could not find application path for {selected_app}.",
            file=sys.stderr,
            flush=True
        )
        return

    executable_prefix = f"{app_path}/Contents/"

    try:
        result = subprocess.run(
            ["/usr/bin/pgrep", "-f", executable_prefix],
            capture_output=True,
            text=True,
            timeout=5
        )

    except (OSError, subprocess.TimeoutExpired) as error:
        print(
            f"ERROR: Could not check processes for {selected_app}: {error}",
            file=sys.stderr,
            flush=True
        )
        return

    if result.returncode == 1:
        return

    if result.returncode != 0:
        print(
            f"ERROR: Process search failed for {selected_app}.",
            file=sys.stderr,
            flush=True
        )
        return

    for line in result.stdout.splitlines():
        try:
            pid = int(line.strip())

            if pid == 0:
                continue

            process = psutil.Process(pid)

            print(f"TERMINATING: PID {pid}", flush=True)

            process.terminate()

            try:
                process.wait(timeout=2)
            except psutil.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

        except (ValueError, psutil.NoSuchProcess):
            continue

        except psutil.AccessDenied:
            print(
                f"ERROR: Permission denied for PID {line}.",
                file=sys.stderr,
                flush=True
            )

        except psutil.Error as error:
            print(
                f"ERROR: Could not terminate PID {line}: {error}",
                file=sys.stderr,
                flush=True
            )


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--list-apps":
        try:
            print(json.dumps(list_applications()), flush=True)
            return 0
        except Exception as error:
            print(
                f"ERROR: Application discovery failed: {error}",
                file=sys.stderr,
                flush=True
            )
            return 1

    schedules = [
        schedule
        for schedule in read_schedules()
        if valid_schedule(schedule)
    ]

    print(
        f"BLOCKER READY: Monitoring {len(schedules)} schedule(s).",
        flush=True
    )

    announced_active = set()

    while True:
        try:
            saved = [
                schedule
                for schedule in read_schedules()
                if valid_schedule(schedule)
            ]

            # Changes made in the GUI are picked up without restarting.
            if saved != schedules:
                schedules = saved
                announced_active.clear()

                print(
                    f"SCHEDULES UPDATED: Monitoring {len(schedules)} schedule(s).",
                    flush=True
                )

            now = dt.now()
            active_keys = set()

            # Check immediately on startup, then once per second.
            for schedule in schedules:
                if not schedule_is_active(schedule, now):
                    continue

                key = (
                    schedule.get("id"),
                    schedule["app"],
                    schedule["start"],
                    schedule["end"],
                    schedule["type"],
                    schedule.get("date"),
                    tuple(schedule.get("days", []))
                )

                active_keys.add(key)

                if key not in announced_active:
                    print(
                        f"BLOCKING: {schedule['app']} "
                        f"from {schedule['start']} until {schedule['end']}.",
                        flush=True
                    )

                terminate_application(schedule["app"])

            announced_active = active_keys

            time.sleep(1)

        except KeyboardInterrupt:
            return 0

        except Exception as error:
            print(
                f"ERROR: Unexpected blocker error: {error}",
                file=sys.stderr,
                flush=True
            )
            time.sleep(2)
if __name__ == "__main__":
    sys.exit(main())