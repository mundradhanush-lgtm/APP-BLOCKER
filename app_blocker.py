
from datetime import datetime as dt, timedelta
import psutil
import subprocess
import sys
import json
import os
import time
from pathlib import Path


if sys.platform != "darwin":
    print(
        f"ERROR: Operating system {sys.platform} is not supported.",
        file=sys.stderr
    )
    sys.exit(1)


schedules_file = (
    Path.home()
    / "Library"
    / "Application Support"
    / "python-projects"
    / "schedules.json"
)


# Discover installed applications.
if len(sys.argv) > 1 and sys.argv[1] == "--list-apps":
    try:
        result = subprocess.run(
            [
                "mdfind",
                "kMDItemContentType == 'com.apple.application-bundle'"
            ],
            capture_output=True,
            text=True
        )

    except OSError as error:
        print(
            f"ERROR: Could not start application discovery: {error}",
            file=sys.stderr
        )
        sys.exit(1)

    if result.returncode != 0:
        print(
            "ERROR: Could not discover installed applications.",
            file=sys.stderr
        )
        sys.exit(1)

    applications = {}

    for item in result.stdout.splitlines():
        if (
            not item.startswith("/Applications/")
            and not item.startswith("/System/Applications/")
        ):
            continue

        parts = item.split("/")
        app_name = parts[-1]

        if not app_name.endswith(".app"):
            continue

        app_name = app_name.removesuffix(".app")

        if not app_name.strip():
            continue

        parent_folder = parts[-2]

        applications.setdefault(app_name, []).append(parent_folder)

    final_list = []

    for app_name, folders in sorted(applications.items()):
        unique_folders = sorted(set(folders))

        if len(unique_folders) == 1:
            final_list.append(app_name)
        else:
            for folder in unique_folders:
                final_list.append([app_name, folder])

    print(json.dumps(final_list), flush=True)
    sys.exit(0)


# Read schedules supplied by the Electron application.
schedules = None

if not sys.stdin.isatty():
    try:
        data = json.load(sys.stdin)

        if (
            isinstance(data, dict)
            and isinstance(data.get("schedules"), list)
        ):
            schedules = data["schedules"]

    except (json.JSONDecodeError, OSError):
        schedules = None


# Load saved schedules if none were supplied through standard input.
if schedules is None:
    try:
        if schedules_file.exists():
            with open(
                schedules_file,
                "r",
                encoding="utf-8"
            ) as file:
                schedules = json.load(file)
        else:
            schedules = []

    except (OSError, json.JSONDecodeError):
        schedules = []


if not isinstance(schedules, list):
    print(
        "ERROR: Invalid schedules received.",
        file=sys.stderr
    )
    sys.exit(1)


# Validate schedules before starting the blocker.
valid_schedules = []

for schedule in schedules:
    if not isinstance(schedule, dict):
        print("ERROR: Invalid schedule received.", file=sys.stderr)
        continue

    required = {
        "app",
        "start",
        "end",
        "type",
        "days",
        "date"
    }

    if not required.issubset(schedule.keys()):
        print("ERROR: Invalid schedule received.", file=sys.stderr)
        continue

    if (
        not isinstance(schedule["app"], str)
        or not schedule["app"].strip()
    ):
        print("ERROR: Invalid schedule received.", file=sys.stderr)
        continue

    if (
        not isinstance(schedule["start"], str)
        or not isinstance(schedule["end"], str)
    ):
        print("ERROR: Invalid schedule received.", file=sys.stderr)
        continue

    if schedule["type"] not in {
        "today",
        "specific_date",
        "every_day",
        "selected_days"
    }:
        print("ERROR: Invalid schedule received.", file=sys.stderr)
        continue

    if not isinstance(schedule["days"], list):
        print("ERROR: Invalid schedule received.", file=sys.stderr)
        continue

    if schedule["type"] in {"today", "specific_date"}:
        try:
            dt.strptime(schedule["date"], "%d/%m/%Y")
        except (TypeError, ValueError):
            print("ERROR: Invalid schedule received.", file=sys.stderr)
            continue

    try:
        start = dt.strptime(schedule["start"], "%H:%M").time()
        end = dt.strptime(schedule["end"], "%H:%M").time()

    except (TypeError, ValueError):
        print("ERROR: Invalid schedule received.", file=sys.stderr)
        continue

    if start == end:
        print("ERROR: Invalid schedule received.", file=sys.stderr)
        continue

    valid_schedules.append(schedule)


schedules = valid_schedules

if not schedules:
    print("ALLOWED", flush=True)


app_paths = {}
announced_active = set()
failed_app_messages = set()

print(
    f"BLOCKER READY: Monitoring {len(schedules)} schedule(s).",
    flush=True
)


try:
    while True:
        current = dt.now()

        # Reload saved schedules so changes take effect without restarting.
        try:
            if schedules_file.exists():
                with open(
                    schedules_file,
                    "r",
                    encoding="utf-8"
                ) as file:
                    saved_schedules = json.load(file)

                if isinstance(saved_schedules, list):
                    valid_schedules = []

                    for schedule in saved_schedules:
                        if not isinstance(schedule, dict):
                            continue

                        required = {
                            "app",
                            "start",
                            "end",
                            "type",
                            "days",
                            "date"
                        }

                        if not required.issubset(schedule.keys()):
                            continue

                        if (
                            not isinstance(schedule["app"], str)
                            or not schedule["app"].strip()
                        ):
                            continue

                        if (
                            not isinstance(schedule["start"], str)
                            or not isinstance(schedule["end"], str)
                        ):
                            continue

                        if schedule["type"] not in {
                            "today",
                            "specific_date",
                            "every_day",
                            "selected_days"
                        }:
                            continue

                        if not isinstance(schedule["days"], list):
                            continue

                        if schedule["type"] in {
                            "today",
                            "specific_date"
                        }:
                            try:
                                dt.strptime(
                                    schedule["date"],
                                    "%d/%m/%Y"
                                )
                            except (TypeError, ValueError):
                                continue

                        try:
                            start = dt.strptime(
                                schedule["start"],
                                "%H:%M"
                            ).time()

                            end = dt.strptime(
                                schedule["end"],
                                "%H:%M"
                            ).time()

                        except (TypeError, ValueError):
                            continue

                        if start == end:
                            continue

                        valid_schedules.append(schedule)

                    schedules = valid_schedules

        except (OSError, json.JSONDecodeError):
            pass

        active_schedules = []

        # Check which schedules are active right now.
        for schedule in schedules:
            if schedule.get("enabled", True) is False:
                continue

            try:
                start = dt.strptime(
                    schedule["start"],
                    "%H:%M"
                ).time()

                end = dt.strptime(
                    schedule["end"],
                    "%H:%M"
                ).time()

            except (KeyError, TypeError, ValueError):
                continue

            current_time = current.time()
            current_date = current.date()

            schedule_starts_today = False

            if schedule["type"] == "every_day":
                schedule_starts_today = True

            elif schedule["type"] in {"today", "specific_date"}:
                schedule_starts_today = (
                    schedule.get("date")
                    == current_date.strftime("%d/%m/%Y")
                )

            elif schedule["type"] == "selected_days":
                schedule_starts_today = (
                    current_date.strftime("%A")
                    in schedule.get("days", [])
                )

            schedule_is_active = False

            if start < end:
                if (
                    schedule_starts_today
                    and start <= current_time < end
                ):
                    schedule_is_active = True

            else:
                # Handle schedules that continue past midnight.
                previous_date = current_date - timedelta(days=1)
                schedule_starts_previous = False

                if schedule["type"] == "every_day":
                    schedule_starts_previous = True

                elif schedule["type"] in {"today", "specific_date"}:
                    schedule_starts_previous = (
                        schedule.get("date")
                        == previous_date.strftime("%d/%m/%Y")
                    )

                elif schedule["type"] == "selected_days":
                    schedule_starts_previous = (
                        previous_date.strftime("%A")
                        in schedule.get("days", [])
                    )

                if (
                    schedule_starts_today
                    and current_time >= start
                ):
                    schedule_is_active = True

                elif (
                    schedule_starts_previous
                    and current_time < end
                ):
                    schedule_is_active = True

            if schedule_is_active:
                active_schedules.append(schedule)

        # Enforce every active schedule.
        for schedule in active_schedules:
            schedule_key = (
                schedule.get("id"),
                schedule["app"],
                schedule["start"],
                schedule["end"],
                schedule["type"],
                schedule.get("date"),
                tuple(schedule.get("days", []))
            )

            if schedule_key not in announced_active:
                print(
                    f"BLOCKING: {schedule['app']} from "
                    f"{schedule['start']} until {schedule['end']}.",
                    flush=True
                )
                announced_active.add(schedule_key)

            selected_app = schedule["app"]

            # Find and cache the selected application's full path.
            if selected_app not in app_paths:
                duplicate_app_name = selected_app
                parent_folder = None

                if " | " in duplicate_app_name:
                    duplicate_app_name, parent_folder = (
                        duplicate_app_name.split(" | ", 1)
                    )

                try:
                    app_search = subprocess.run(
                        [
                            "mdfind",
                            f"kMDItemFSName == '{duplicate_app_name}.app'"
                        ],
                        capture_output=True,
                        text=True
                    )

                except OSError as error:
                    if selected_app not in failed_app_messages:
                        print(
                            f"ERROR: Could not start application search: "
                            f"{error}",
                            file=sys.stderr
                        )
                        failed_app_messages.add(selected_app)

                    continue

                if app_search.returncode != 0:
                    if selected_app not in failed_app_messages:
                        print(
                            f"ERROR: Could not search for the application "
                            f"{selected_app}.",
                            file=sys.stderr
                        )
                        failed_app_messages.add(selected_app)

                    continue

                paths = app_search.stdout.splitlines()
                app_path = None

                if parent_folder:
                    for check in paths:
                        if (
                            f"/{parent_folder}/" in check
                            and check.endswith(
                                f"/{duplicate_app_name}.app"
                            )
                        ):
                            app_path = check
                            break

                else:
                    if len(paths) == 1:
                        app_path = paths[0]
                    else:
                        for check in paths:
                            if check.endswith(
                                f"/{duplicate_app_name}.app"
                            ):
                                app_path = check
                                break

                if not app_path:
                    if selected_app not in failed_app_messages:
                        print(
                            f"ERROR: Could not find the application path "
                            f"for {selected_app}.",
                            file=sys.stderr
                        )
                        failed_app_messages.add(selected_app)

                    continue

                if not os.path.isdir(app_path):
                    if selected_app not in failed_app_messages:
                        print(
                            f"ERROR: The application path is no longer "
                            f"available for {selected_app}.",
                            file=sys.stderr
                        )
                        failed_app_messages.add(selected_app)

                    continue

                executable_directory = (
                    f"{app_path}/Contents/MacOS"
                )

                if not os.path.isdir(executable_directory):
                    if selected_app not in failed_app_messages:
                        print(
                            f"ERROR: Could not find the executable "
                            f"directory for {selected_app}.",
                            file=sys.stderr
                        )
                        failed_app_messages.add(selected_app)

                    continue

                app_paths[selected_app] = app_path

                if selected_app in failed_app_messages:
                    failed_app_messages.remove(selected_app)

            app_path = app_paths[selected_app]

            # Find running processes belonging to this application.
            try:
                pid = subprocess.run(
                    [
                        "pgrep",
                        "-f",
                        f"{app_path}/Contents/MacOS/"
                    ],
                    capture_output=True,
                    text=True
                )

            except OSError as error:
                print(
                    f"ERROR: Could not start process check: {error}",
                    file=sys.stderr
                )
                continue

            if pid.returncode not in (0, 1):
                print(
                    "ERROR: Could not check whether the application "
                    "is running.",
                    file=sys.stderr
                )
                continue

            final_pids = pid.stdout.splitlines()

            for final_pid in final_pids:
                try:
                    final_pid = int(final_pid)
                    process = psutil.Process(final_pid)

                    print(
                        f"TERMINATING: PID {final_pid}",
                        flush=True
                    )

                    process.terminate()

                    try:
                        process.wait(timeout=2)

                    except psutil.TimeoutExpired:
                        print(
                            f"ERROR: PID {final_pid} did not terminate "
                            "within the expected time.",
                            file=sys.stderr
                        )

                        try:
                            process.kill()
                            process.wait(timeout=2)

                        except psutil.NoSuchProcess:
                            continue

                        except psutil.AccessDenied:
                            print(
                                f"ERROR: Permission denied while forcing "
                                f"PID {final_pid} to terminate.",
                                file=sys.stderr
                            )
                            continue

                        except psutil.Error as error:
                            print(
                                f"ERROR: Could not force PID {final_pid} "
                                f"to terminate: {error}",
                                file=sys.stderr
                            )
                            continue

                except ValueError:
                    continue

                except psutil.NoSuchProcess:
                    continue

                except psutil.AccessDenied:
                    print(
                        f"ERROR: Permission denied while trying to "
                        f"terminate PID {final_pid}.",
                        file=sys.stderr
                    )
                    continue

                except psutil.Error as error:
                    print(
                        f"ERROR: Could not terminate PID {final_pid}: "
                        f"{error}",
                        file=sys.stderr
                    )
                    continue

        if not active_schedules:
            announced_active.clear()

        time.sleep(1)

except KeyboardInterrupt:
    sys.exit(1)

except OSError as error:
    print(
        f"ERROR: Operating system error: {error}",
        file=sys.stderr
    )
    sys.exit(1)

except Exception as error:
    print(
        f"ERROR: Unexpected error: {error}",
        file=sys.stderr
    )
    sys.exit(1)