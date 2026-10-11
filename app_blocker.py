from datetime import datetime as dt, timedelta
from pathlib import Path
import json
import os
import subprocess
import sys
import time
import psutil

if sys.platform != "darwin":
    print(
        f"ERROR: Unsupported operating system: {sys.platform}",
        file=sys.stderr,
        flush=True,
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
    Path("/System/Applications/Utilities"),
    HOME / "Applications",
]

POLL_INTERVAL = 1
APP_CACHE_SECONDS = 60

_application_paths_cache = None
_application_paths_cache_time = 0.0

def parent_label(app_path):
    """Return the folder label used to distinguish duplicate apps."""

    parent = app_path.parent.name

    if str(app_path).startswith("/System/Applications/"):
        if parent == "Applications":
            return "System Applications"

    if str(app_path).startswith(str(HOME / "Applications") + "/"):
        if parent == "Applications":
            return "User Applications"

    return parent



def scan_application_paths():
    """Find actual application bundles in application folders."""

    found = set()

    def walk(folder, depth=0):
        try:
            entries = folder.iterdir()
        except OSError:
            return

        for entry in entries:
            try:
                if not entry.is_dir():
                    continue

                if entry.name.endswith(".app"):
                    found.add(str(entry))
                    continue

                if depth < 4 and not entry.name.startswith("."):
                    walk(entry, depth + 1)

            except OSError:
                continue

    for root in APP_ROOTS:
        if not root.exists():
            continue

        if root == Path("/System/Applications"):
            try:
                for entry in root.iterdir():
                    if entry.is_dir() and entry.name.endswith(".app"):
                        found.add(str(entry))
            except OSError:
                pass
        else:
            walk(root)

    return found

def discover_application_paths(force_refresh=False):
    """Discover installed apps without searching build folders."""

    global _application_paths_cache
    global _application_paths_cache_time

    now = time.monotonic()

    if (
        not force_refresh
        and _application_paths_cache is not None
        and now - _application_paths_cache_time < APP_CACHE_SECONDS
    ):
        return list(_application_paths_cache)

    paths = scan_application_paths()

    _application_paths_cache = sorted(
        paths,
        key=str.casefold,
    )
    _application_paths_cache_time = time.monotonic()

    return list(_application_paths_cache)


def list_applications():
    """Return applications in the format expected by Electron."""

    grouped = {}

    for app_path_text in discover_application_paths(
        force_refresh=True
    ):
        app_path = Path(app_path_text)
        name = app_path.name[:-4]
        if name in {"Finder", "System Settings"}:
            continue
        label = parent_label(app_path)

        grouped.setdefault(name, []).append(
            (label, str(app_path))
        )

    result = []

    for name, entries in sorted(
        grouped.items(),
        key=lambda item: item[0].casefold(),
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
    """Resolve an application name to its actual .app bundle."""

    if not isinstance(selected_app, str):
        return None

    app_name = selected_app.strip()
    requested_parent = None

    if " | " in app_name:
        app_name, requested_parent = app_name.split(" | ", 1)

    candidates = []

    for path_text in discover_application_paths():
        candidate = Path(path_text)

        if candidate.name != f"{app_name}.app":
            continue

        candidates.append(candidate)

    if not candidates:
        return None

    if requested_parent:
        for candidate in candidates:
            label = parent_label(candidate)

            if label == requested_parent:
                return str(candidate)

            if (
                requested_parent.endswith(" / " + label)
                and candidate.parent.parent.name
                in requested_parent
            ):
                return str(candidate)

        return None

    candidates.sort(
        key=lambda candidate: (
            0
            if str(candidate).startswith("/Applications/")
            else 1,
            str(candidate).casefold(),
        )
    )

    return str(candidates[0])

def read_schedules():
    """
    Read saved schedules.

    Return None on a read/JSON error so the running blocker can
    retain its last valid schedules instead of accidentally
    stopping enforcement because of a temporary file problem.
    """

    try:
        with SCHEDULES_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            schedules = json.load(file)

        if isinstance(schedules, list):
            return schedules

        print(
            "ERROR: The schedules file must contain a JSON list.",
            file=sys.stderr,
            flush=True,
        )
        return None

    except FileNotFoundError:
        # No saved schedules file exists.
        return []

    except (OSError, json.JSONDecodeError) as error:
        print(
            f"WARNING: Could not read schedules: {error}",
            file=sys.stderr,
            flush=True,
        )
        return None


def valid_schedule(schedule):
    """Check whether a saved schedule has the required fields."""

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
        "selected_days",
    }:
        return False

    if not isinstance(schedule["days"], list):
        return False

    if not all(
        isinstance(day, str)
        for day in schedule["days"]
    ):
        return False

    try:
        if not isinstance(schedule["start"], str):
            return False

        if not isinstance(schedule["end"], str):
            return False

        start = dt.strptime(
            schedule["start"],
            "%H:%M",
        ).time()

        end = dt.strptime(
            schedule["end"],
            "%H:%M",
        ).time()

        # Equal times are not accepted as a full-day schedule.
        if start == end:
            return False

        if schedule["type"] in {
            "today",
            "specific_date",
        }:
            dt.strptime(
                schedule["date"],
                "%d/%m/%Y",
            )

    except (KeyError, TypeError, ValueError):
        return False

    return True


def schedules_start_on(schedule, date):
    """Check whether a schedule is meant to start on this date."""

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
    """
    Check whether a schedule is active at the supplied time.

    Overnight schedules can continue past midnight, including
    when their starting day was yesterday.
    """

    if not valid_schedule(schedule):
        return False

    if schedule.get("enabled", True) is False:
        return False

    start = dt.strptime(
        schedule["start"],
        "%H:%M",
    ).time()

    end = dt.strptime(
        schedule["end"],
        "%H:%M",
    ).time()

    today = now.date()
    yesterday = today - timedelta(days=1)
    current_time = now.time()

    if start < end:
        return (
            schedules_start_on(schedule, today)
            and start <= current_time < end
        )

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

def process_belongs_to_application(process, app_path):
    """
    Check whether a process executable belongs to the selected
    application's bundle.

    Matching the executable path also handles many helper
    processes whose process names differ from the app's name.
    """

    bundle_path = os.path.realpath(app_path)
    bundle_prefix = bundle_path.rstrip(os.sep) + os.sep

    try:
        info = process.info

        executable = info.get("exe")

        if executable:
            executable = os.path.realpath(executable)

            if executable.startswith(bundle_prefix):
                return True

        # On macOS, exe may be unavailable. Fall back to the
        # first command-line argument, which is usually the
        # executable path.
        command_line = info.get("cmdline") or []

        if command_line:
            first_argument = command_line[0]

            if isinstance(first_argument, str):
                first_argument = os.path.realpath(
                    first_argument
                )

                if first_argument.startswith(bundle_prefix):
                    return True

    except (
        psutil.NoSuchProcess,
        psutil.AccessDenied,
        psutil.ZombieProcess,
        OSError,
    ):
        return False

    return False


def terminate_application(selected_app):
    """
    Terminate running processes belonging to the selected app.

    Returns the number of processes successfully terminated.
    """

    app_path = resolve_application_path(selected_app)

    if not app_path:
        print(
            f"ERROR: Application not found: {selected_app}",
            file=sys.stderr,
            flush=True,
        )
        return 0

    terminated = 0

    try:
        processes = psutil.process_iter(
            attrs=["pid", "name", "exe", "cmdline"]
        )

        for process in processes:
            # Never terminate the background blocker itself.
            if process.pid == os.getpid():
                continue

            try:
                if not process_belongs_to_application(
                    process,
                    app_path,
                ):
                    continue

                print(
                    f"TERMINATING: {selected_app}, "
                    f"PID {process.pid}",
                    flush=True,
                )

                process.terminate()

                try:
                    process.wait(timeout=2)

                except psutil.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)

                terminated += 1

            except psutil.NoSuchProcess:
                # The process may have closed on its own.
                continue

            except psutil.AccessDenied:
                print(
                    f"ERROR: Permission denied for PID "
                    f"{process.pid}.",
                    file=sys.stderr,
                    flush=True,
                )

            except psutil.Error as error:
                print(
                    f"ERROR: Could not terminate PID "
                    f"{process.pid}: {error}",
                    file=sys.stderr,
                    flush=True,
                )

    except psutil.Error as error:
        print(
            f"ERROR: Could not inspect running processes: {error}",
            file=sys.stderr,
            flush=True,
        )

    return terminated

def schedule_key(schedule):
    """Create a stable key for tracking active schedules."""

    return (
        schedule.get("id"),
        schedule["app"],
        schedule["start"],
        schedule["end"],
        schedule["type"],
        schedule.get("date"),
        tuple(schedule.get("days", [])),
    )


def load_valid_schedules():
    """Load schedules and discard invalid entries."""

    saved = read_schedules()

    if saved is None:
        return None

    valid = [
        schedule
        for schedule in saved
        if valid_schedule(schedule)
    ]

    if len(valid) != len(saved):
        print(
            "WARNING: Some invalid schedules were ignored.",
            file=sys.stderr,
            flush=True,
        )

    return valid


def main():
    if (len(sys.argv) > 1 and sys.argv[1] == "--list-apps"):
        try:
            print(
                json.dumps(list_applications()),
                flush=True,
            )
            return 0

        except Exception as error:
            print(
                f"ERROR: Application discovery failed: {error}",
                file=sys.stderr,
                flush=True,
            )
            return 1

    schedules = load_valid_schedules()

    if schedules is None:
        schedules = []

    print(
        f"BLOCKER READY: Monitoring {len(schedules)} "
        f"schedule(s).",
        flush=True,
    )

    announced_active = set()

    while True:
        try:
            saved = load_valid_schedules()

            # Keep the last valid list if the file is temporarily
            # unreadable or contains invalid JSON.
            if saved is not None and saved != schedules:
                schedules = saved
                announced_active.clear()

                print(
                    f"SCHEDULES UPDATED: Monitoring "
                    f"{len(schedules)} schedule(s).",
                    flush=True,
                )

            now = dt.now()
            active_keys = set()

            for schedule in schedules:
                if not schedule_is_active(schedule, now):
                    continue

                key = schedule_key(schedule)
                active_keys.add(key)

                if key not in announced_active:
                    print(
                        f"ACTIVE SCHEDULE: {schedule['app']} "
                        f"from {schedule['start']} "
                        f"until {schedule['end']}.",
                        flush=True,
                    )

                terminate_application(schedule["app"])

            announced_active = active_keys

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print(
                "BLOCKER STOPPED.",
                flush=True,
            )
            return 0

        except Exception as error:
            print(
                f"ERROR: Unexpected blocker error: {error}",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(2)

if __name__ == "__main__":
    sys.exit(main())