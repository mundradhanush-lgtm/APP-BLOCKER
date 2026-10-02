from datetime import datetime as dt
import psutil
import subprocess
import sys
import json
import os

dictionary = {}
main_list = []
new_list_for_i = []
processed = []
final_list = []
try:
    try:
        path=subprocess.run(["mdfind", "kMDItemContentType == 'com.apple.application-bundle'"],
            capture_output=True,
            text=True
        )
    except OSError as error:
        print(f"ERROR: Could not start application discovery: {error}", file=sys.stderr)
        exit()

    if(path.returncode != 0):
        print("ERROR: Could not discover installed applications.", file=sys.stderr)
        exit()

    main_path=path.stdout.splitlines()

    for i in main_path:
        if(i.startswith("/Applications/") or i.startswith("/System/Applications/")):
            i = i.split("/")
            path = i[-1]
            if(not path.endswith(".app")):
                continue
            path = path.removesuffix(".app")
            main_app = path
            if(not main_app.strip()):
                continue
            main_list.append(main_app)

            if(main_app in dictionary):
                dictionary[main_app] += 1
                new_list_for_i.append([main_app, i[-2]])
            else:
                dictionary[main_app] = 1

    for i2 in main_list:
        if(dictionary[i2] == 1):
            final_list.append(i2)
        elif dictionary[i2] > 1:
            for iteration in new_list_for_i:
                if(iteration[0] == i2 and iteration not in processed):
                    final_list.append([iteration[0], iteration[-1]])
                    processed.append(iteration)

    if(len(sys.argv) > 1 and sys.argv[1] == "--list-apps"):
        print(json.dumps(final_list), flush=True)
        exit()

    try:
        data = json.load(sys.stdin)

        if(not isinstance(data, dict)):
            print("ERROR: Invalid data received.", file=sys.stderr)
            exit()

        if("app" not in data or "start" not in data or "end" not in data):
            print("ERROR: Missing required blocking information.", file=sys.stderr)
            exit()

        allowed_keys = {"app", "start", "end"}

        if(set(data.keys()) != allowed_keys):
            print("ERROR: Unexpected blocking information received.", file=sys.stderr)
            exit()

        selected_app = data["app"]
        start_time = data["start"]
        end_time = data["end"]

        if(not isinstance(selected_app, str) or not selected_app.strip()):
            print("ERROR: Invalid application.", file=sys.stderr)
            exit()

        if(not isinstance(start_time, str) or not isinstance(end_time, str)):
            print("ERROR: Invalid schedule.", file=sys.stderr)
            exit()

        if(selected_app not in final_list):
            print("ERROR: The selected application was not found.", file=sys.stderr)
            exit()

    except json.JSONDecodeError:
        print("ERROR: Could not read the data received from Electron.", file=sys.stderr)
        exit()

    try:
        start = dt.strptime(start_time, "%H:%M").time()
        end = dt.strptime(end_time, "%H:%M").time()
    except ValueError:
        print("ERROR: Invalid time format. Expected HH:MM.", file=sys.stderr)
        exit()

    current=dt.now().time()

    if(start<end):
        blocking_time = current>=start and current<end
    else:
        blocking_time = current>=start or current<end

    if(blocking_time):

        duplicate_app_name=selected_app

        if(" | " in duplicate_app_name):
            duplicate_app_name, parent_folder = duplicate_app_name.split(" | ", 1)

            try:
                app_path=subprocess.run(
                    ["mdfind", f"kMDItemFSName == '{duplicate_app_name}.app'"],
                    capture_output=True,
                    text=True
                )
            except OSError as error:
                print(f"ERROR: Could not start application search: {error}", file=sys.stderr)
                exit()

            if(app_path.returncode != 0):
                print(f"ERROR: Could not search for the application {selected_app}.", file=sys.stderr)
                exit()

            a=app_path.stdout.splitlines()

            for check in a:
                if(f"/{parent_folder}/" in check and check.endswith(f"/{duplicate_app_name}.app")):
                    app_path = check
                    break

        else:
            try:
                app_path=subprocess.run(
                    ["mdfind", f"kMDItemFSName == '{duplicate_app_name}.app'"],
                    capture_output=True,
                    text=True
                )
            except OSError as error:
                print(f"ERROR: Could not start application search: {error}", file=sys.stderr)
                exit()

            if(app_path.returncode != 0):
                print(f"ERROR: Could not search for the application {selected_app}.", file=sys.stderr)
                exit()

            a=app_path.stdout.splitlines()

            if(len(a)==1):
                app_path=a[0]
            else:
                for check in a:
                    if check.endswith(f"/{duplicate_app_name}.app"):
                        app_path=check
                        break

        if(not isinstance(app_path, str) or not app_path.strip()):
            print(f"ERROR: Could not find the application path for {selected_app}.", file=sys.stderr)
            exit()

        if(not os.path.isdir(app_path)):
            print(f"ERROR: The application path is no longer available for {selected_app}.", file=sys.stderr)
            exit()

        if(not os.path.isdir(f"{app_path}/Contents/MacOS")):
            print(f"ERROR: Could not find the executable directory for {selected_app}.", file=sys.stderr)
            exit()
                
        try:
            pid=subprocess.run(
                ["pgrep", "-f", f"{app_path}/Contents/MacOS/"],
                capture_output=True,
                text=True
            )
        except OSError as error:
            print(f"ERROR: Could not start process check: {error}", file=sys.stderr)
            exit()

        if(pid.returncode not in (0, 1)):
            print("ERROR: Could not check whether the application is running.", file=sys.stderr)
            exit()

        final_pids=pid.stdout.splitlines()

        if(not final_pids):
            print(f"THE APP IS CLOSED AND YOU WOULD NOT BE ABLE TO USE THAT UNTIL {end}")
        else:
            print(f"THIS APP IS ALREADY RUNNING SO IT WILL BE TERMINATED AND YOU WOULD NOT BE ABLE TO USE IT UNTIL {end}")
                
        while(True):

            current=dt.now().time()

            if(start<end):
                blocking_time = current>=start and current<end
            else:
                blocking_time = current>=start or current<end

            if(not blocking_time):
                break

            try:
                pid=subprocess.run(
                    ["pgrep", "-f", f"{app_path}/Contents/MacOS/"],
                    capture_output=True,
                    text=True
                )
            except OSError as error:
                print(f"ERROR: Could not start process check: {error}", file=sys.stderr)
                break

            if(pid.returncode not in (0, 1)):
                print("ERROR: Could not check whether the application is running.", file=sys.stderr)
                break

            final_pids=pid.stdout.splitlines()

            for final_pid in final_pids:
                try:
                    final_pid=int(final_pid)
                    process=psutil.Process(final_pid)
                    process.terminate()

                    try:
                        process.wait(timeout=2)
                    except psutil.TimeoutExpired:
                        print(f"ERROR: PID {final_pid} did not terminate within the expected time.", file=sys.stderr)

                        try:
                            process.kill()
                            process.wait(timeout=2)
                        except psutil.NoSuchProcess:
                            continue
                        except psutil.AccessDenied:
                            print(f"ERROR: Permission denied while forcing PID {final_pid} to terminate.", file=sys.stderr)
                            continue
                        except psutil.Error as error:
                            print(f"ERROR: Could not force PID {final_pid} to terminate: {error}", file=sys.stderr)
                            continue

                except ValueError:
                    continue
                except psutil.NoSuchProcess:
                    continue
                except psutil.AccessDenied:
                    print(f"ERROR: Permission denied while trying to terminate PID {final_pid}.", file=sys.stderr)
                    continue
                except psutil.Error as error:
                    print(f"ERROR: Could not terminate PID {final_pid}: {error}", file=sys.stderr)
                    continue
        
    else:
        print("ALLOWED")

except KeyboardInterrupt:
    exit()

except OSError as error:
    print(f"ERROR: Operating system error: {error}", file=sys.stderr)
    exit()

except Exception as error:
    print(f"ERROR: Unexpected error: {error}", file=sys.stderr)
    exit()