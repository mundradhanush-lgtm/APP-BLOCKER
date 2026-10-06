const { app, BrowserWindow, ipcMain } = require("electron");
const { spawn } = require("child_process");
let blocker_process=null;
function createWindow(){
    const window=new BrowserWindow({
        width:900,
        height:700,
        webPreferences:{
            preload:__dirname+"/preload.js"
        }
    });
    window.loadFile("index.html");
}
function getApps(){
    const python=spawn("python3",["app_blocker.py","--list-apps"]);
    let output="";
    python.stdout.on("data",(data)=>{
        output+=data.toString();
    });
    python.stderr.on("data",(error)=>{
        console.error(`Python Error: ${error}`);
    });
    python.on("error",(error)=>{
        console.error(`Could not start Python: ${error}`);
    });
    python.on("close",(code)=>{
        if(code!==0){
            console.error(`Python failed with exit code: ${code}`);
            return;
        }
        try{
            const apps=JSON.parse(output);
            const window=BrowserWindow.getAllWindows()[0];
            if(window){
                window.webContents.send("apps-found",apps);
            }
        }
        catch(error){
            console.error("Could not read the app list from Python:",error);
        }
    });
}
function stopBlocker(){
    if(blocker_process&&!blocker_process.killed){
        try{
            blocker_process.kill();
        }
        catch(error){
            console.error("Could not stop the previous blocker process:",error);
        }
    }
    blocker_process=null;
}
function startBlocker(data,event){
    stopBlocker();
    if(!data||!Array.isArray(data.schedules)||data.schedules.length===0){
        event.sender.send("blocker-ended","No active schedules. The application blocker has stopped.");
        return;
    }
    const python=spawn("python3",["app_blocker.py"]);
    blocker_process=python;
    python.stdout.on("data",(output)=>{
        const message=output.toString().trim();
        if(message){
            event.sender.send("blocker-status",message);
        }
        console.log(`Python: ${output}`);
    });
    python.stderr.on("data",(error)=>{
        const message=error.toString().trim();
        if(message){
            event.sender.send("blocker-error",message);
        }
        console.error(`Python Error: ${error}`);
    });
    python.stdin.on("error",(error)=>{
        console.error(`Python input error: ${error}`);
    });
    python.on("error",(error)=>{
        console.error(`Could not start Python: ${error}`);
        event.sender.send("blocker-error","Could not start the application blocker.");
        blocker_process=null;
    });
    python.on("close",(code)=>{
        if(code===0){
            event.sender.send("blocker-ended","The application blocker has stopped.");
        }
        else{
            console.error(`Python blocker failed with exit code: ${code}`);
        }
        if(blocker_process===python){
            blocker_process=null;
        }
    });
    try{
        python.stdin.write(JSON.stringify(data));
        python.stdin.end();
    }
    catch(error){
        console.error("Could not send data to Python:",error);
        event.sender.send("blocker-error","Could not send the blocking information to Python.");
    }
}
app.whenReady().then(()=>{
    createWindow();
    getApps();
});
ipcMain.on("block-app",(event,data)=>{
    if(!data||typeof data!=="object"){
        console.error("Invalid data received from the GUI.");
        return;
    }
    console.log(`Updating blocker with ${Array.isArray(data.schedules)?data.schedules.length:0} schedule(s).`);
    console.log("Schedules:",JSON.stringify(data.schedules||[],null,2));
    startBlocker(data,event);
});
app.on("window-all-closed",()=>{
    if(process.platform!=="darwin"){
        stopBlocker();
        app.quit();
    }
});
app.on("before-quit",()=>{
    stopBlocker();
});