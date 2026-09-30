from datetime import datetime as dt
import psutil
import subprocess

dictionary={}
main_list=[]
new_list_for_i=[]
processed=[]
final_list=[]
numbered_apps={}
try:
    start_hours=int(input("Please enter the start time hours: "))
    start_minutes=int(input("Please enter the start time minutes: "))
    start_am_pm=input("Please enter the start time indicator: ").upper()
    end_hours=int(input("Please enter the end time hours: "))
    end_minutes=int(input("Please enter the end time minutes: "))
    end_am_pm=input("Please enter the end time indicator: ").upper()
    start=dt.strptime(f"{start_hours}:{start_minutes} {start_am_pm}", "%I:%M %p").time()
    end=dt.strptime(f"{end_hours}:{end_minutes} {end_am_pm}", "%I:%M %p").time()
    current=dt.now().time()

    if(current>=start and current<end):
        
        path=subprocess.run([f"mdfind","kMDItemContentType == 'com.apple.application-bundle'"],
            capture_output=True,
            text=True
        )
        main_path=path.stdout
        main_path=main_path.splitlines()

        for i in main_path:
            if(i.startswith("/Applications/") or i.startswith("/System/Applications/")):
                i=i.split("/")
                path=i[-1]
                path=path.split(".app")
                main_app=path[-2]
                main_list.append(main_app)
                if(main_app in dictionary):
                    dictionary [main_app] += 1
                    new_list_for_i.append([main_app, i[-2]])
                elif(main_app not in dictionary):
                    dictionary [main_app] = 1
                else:
                    continue
        for i2 in main_list:
            if(dictionary [i2]==1):
                final_list.append(i2)
            elif(dictionary [i2]>1):
                for iteration in new_list_for_i:
                    if(iteration[0] == i2 and iteration not in processed):
                        final_list.append([iteration[0], iteration[-1]])
                        processed.append(iteration)

        for number, apps in enumerate(final_list, start=1):

            numbered_apps[number] = apps

            if isinstance(apps, list):
                print(number, ":", apps[0], "—", apps[1])
            else:
                print(number, ":", apps)

        input_of_apps_to_be_blocked=int(input("PLEASE ENTER THE NUMBER CORRESPONDING TO THE APP YOU WANT ME TO BE BLOCKED: "))

        if(isinstance(numbered_apps[input_of_apps_to_be_blocked], list)):
            duplicate_app_name=numbered_apps[input_of_apps_to_be_blocked][-2]
        else:
           duplicate_app_name=numbered_apps[input_of_apps_to_be_blocked]

        app_path=subprocess.run(["mdfind", f"kMDItemFSName == '{duplicate_app_name}.app'"],
            capture_output=True,
            text=True
        )
        a=app_path.stdout.splitlines()
       
        if(len(a)==1):
            app_path=app_path.stdout.strip()
        else:
            for check in a:
                if(numbered_apps[input_of_apps_to_be_blocked][-1] in check):
                    app_path=check
        
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