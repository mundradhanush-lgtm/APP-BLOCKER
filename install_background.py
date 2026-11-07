import os
import sys
import plistlib
import subprocess
from pathlib import Path

LABEL="com.appblocker.background"
HOME=Path.home()
LAUNCH_AGENTS=HOME/"Library"/"LaunchAgents"
LOGS=HOME/"Library"/"Logs"
PLIST_PATH=LAUNCH_AGENTS/f"{LABEL}.plist"

if(sys.platform!="darwin"):
    sys.exit(0)

if(len(sys.argv)>1):
    blocker_argument=sys.argv[1]
else:
    blocker_argument=str(Path(__file__).resolve().parent/"app_blocker.py")

blocker_path=Path(blocker_argument).expanduser()

if(blocker_path.is_absolute() and blocker_path.exists()):
    if(blocker_path.suffix==".py"):
        program_arguments=[sys.executable,str(blocker_path)]
    else:
        program_arguments=[str(blocker_path)]
else:
    fallback=Path(__file__).resolve().parent/"app_blocker.py"
    if(not fallback.exists()):
        print("ERROR: App Blocker background executable was not found.",file=sys.stderr)
        sys.exit(1)
    program_arguments=[sys.executable,str(fallback)]

LAUNCH_AGENTS.mkdir(parents=True,exist_ok=True)
LOGS.mkdir(parents=True,exist_ok=True)

plist={
    "Label":LABEL,
    "ProgramArguments":program_arguments,
    "RunAtLoad":True,
    "KeepAlive":True,
    "ProcessType":"Background",
    "StandardOutPath":str(LOGS/"AppBlocker.log"),
    "StandardErrorPath":str(LOGS/"AppBlocker-error.log")
}

with open(PLIST_PATH,"wb") as file:
    plistlib.dump(plist,file)

subprocess.run(
    ["launchctl","bootout",f"gui/{os.getuid()}/{LABEL}"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

result=subprocess.run(
    ["launchctl","bootstrap",f"gui/{os.getuid()}",str(PLIST_PATH)],
    capture_output=True,
    text=True
)

if(result.returncode!=0):
    retry=subprocess.run(
        ["launchctl","kickstart","-k",f"gui/{os.getuid()}/{LABEL}"],
        capture_output=True,
        text=True
    )
    if(retry.returncode!=0):
        print(result.stderr or retry.stderr,file=sys.stderr)
        sys.exit(1)