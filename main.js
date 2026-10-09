const{app,BrowserWindow,ipcMain}=require("electron");
const path=require("path");
const fs=require("fs");
const {spawn}=require("child_process");

let main_window=null;
let is_quitting=false;

const schedules_file=path.join(
    app.getPath("home"),
    "Library",
    "Application Support",
    "python-projects",
    "schedules.json"
);

const applications_file=path.join(
    app.getPath("userData"),
    "applications.json"
);

function createWindow(){
    main_window=new BrowserWindow({
        width:1000,
        height:700,
        minWidth:850,
        minHeight:600,
        show:false,
        webPreferences:{
            preload:path.join(__dirname,"preload.js"),
            contextIsolation:true,
            nodeIntegration:false
        }
    });

    main_window.loadFile("index.html");

    main_window.once("ready-to-show",()=>{
        loadSavedApplications();
        main_window.show();
    });

    main_window.on("close",(event)=>{
        if(!is_quitting){
            event.preventDefault();
            main_window.hide();
        }
    });
}

function saveSchedules(schedules){
    try{
        fs.mkdirSync(path.dirname(schedules_file),{recursive:true});
        fs.writeFileSync(schedules_file,JSON.stringify(schedules,null,2),"utf8");
    }
    catch(error){
        console.error("Could not save schedules:",error);
    }
}

function loadSchedules(){
    try{
        if(!fs.existsSync(schedules_file)){
            return [];
        }

        const schedules=JSON.parse(fs.readFileSync(schedules_file,"utf8"));
        return Array.isArray(schedules)?schedules:[];
    }
    catch(error){
        console.error("Could not load schedules:",error);
        return [];
    }
}

function getBlockerPath(){
    const packaged_path=path.join(process.resourcesPath,"app_blocker");

    if(app.isPackaged&&fs.existsSync(packaged_path)){
        return{command:packaged_path,args:[]};
    }

    return{
        command:"python3",
        args:[path.join(__dirname,"app_blocker.py")]
    };
}

function getInstallerPath(){
    const packaged_path=path.join(process.resourcesPath,"install_background.py");

    if(app.isPackaged&&fs.existsSync(packaged_path)){
        return packaged_path;
    }

    return path.join(__dirname,"install_background.py");
}

function loadSavedApplications(){
    try{
        if(!fs.existsSync(applications_file)){
            return;
        }

        const apps=JSON.parse(fs.readFileSync(applications_file,"utf8"));

        if(Array.isArray(apps)&&main_window&&!main_window.isDestroyed()){
            main_window.webContents.send("apps-found",apps);
        }
    }
    catch(error){
        console.error("Could not load saved applications:",error);
    }
}

function loadApplications(){
    const blocker=getBlockerPath();
    const blocker_process=spawn(blocker.command,[...blocker.args,"--list-apps"],{
        stdio:["ignore","pipe","pipe"]
    });

    let output="";

    blocker_process.stdout.on("data",(data)=>{
        output+=data.toString();
    });

    blocker_process.stderr.on("data",(data)=>{
        console.error("Application discovery error:",data.toString());
    });

    blocker_process.on("close",(code)=>{
        try{
            if(code!==0){
                throw new Error(`Application discovery exited with code ${code}`);
            }

            const apps=JSON.parse(output);
            fs.mkdirSync(path.dirname(applications_file),{recursive:true});
            fs.writeFileSync(applications_file,JSON.stringify(apps,null,2),"utf8");

            if(main_window&&!main_window.isDestroyed()){
                main_window.webContents.send("apps-found",apps);
            }
        }
        catch(error){
            console.error("Could not load applications:",error);
        }
    });
}

function startBackgroundInstaller(){
    const installer_path=getInstallerPath();

    if(!fs.existsSync(installer_path)){
        console.error("Background installer not found:",installer_path);
        return;
    }

    const blocker=getBlockerPath();

    const installer=spawn("python3",[installer_path,blocker.command],{
        detached:true,
        stdio:"ignore"
    });

    installer.on("error",(error)=>{
        console.error("Could not start background installer:",error);
    });

    installer.unref();
}

function sendSchedulesToBackground(){
    const schedules=loadSchedules();

    if(main_window&&!main_window.isDestroyed()){
        main_window.webContents.send("schedules-loaded",schedules);
    }

}

ipcMain.on("load-schedules",()=>{
    sendSchedulesToBackground();
});

ipcMain.on("block-app",(event,data)=>{
    if(!data||!Array.isArray(data.schedules)){
        return;
    }

    saveSchedules(data.schedules);
});

app.whenReady().then(()=>{
    startBackgroundInstaller();
    createWindow();

    main_window.webContents.once("did-finish-load",()=>{
        loadApplications();
        sendSchedulesToBackground();
    });
});

app.on("before-quit",()=>{
    is_quitting=true;
});

app.on("window-all-closed",()=>{});

app.on("activate",()=>{
    if(main_window){
        main_window.show();
        main_window.focus();
    }
});