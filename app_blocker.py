from datetime import datetime as dt, timedelta
from pathlib import Path
import fcntl
import json
import os
import psutil
import sys
import time

if sys.platform != "darwin":
    print(
        f"ERROR: Unsupported operating system: {sys.platform}",
        file=sys.stderr,
        flush=True,
    )
    sys.exit(1)


HOME = Path.home()

APP_SUPPORT = (
    HOME
    / "Library"
    / "Application Support"
    / "python-projects"
)

SCHEDULES_FILE = APP_SUPPORT / "schedules.json"
LOCK_FILE = APP_SUPPORT / "app_blocker.lock"

APP_ROOTS = [
    Path("/Applications"),
    Path("/System/Applications"),
    Path("/System/Applications/Utilities"),
    HOME / "Applications",
]

# CHANGED: Check schedules five times per second.
POLL_INTERVAL = 0.2

# Unchanged: Cache installed applications for 60 seconds.
APP_CACHE_SECONDS = 60

_application_paths_cache = None
_application_paths_cache_time = 0.0
_blocker_lock_file = None


def acquire_single_instance_lock():
    """
    Prevent multiple Python blocker loops from running
    simultaneously.

    The operating system releases this lock automatically
    when the owning process exits.
    """

    global _blocker_lock_file

    try:
        APP_SUPPORT.mkdir(parents=True, exist_ok=True)

        _blocker_lock_file = LOCK_FILE.open("a")

        fcntl.flock(
            _blocker_lock_file.fileno(),
            fcntl.LOCK_EX | fcntl.LOCK_NB,
        )

        return True

    except BlockingIOError:
        print(
            "BLOCKER ALREADY RUNNING.",
            flush=True,
        )
        return False

    except OSError as error:
        print(
            f"ERROR: Could not acquire blocker lock: {error}",
            file=sys.stderr,
            flush=True,
        )
        return False


def parent_label(app_path):
    """Return a readable parent-folder label for an app."""

    parent = app_path.parent.name

    if str(app_path).startswith("/System/Applications/"):
        if parent == "Applications":
            return "System Applications"

    user_apps = str(HOME / "Applications")

    if str(app_path).startswith(user_apps + "/"):
        if parent == "Applications":
            return "User Applications"

    return parent


def scan_application_paths():
    """Find application bundles without scanning build folders."""

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
            # Only scan immediate application bundles here.
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
    """Discover installed apps and cache the results."""

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


def get_application_labels(paths):
    """
    Generate distinct labels for applications sharing a name.

    The labels are also used when resolving the app selected
    in the Electron dropdown.
    """

    labels = {
        path: parent_label(Path(path))
        for path in paths
    }

    while True:
        groups = {}

        for path, label in labels.items():
            groups.setdefault(label.casefold(), []).append(path)

        duplicates = [
            paths_with_same_label
            for paths_with_same_label in groups.values()
            if len(paths_with_same_label) > 1
        ]

        if not duplicates:
            break

        changed = False

        for duplicate_paths in duplicates:
            for path in duplicate_paths:
                app_path = Path(path)
                parent = app_path.parent

                if parent.parent == parent:
                    continue

                ancestor = parent.parent.name

                if not ancestor:
                    ancestor = str(parent.parent)

                new_label = f"{ancestor} / {labels[path]}"

                if new_label != labels[path]:
                    labels[path] = new_label
                    changed = True

        if not changed:
            for duplicate_paths in duplicates:
                for path in duplicate_paths:
                    labels[path] = (
                        f"{labels[path]} ({path})"
                    )
            break

    return labels


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

        grouped.setdefault(name, []).append(str(app_path))

    result = []

    for name, paths in sorted(
        grouped.items(),
        key=lambda item: item[0].casefold(),
    ):
        paths.sort(key=str.casefold)

        if len(paths) == 1:
            result.append(name)
            continue

        labels = get_application_labels(paths)

        for path in paths:
            result.append([name, labels[path]])

    return result


def resolve_application_path(selected_app):
    """Resolve an Electron selection to an actual .app bundle."""

    if not isinstance(selected_app, str):
        return None

    selected_app = selected_app.strip()

    if not selected_app:
        return None

    requested_parent = None

    if " | " in selected_app:
        app_name, requested_parent = selected_app.split(
            " | ",
            1,
        )
        app_name = app_name.strip()
        requested_parent = requested_parent.strip()
    else:
        app_name = selected_app

    if not app_name:
        return None

    candidates = []

    for path_text in discover_application_paths():
        candidate = Path(path_text)

        if candidate.name == f"{app_name}.app":
            candidates.append(str(candidate))

    if not candidates:
        return None

    if requested_parent:
        labels = get_application_labels(candidates)

        for path in candidates:
            if labels[path] == requested_parent:
                return path

        return None

    candidates.sort(
        key=lambda path: (
            0 if path.startswith("/Applications/") else 1,
            path.casefold(),
        )
    )

    return candidates[0]


def read_schedules():
    """
    Read schedules.json.

    Return None on a read error so the blocker can retain
    its last valid schedules.
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
        return None

    except (OSError, json.JSONDecodeError) as error:
        print(
            f"WARNING: Could not read schedules: {error}",
            file=sys.stderr,
            flush=True,
        )

        return None


VALID_SCHEDULE_TYPES = {
    "today",
    "specific_date",
    "every_day",
    "selected_days",
}

VALID_WEEKDAYS = {
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
}


def valid_schedule(schedule):
    """Validate a schedule before it can block an application."""

    if not isinstance(schedule, dict):
        return False

    required = {
        "app",
        "start",
        "end",
        "type",
        "days",
    }

    if not required.issubset(schedule):
        return False

    if (
        not isinstance(schedule["app"], str)
        or not schedule["app"].strip()
    ):
        return False

    if schedule["type"] not in VALID_SCHEDULE_TYPES:
        return False

    if not isinstance(schedule["days"], list):
        return False

    if not all(
        isinstance(day, str)
        and day in VALID_WEEKDAYS
        for day in schedule["days"]
    ):
        return False

    if schedule.get("enabled", True) not in (True, False):
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

        if start == end:
            return False

        if schedule["type"] in {"today", "specific_date"}:
            if not isinstance(schedule.get("date"), str):
                return False

            dt.strptime(
                schedule["date"],
                "%d/%m/%Y",
            )

    except (KeyError, TypeError, ValueError):
        return False

    return True


def load_valid_schedules():
    """Load schedules, ignoring invalid entries."""

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


def schedules_start_on(schedule, date):
    """Check whether a schedule starts on a particular date."""

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
    Check whether a schedule is active now.

    Supports schedules that cross midnight and schedules
    that started on the previous day.
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
    Check whether a process executable belongs to an app bundle.

    Do not match by process name alone: unrelated apps and
    background processes can share names.
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
    Terminate processes belonging to the selected application.

    Returns the number of successfully terminated processes.
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


def main():
    # Electron uses this command to populate the app dropdown.
    # It must not start the continuous blocking loop.
    if len(sys.argv) > 1 and sys.argv[1] == "--list-apps":
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

    if not acquire_single_instance_lock():
        return 0

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