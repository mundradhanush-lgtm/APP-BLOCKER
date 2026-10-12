module.exports={
    packagerConfig:{
        name:"App Blocker",
        executableName:"app-blocker",
        extraResource: [
            "dist/app_blocker"
        ]
    },
    makers:[
        {
            name:"@electron-forge/maker-dmg"
        }
    ]
}