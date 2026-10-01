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

    main_path=path.stdout.splitlines()

    for i in main_path:
        if i.startswith("/Applications/") or i.startswith("/System/Applications/"):
            i = i.split("/")
            path = i[-1]
            path = path.split(".app")
            main_app = path[-2]
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

    data=json.load(sys.stdin)
    selected_app=data["app"]
    start_time=data["start"]
    end_time=data["end"]

    start=dt.strptime(start_time, "%H:%M").time()
    end=dt.strptime(end_time, "%H:%M").time()
    current=dt.now().time()

    if(current>=start and current<end):

        duplicate_app_name=selected_app

        if " | " in duplicate_app_name:
            duplicate_app_name, parent_folder = duplicate_app_name.split(" | ", 1)

            app_path=subprocess.run(
                ["mdfind", f"kMDItemFSName == '{duplicate_app_name}.app'"],
                capture_output=True,
                text=True
            )

            a=app_path.stdout.splitlines()

            for check in a:
                if f"/{parent_folder}/" in check:
                    app_path=check
                    break
        else:
            app_path=subprocess.run(
                ["mdfind", f"kMDItemFSName == '{duplicate_app_name}.app'"],
                capture_output=True,
                text=True
            )

            a=app_path.stdout.splitlines()

            if len(a)==1:
                app_path=a[0]
            else:
                for check in a:
                    if check.endswith(f"/{duplicate_app_name}.app"):
                        app_path=check
                        break
                
        pid=subprocess.run(["pgrep", "-f", f"{app_path}/Contents/MacOS/"],
            capture_output=True,
            text=True
        )

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

            final_pid=pid.stdout

            if(final_pid==""):
                final_pid=0
            else:
                final_pid=int(final_pid)
                name=psutil.Process(final_pid)
                name.terminate()
        
    else:
        print("ALLOWED")
except KeyboardInterrupt:
    exit()