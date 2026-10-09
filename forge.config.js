module.exports={
    packagerConfig:{
        name:"App Blocker",
        executableName:"app-blocker",
        extraResource:[
            "dist/app_blocker",
            "install_background.py"
        ]
    },
    makers:[
        {
            name:"@electron-forge/maker-dmg"
        }
    ]
}