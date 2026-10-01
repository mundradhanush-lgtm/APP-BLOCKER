from datetime import datetime as dt
import psutil
import subprocess
import sys
import json

dictionary = {}
main_list = []
new_list_for_i = []
processed = []
final_list = []
try:
    path=subprocess.run(["mdfind", "kMDItemContentType == 'com.apple.application-bundle'"],
    capture_output=True,
    text=True
)
    if path.returncode != 0:
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

            if main_app in dictionary:
                dictionary[main_app] += 1
                new_list_for_i.append([main_app, i[-2]])
            else:
                dictionary[main_app] = 1

    for i2 in main_list:
        if dictionary[i2] == 1:
            final_list.append(i2)
        elif dictionary[i2] > 1:
            for iteration in new_list_for_i:
                if iteration[0] == i2 and iteration not in processed:
                    final_list.append([iteration[0], iteration[-1]])
                    processed.append(iteration)

    if len(sys.argv) > 1 and sys.argv[1] == "--list-apps":
        print(json.dumps(final_list), flush=True)
        exit()

    try:
        data = json.load(sys.stdin)

        if not isinstance(data, dict):
            print("ERROR: Invalid data received.", file=sys.stderr)
            exit()

        if "app" not in data or "start" not in data or "end" not in data:
            print("ERROR: Missing required blocking information.", file=sys.stderr)
            exit()

        allowed_keys = {"app", "start", "end"}

        if set(data.keys()) != allowed_keys:
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

    if(current>=start and current<end):

        duplicate_app_name=selected_app

        if(" | " in duplicate_app_name):
            duplicate_app_name, parent_folder = duplicate_app_name.split(" | ", 1)

            app_path=subprocess.run(["mdfind", f"kMDItemFSName == '{duplicate_app_name}.app'"],
                capture_output=True,
                text=True
            )

            if(app_path.returncode != 0):
                print(f"ERROR: Could not search for the application {selected_app}.", file=sys.stderr)
                exit()

            a=app_path.stdout.splitlines()

            for check in a:
                if(f"/{parent_folder}/" in check and check.endswith(f"/{duplicate_app_name}.app")):
                    app_path = check
                    break

        else:
            app_path=subprocess.run(["mdfind", f"kMDItemFSName == '{duplicate_app_name}.app'"],
                capture_output=True,
                text=True
            )

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
                
        pid=subprocess.run(["pgrep", "-f", f"{app_path}/Contents/MacOS/"],
            capture_output=True,
            text=True
        )

        if pid.returncode not in (0, 1):
            print("ERROR: Could not check whether the application is running.", file=sys.stderr)
            exit()

        final_pid=pid.stdout

        if(final_pid==""):
            print(f"THE APP IS CLOSED AND YOU WOULD NOT BE ABLE TO USE THAT UNTIL {end}")
        else:
            print(f"THIS APP IS ALREADY RUNNING SO IT WILL BE TERMINATED AND YOU WOULD NOT BE ABLE TO USE IT UNTIL {end}")
        
        while(current>=start and current<end):
            current=dt.now().time()

            pid=subprocess.run(["pgrep", "-f", f"{app_path}/Contents/MacOS/"],
                capture_output=True,
                text=True
            )

            if pid.returncode not in (0, 1):
                print("ERROR: Could not check whether the application is running.", file=sys.stderr)
                break

            final_pid=pid.stdout

            if(final_pid==""):
                final_pid=0
            else:
                final_pid=int(final_pid)
                try:
                    name=psutil.Process(final_pid)
                    name.terminate()
                except psutil.NoSuchProcess:
                    continue
                except psutil.AccessDenied:
                    print(f"ERROR: Permission denied while trying to terminate PID {final_pid}.", file=sys.stderr)
                    continue
        
    else:
        print("ALLOWED")
except KeyboardInterrupt:
    exit()