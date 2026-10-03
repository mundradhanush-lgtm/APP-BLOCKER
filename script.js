const app_selector=document.querySelector("#app_selector");
const status_message=document.querySelector("#status_message");

window.electronAPI.receiveApps((app_list) => {
    app_list.forEach((event) => {
        const option = document.createElement("option");

        if (Array.isArray(event)) {
            option.textContent = event[0] + " | " + event[1];
        }
        else {
            option.textContent = event;
        }

        app_selector.append(option);
    });

    if(app_list.length>0){
        status_message.textContent="Applications loaded. Select an app and set a schedule.";
    }
    else{
        status_message.textContent="No applications were found.";
    }
});

const start_hour=document.querySelector("#start_hour");
const start_minutes=document.querySelector("#start_minutes");
const start_ampm=document.querySelector("#start_ampm");
const end_hour=document.querySelector("#end_hour");
const end_minutes=document.querySelector("#end_minutes");
const end_ampm=document.querySelector("#end_ampm");

start_hour.addEventListener("input", (event)=>{
    if(start_hour.value!=""){
        if(start_hour.value>12){
            alert("YOU CANNOT ENTER AN HOUR GREATER THAN 12 AS IT FOLLOWS A 12 HOUR SYSTEM");
            start_hour.value="";
        }
        else if(start_hour.value<=0){
            alert("YOU CANNOT ENTER AN HOUR EQUAL TO 0 OR LESS THAN THAT AS IT FOLLOWS A 12 HOUR SYSTEM");
            start_hour.value="";
        };
    };
});

start_minutes.addEventListener("input", (event)=>{
    if(start_minutes.value!=""){
        if(start_minutes.value>59){
            alert("YOU CANNOT ENTER MINUTES GREATER THAN 59 AS IT WOULD BE AN HOUR");
            start_minutes.value="";
        }
        else if(start_minutes.value<0){
            alert("YOU CANNOT ENTER A MINUTE LESS THAN 0 AS IT DOES NOT FOLLOWS THE FORMAT OF TIME");
            start_minutes.value="";
        };
    };
});

end_hour.addEventListener("input", (event)=>{
    if(end_hour.value!=""){
        if(end_hour.value>12){
            alert("YOU CANNOT ENTER AN HOUR GREATER THAN 12 AS IT FOLLOWS A 12 HOUR SYSTEM");
            end_hour.value="";
        }
        else if(end_hour.value<=0){
            alert("YOU CANNOT ENTER AN HOUR EQUAL TO 0 OR LESS THAN THAT AS IT FOLLOWS A 12 HOUR SYSTEM");
            end_hour.value="";
        };
    };
});

end_minutes.addEventListener("input", (event)=>{
    if(end_minutes.value!=""){
        if(end_minutes.value>59){
            alert("YOU CANNOT ENTER MINUTES GREATER THAN 59 AS IT WOULD BE AN HOUR");
            end_minutes.value="";
        }
        else if(end_minutes.value<0){
            alert("YOU CANNOT ENTER A MINUTE LESS THAN 0 AS IT DOES NOT FOLLOWS THE FORMAT OF TIME");
            end_minutes.value="";
        };
    };
});

const block_button=document.querySelector("#block_button");

block_button.addEventListener("click", (event)=>{
    if(start_hour.value!="" && start_minutes.value!="" && start_ampm.value!="" && end_hour.value!="" && end_minutes.value!="" && end_ampm.value!=""){
        let sh=Number(start_hour.value);
        let sm=Number(start_minutes.value);
        let eh=Number(end_hour.value);
        let em=Number(end_minutes.value);

        if(start_ampm.value==="A.M." && sh===12){
            sh=0;
        }

        if(start_ampm.value==="P.M." && sh!=12){
            sh=sh+12;
        }

        if(end_ampm.value==="A.M." && eh===12){
            eh=0;
        }

        if(end_ampm.value==="P.M." && eh!=12){
            eh=eh+12;
        }

        let start_h;
        let start_m;
        let end_h;
        let end_m;

        if(sh<10){
            start_h="0"+sh;
        }
        else{
            start_h=sh;
        }

        if(sm<10){
            start_m="0"+sm;
        }
        else{
            start_m=sm;
        }

        if(eh<10){
            end_h="0"+eh;
        }
        else{
            end_h=eh;
        }

        if(em<10){
            end_m="0"+em;
        }
        else{
            end_m=em;
        }

        let start_time=start_h+":"+start_m;
        let end_time=end_h+":"+end_m;

        let selected_app=app_selector.value;

        const main_obj={
            "app":selected_app,
            "start":start_time,
            "end":end_time
        };

        status_message.textContent="Blocking schedule sent. The application will be blocked during the selected time.";

        window.electronAPI.sendAppData(main_obj);
    }
    else{
        status_message.textContent="Please complete the application and time fields before blocking.";
    }
})