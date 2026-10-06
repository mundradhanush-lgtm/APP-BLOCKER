from datetime import datetime as dt,timedelta
import psutil
import subprocess
import sys
import json
import os
import time
import platform

dictionary={}
main_list=[]
new_list_for_i=[]
processed=[]
final_list=[]

operating_system=platform.system()


def format_date(date):
    return date.strftime("%d/%m/%Y")


def get_date_from_string(date_string):
    try:
        return dt.strptime(date_string,"%d/%m/%Y").date()
    except (TypeError,ValueError):
        return None


def get_weekday_name(date):
    return date.strftime("%A")


def schedule_starts_on_date(schedule,date):
    if(schedule.get("enabled",True) is False):
        return False

    schedule_type=schedule.get("type")

    if(schedule_type=="every_day"):
        return True

    if(schedule_type=="today"):
        return schedule.get("date")==format_date(date)

    if(schedule_type=="specific_date"):
        return schedule.get("date")==format_date(date)

    if(schedule_type=="selected_days"):
        return get_weekday_name(date) in schedule.get("days",[])

    return False


def schedule_is_active(schedule,now):
    if(schedule.get("enabled",True) is False):
        return False

    try:
        start=dt.strptime(schedule["start"],"%H:%M").time()
        end=dt.strptime(schedule["end"],"%H:%M").time()
    except ValueError:
        return False

    current=now.time()
    current_date=now.date()

    if(start<end):
        return schedule_starts_on_date(schedule,current_date) and start<=current<end

    previous_date=current_date-timedelta(days=1)

    return (
        (schedule_starts_on_date(schedule,current_date) and current>=start)
        or
        (schedule_starts_on_date(schedule,previous_date) and current<end)
    )


def validate_schedule(schedule):
    if(not isinstance(schedule,dict)):
        return False

    required={"app","start","end","type","days","date"}

    if(not required.issubset(schedule.keys())):
        return False

    if(not isinstance(schedule["app"],str) or not schedule["app"].strip()):
        return False

    if(not isinstance(schedule["start"],str) or not isinstance(schedule["end"],str)):
        return False

    if(schedule["type"] not in {"today","specific_date","every_day","selected_days"}):
        return False

    if(not isinstance(schedule["days"],list)):
        return False

    if(schedule["type"] in {"today","specific_date"}):
        if(get_date_from_string(schedule["date"]) is None):
            return False

    try:
        start=dt.strptime(schedule["start"],"%H:%M").time()
        end=dt.strptime(schedule["end"],"%H:%M").time()
    except ValueError:
        return False

    if(start==end):
        return False

    return True


# ============================================================
# MACOS
# ============================================================

def get_process_path_macos(selected_app):
    duplicate_app_name=selected_app
    parent_folder=None

    if(" | " in duplicate_app_name):
        duplicate_app_name,parent_folder=duplicate_app_name.split(" | ",1)

    try:
        app_search=subprocess.run(
            ["mdfind",f"kMDItemFSName == '{duplicate_app_name}.app'"],
            capture_output=True,
            text=True
        )
    except OSError as error:
        print(
            f"ERROR: Could not start application search: {error}",
            file=sys.stderr
        )
        return None

    if(app_search.returncode!=0):
        print(
            f"ERROR: Could not search for the application {selected_app}.",
            file=sys.stderr
        )
        return None

    paths=app_search.stdout.splitlines()

    if(parent_folder):
        for check in paths:
            if(
                f"/{parent_folder}/" in check
                and check.endswith(f"/{duplicate_app_name}.app")
            ):
                return check
    else:
        if(len(paths)==1):
            return paths[0]

        for check in paths:
            if(check.endswith(f"/{duplicate_app_name}.app")):
                return check

    return None


def terminate_running_processes_macos(app_path):
    try:
        pid=subprocess.run(
            ["pgrep","-f",f"{app_path}/Contents/MacOS/"],
            capture_output=True,
            text=True
        )
    except OSError as error:
        print(
            f"ERROR: Could not start process check: {error}",
            file=sys.stderr
        )
        return

    if(pid.returncode not in (0,1)):
        print(
            "ERROR: Could not check whether the application is running.",
            file=sys.stderr
        )
        return

    final_pids=pid.stdout.splitlines()

    for final_pid in final_pids:
        try:
            final_pid=int(final_pid)
            process=psutil.Process(final_pid)

            process.terminate()

            try:
                process.wait(timeout=2)
            except psutil.TimeoutExpired:
                print(
                    f"ERROR: PID {final_pid} did not terminate within the expected time.",
                    file=sys.stderr
                )

                try:
                    process.kill()
                    process.wait(timeout=2)
                except psutil.NoSuchProcess:
                    continue
                except psutil.AccessDenied:
                    print(
                        f"ERROR: Permission denied while forcing PID {final_pid} to terminate.",
                        file=sys.stderr
                    )
                    continue
                except psutil.Error as error:
                    print(
                        f"ERROR: Could not force PID {final_pid} to terminate: {error}",
                        file=sys.stderr
                    )
                    continue

        except ValueError:
            continue
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            print(
                f"ERROR: Permission denied while trying to terminate PID {final_pid}.",
                file=sys.stderr
            )
            continue
        except psutil.Error as error:
            print(
                f"ERROR: Could not terminate PID {final_pid}: {error}",
                file=sys.stderr
            )
            continue


# ============================================================
# WINDOWS
# ============================================================

def get_windows_start_menu_directories():
    directories=[]

    user_start_menu=os.path.join(
        os.environ.get("APPDATA",""),
        "Microsoft",
        "Windows",
        "Start Menu",
        "Programs"
    )

    common_start_menu=os.path.join(
        os.environ.get("PROGRAMDATA",""),
        "Microsoft",
        "Windows",
        "Start Menu",
        "Programs"
    )

    if(os.path.isdir(user_start_menu)):
        directories.append(user_start_menu)

    if(os.path.isdir(common_start_menu)):
        directories.append(common_start_menu)

    return directories


def get_windows_shortcut_target(shortcut_path):
    powershell_command=(
        "$shell=New-Object -ComObject WScript.Shell;"
        f"$shortcut=$shell.CreateShortcut('{shortcut_path}');"
        "Write-Output $shortcut.TargetPath"
    )

    try:
        result=subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                powershell_command
            ],
            capture_output=True,
            text=True
        )
    except OSError:
        return None

    if(result.returncode!=0):
        return None

    target=result.stdout.strip()

    if(not target):
        return None

    if(not target.lower().endswith(".exe")):
        return None

    if(not os.path.isfile(target)):
        return None

    return os.path.normpath(target)


def discover_windows_start_menu_apps():
    discovered=[]

    for directory in get_windows_start_menu_directories():
        for root,dirs,files in os.walk(directory):
            dirs[:]=[
                directory_name
                for directory_name in dirs
                if directory_name.lower() not in {
                    "startup",
                    "windows accessories",
                    "windows administrative tools"
                }
            ]

            for file_name in files:
                if(not file_name.lower().endswith(".lnk")):
                    continue

                shortcut_path=os.path.join(root,file_name)
                target=get_windows_shortcut_target(shortcut_path)

                if(not target):
                    continue

                app_name=os.path.splitext(file_name)[0].strip()

                if(not app_name):
                    continue

                discovered.append((app_name,target))

    return discovered


def discover_windows_executable_apps():
    discovered=[]

    program_directories=[]

    program_files=os.environ.get("ProgramFiles")
    program_files_x86=os.environ.get("ProgramFiles(x86)")
    local_app_data=os.environ.get("LOCALAPPDATA")

    if(program_files and os.path.isdir(program_files)):
        program_directories.append(program_files)

    if(program_files_x86 and os.path.isdir(program_files_x86)):
        program_directories.append(program_files_x86)

    if(local_app_data):
        local_programs=os.path.join(local_app_data,"Programs")

        if(os.path.isdir(local_programs)):
            program_directories.append(local_programs)

    for base_directory in program_directories:
        try:
            for root,dirs,files in os.walk(base_directory):
                depth=root[len(base_directory):].count(os.sep)

                if(depth>=3):
                    dirs[:]=[]

                for file_name in files:
                    if(not file_name.lower().endswith(".exe")):
                        continue

                    executable_path=os.path.join(root,file_name)

                    if(not os.path.isfile(executable_path)):
                        continue

                    app_name=os.path.splitext(file_name)[0].strip()

                    if(not app_name):
                        continue

                    discovered.append((app_name,executable_path))

        except OSError:
            continue

    return discovered


def discover_windows_apps():
    discovered=discover_windows_start_menu_apps()

    if(not discovered):
        discovered=discover_windows_executable_apps()

    unique_apps={}
    app_name_counts={}

    for app_name,app_path in discovered:
        normalized_path=os.path.normcase(os.path.normpath(app_path))
        key=(app_name,normalized_path)

        if(key in unique_apps):
            continue

        unique_apps[key]=app_path
        app_name_counts[app_name]=app_name_counts.get(app_name,0)+1

    for (app_name,normalized_path),app_path in unique_apps.items():
        if(app_name_counts[app_name]==1):
            final_list.append(app_name)
        else:
            parent_folder=os.path.basename(os.path.dirname(app_path))

            if(parent_folder):
                final_list.append([app_name,parent_folder])


def get_process_path_windows(selected_app):
    duplicate_app_name=selected_app
    parent_folder=None

    if(" | " in duplicate_app_name):
        duplicate_app_name,parent_folder=duplicate_app_name.split(" | ",1)

    discovered=discover_windows_start_menu_apps()

    if(not discovered):
        discovered=discover_windows_executable_apps()

    matches=[]

    for app_name,app_path in discovered:
        if(app_name.lower()!=duplicate_app_name.lower()):
            continue

        if(parent_folder):
            if(
                os.path.basename(os.path.dirname(app_path)).lower()
                ==parent_folder.lower()
            ):
                return app_path

        matches.append(app_path)

    if(len(matches)==1):
        return matches[0]

    return None


def terminate_running_processes_windows(app_path):
    normalized_target=os.path.normcase(os.path.normpath(app_path))

    for process in psutil.process_iter(["pid","name","exe"]):
        try:
            process_executable=process.info["exe"]

            if(not process_executable):
                continue

            normalized_process=os.path.normcase(
                os.path.normpath(process_executable)
            )

            if(normalized_process!=normalized_target):
                continue

            process.terminate()

            try:
                process.wait(timeout=2)
            except psutil.TimeoutExpired:
                print(
                    f"ERROR: PID {process.pid} did not terminate within the expected time.",
                    file=sys.stderr
                )

                try:
                    process.kill()
                    process.wait(timeout=2)
                except psutil.NoSuchProcess:
                    continue
                except psutil.AccessDenied:
                    print(
                        f"ERROR: Permission denied while forcing PID {process.pid} to terminate.",
                        file=sys.stderr
                    )
                    continue
                except psutil.Error as error:
                    print(
                        f"ERROR: Could not force PID {process.pid} to terminate: {error}",
                        file=sys.stderr
                    )
                    continue

        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            print(
                f"ERROR: Permission denied while trying to terminate PID {process.pid}.",
                file=sys.stderr
            )
            continue
        except psutil.Error as error:
            print(
                f"ERROR: Could not terminate PID {process.pid}: {error}",
                file=sys.stderr
            )
            continue


# ============================================================
# COMMON APP FUNCTIONS
# ============================================================

def get_process_path(selected_app):
    if(operating_system=="Darwin"):
        return get_process_path_macos(selected_app)

    elif(operating_system=="Windows"):
        return get_process_path_windows(selected_app)

    return None


def terminate_running_processes(app_path):
    if(operating_system=="Darwin"):
        terminate_running_processes_macos(app_path)

    elif(operating_system=="Windows"):
        terminate_running_processes_windows(app_path)

    else:
        print(
            f"ERROR: Operating system {operating_system} is not supported.",
            file=sys.stderr
        )


def block_schedule(schedule,app_paths):
    if(schedule.get("enabled",True) is False):
        return

    selected_app=schedule["app"]

    if(selected_app not in app_paths):
        app_path=get_process_path(selected_app)

        if(not app_path):
            print(
                f"ERROR: Could not find the application path for {selected_app}.",
                file=sys.stderr
            )
            return

        if(not os.path.isfile(app_path) and operating_system=="Windows"):
            print(
                f"ERROR: The application executable is no longer available for {selected_app}.",
                file=sys.stderr
            )
            return

        if(operating_system=="Darwin"):
            if(not os.path.isdir(app_path)):
                print(
                    f"ERROR: The application path is no longer available for {selected_app}.",
                    file=sys.stderr
                )
                return

            if(not os.path.isdir(f"{app_path}/Contents/MacOS")):
                print(
                    f"ERROR: Could not find the executable directory for {selected_app}.",
                    file=sys.stderr
                )
                return

        app_paths[selected_app]=app_path

    terminate_running_processes(app_paths[selected_app])


def discover_apps():
    if(operating_system=="Darwin"):
        discover_macos_apps()

    elif(operating_system=="Windows"):
        discover_windows_apps()

    else:
        print(
            f"ERROR: Operating system {operating_system} is not supported.",
            file=sys.stderr
        )
        sys.exit(1)


def discover_macos_apps():
    try:
        path=subprocess.run(
            ["mdfind","kMDItemContentType == 'com.apple.application-bundle'"],
            capture_output=True,
            text=True
        )
    except OSError as error:
        print(
            f"ERROR: Could not start application discovery: {error}",
            file=sys.stderr
        )
        sys.exit(1)

    if(path.returncode!=0):
        print(
            "ERROR: Could not discover installed applications.",
            file=sys.stderr
        )
        sys.exit(1)

    main_path=path.stdout.splitlines()

    for item in main_path:
        if(
            item.startswith("/Applications/")
            or item.startswith("/System/Applications/")
        ):
            parts=item.split("/")
            app_name=parts[-1]

            if(not app_name.endswith(".app")):
                continue

            app_name=app_name.removesuffix(".app")

            if(not app_name.strip()):
                continue

            main_list.append(app_name)

            if(app_name in dictionary):
                dictionary[app_name]+=1
                new_list_for_i.append([app_name,parts[-2]])
            else:
                dictionary[app_name]=1

    for item in main_list:
        if(dictionary[item]==1):
            final_list.append(item)

        elif(dictionary[item]>1):
            for iteration in new_list_for_i:
                if(
                    iteration[0]==item
                    and iteration not in processed
                ):
                    final_list.append([iteration[0],iteration[-1]])
                    processed.append(iteration)


def normalize_app_name(app):
    if(isinstance(app,list)):
        return app[0]+" | "+app[1]

    return app


# ============================================================
# PROGRAM START
# ============================================================

try:
    if(operating_system not in {"Darwin","Windows"}):
        print(
            f"ERROR: Operating system {operating_system} is not supported.",
            file=sys.stderr
        )
        sys.exit(1)

    discover_apps()

    if(len(sys.argv)>1 and sys.argv[1]=="--list-apps"):
        print(json.dumps(final_list),flush=True)
        sys.exit(0)

    try:
        data=json.load(sys.stdin)

        if(not isinstance(data,dict)):
            print(
                "ERROR: Invalid data received.",
                file=sys.stderr
            )
            sys.exit(1)

        schedules=data.get("schedules")

        if(not isinstance(schedules,list)):
            print(
                "ERROR: Invalid schedules received.",
                file=sys.stderr
            )
            sys.exit(1)

        for schedule in schedules:
            if(not validate_schedule(schedule)):
                print(
                    "ERROR: Invalid schedule received.",
                    file=sys.stderr
                )
                sys.exit(1)

    except json.JSONDecodeError:
        print(
            "ERROR: Could not read the data received from Electron.",
            file=sys.stderr
        )
        sys.exit(1)

    if(not schedules):
        print("ALLOWED",flush=True)
        sys.exit(0)

    available_apps=set()

    for item in final_list:
        available_apps.add(normalize_app_name(item))

    for schedule in schedules:
        if(schedule["app"] not in available_apps):
            print(
                f"ERROR: The selected application was not found: {schedule['app']}.",
                file=sys.stderr
            )
            sys.exit(1)

    app_paths={}
    announced_active=set()

    print(
        f"BLOCKER READY: Monitoring {len(schedules)} schedule(s).",
        flush=True
    )

    while True:
        current=dt.now()
        active_schedules=[]

        for schedule in schedules:
            if(schedule.get("enabled",True) is False):
                continue

            if(schedule_is_active(schedule,current)):
                active_schedules.append(schedule)

        for schedule in active_schedules:
            schedule_key=(
                schedule["id"],
                schedule["app"],
                schedule["start"],
                schedule["end"],
                schedule["type"],
                schedule.get("date"),
                tuple(schedule.get("days",[]))
            )

            if(schedule_key not in announced_active):
                print(
                    f"BLOCKING: {schedule['app']} from {schedule['start']} until {schedule['end']}.",
                    flush=True
                )
                announced_active.add(schedule_key)

            block_schedule(schedule,app_paths)

        if(not active_schedules):
            announced_active.clear()

        future_schedule_exists=False

        for schedule in schedules:
            if(schedule.get("enabled",True) is False):
                continue

            if(schedule["type"] in {"today","specific_date"}):
                schedule_date=get_date_from_string(schedule["date"])

                if(schedule_date and current.date()<=schedule_date):
                    future_schedule_exists=True
                    break

            elif(schedule["type"] in {"every_day","selected_days"}):
                future_schedule_exists=True
                break

        if(not future_schedule_exists):
            print("ALLOWED",flush=True)
            break

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