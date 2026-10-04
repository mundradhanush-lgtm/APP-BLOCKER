const app_selector=document.querySelector("#app_selector");
const status_message=document.querySelector("#status_message");
const home_view=document.querySelector("#home_view");
const add_schedule_view=document.querySelector("#add_schedule_view");
const add_schedule_button=document.querySelector("#add_schedule_button");
const save_schedule_button=document.querySelector("#save_schedule_button");
const cancel_schedule_button=document.querySelector("#cancel_schedule_button");
const schedule_list=document.querySelector("#schedule_list");
const no_schedules_message=document.querySelector("#no_schedules_message");
const schedule_type=document.querySelector("#schedule_type");
const selected_days_section=document.querySelector("#selected_days_section");
const specific_date_section=document.querySelector("#specific_date_section");
const specific_day=document.querySelector("#specific_day");
const specific_month=document.querySelector("#specific_month");
const specific_year=document.querySelector("#specific_year");
const start_time_section=document.querySelector("#start_time");
const end_time_section=document.querySelector("#end_time");
const start_hour=document.querySelector("#start_hour");
const start_minutes=document.querySelector("#start_minutes");
const start_ampm=document.querySelector("#start_ampm");
const end_hour=document.querySelector("#end_hour");
const end_minutes=document.querySelector("#end_minutes");
const end_ampm=document.querySelector("#end_ampm");
let schedules=[];
const error_style=document.createElement("style");
error_style.textContent=".validation_error{margin:0 0 0.75rem;color:#FF5C5C;font-size:0.875rem;font-weight:600;}";
document.head.append(error_style);
function showError(element,message){
    removeError(element);
    const error=document.createElement("p");
    error.classList.add("validation_error");
    error.textContent=message;
    element.parentNode.insertBefore(error,element);
}
function removeError(element){
    const previous=element.previousElementSibling;
    if(previous&&previous.classList.contains("validation_error")){
        previous.remove();
    }
}
function clearAllErrors(){
    document.querySelectorAll(".validation_error").forEach((error)=>{
        error.remove();
    });
}
window.electronAPI.receiveApps((app_list)=>{
    app_list.forEach((event)=>{
        const option=document.createElement("option");
        if(Array.isArray(event)){
            option.textContent=event[0]+" | "+event[1];
            option.value=event[0];
        }
        else{
            option.textContent=event;
            option.value=event;
        }
        app_selector.append(option);
    });
    if(app_list.length>0){
        status_message.textContent="Applications loaded. Add a schedule to begin.";
    }
    else{
        status_message.textContent="No applications were found.";
    }
});
window.electronAPI.receiveBlockerStatus((message)=>{
    status_message.textContent=message;
});
window.electronAPI.receiveBlockerError((message)=>{
    status_message.textContent=message;
});
window.electronAPI.receiveBlockerEnded((message)=>{
    status_message.textContent=message;
});
schedule_type.addEventListener("change",()=>{
    clearAllErrors();
    selected_days_section.hidden=schedule_type.value!=="selected_days";
    specific_date_section.hidden=schedule_type.value!=="specific_date";
});
add_schedule_button.addEventListener("click",()=>{
    home_view.hidden=true;
    add_schedule_view.hidden=false;
    status_message.textContent="Create a schedule for an application.";
});
cancel_schedule_button.addEventListener("click",()=>{
    add_schedule_view.hidden=true;
    home_view.hidden=false;
    resetForm();
    status_message.textContent="No changes were made.";
});
save_schedule_button.addEventListener("click",()=>{
    clearAllErrors();
    let has_error=false;
    if(app_selector.value===""){
        showError(app_selector,"Please select an application.");
        has_error=true;
    }
    let start_valid=true;
    let end_valid=true;
    if(start_hour.value===""||start_minutes.value===""){
        showError(start_time_section,"Please enter a complete start time.");
        has_error=true;
        start_valid=false;
    }
    else if(Number(start_hour.value)<1||Number(start_hour.value)>12||Number(start_minutes.value)<0||Number(start_minutes.value)>59){
        start_hour.value="";
        start_minutes.value="";
        showError(start_time_section,"Please enter a valid start time.");
        has_error=true;
        start_valid=false;
    }
    if(end_hour.value===""||end_minutes.value===""){
        showError(end_time_section,"Please enter a complete end time.");
        has_error=true;
        end_valid=false;
    }
    else if(Number(end_hour.value)<1||Number(end_hour.value)>12||Number(end_minutes.value)<0||Number(end_minutes.value)>59){
        end_hour.value="";
        end_minutes.value="";
        showError(end_time_section,"Please enter a valid end time.");
        has_error=true;
        end_valid=false;
    }
    if(schedule_type.value==="selected_days"){
        const day_checkboxes=selected_days_section.querySelectorAll('input[type="checkbox"]:checked');
        if(day_checkboxes.length===0){
            showError(selected_days_section,"Please select at least one day.");
            has_error=true;
        }
    }
    let selected_date=null;
    if(schedule_type.value==="specific_date"){
        specific_date_section.hidden=false;
        if(specific_day.value===""||specific_month.value===""||specific_year.value===""){
            specific_day.value="";
            specific_month.value="";
            specific_year.value="";
            showError(specific_date_section,"Please enter a complete date.");
            has_error=true;
        }
        else{
            const day=Number(specific_day.value);
            const month=Number(specific_month.value);
            const year=Number(specific_year.value);
            const selected_date_object=new Date(year,month-1,day);
            const today=new Date();
            today.setHours(0,0,0,0);
            if(!Number.isInteger(day)||!Number.isInteger(month)||!Number.isInteger(year)||String(year).length!==4||selected_date_object.getFullYear()!==year||selected_date_object.getMonth()!==month-1||selected_date_object.getDate()!==day){
                specific_day.value="";
                specific_month.value="";
                specific_year.value="";
                showError(specific_date_section,"Please enter a valid date.");
                has_error=true;
            }
            else{
                selected_date_object.setHours(0,0,0,0);
                if(selected_date_object<today){
                    specific_day.value="";
                    specific_month.value="";
                    specific_year.value="";
                    showError(specific_date_section,"The selected date cannot be before today.");
                    has_error=true;
                }
                else{
                    selected_date=String(day).padStart(2,"0")+"/"+String(month).padStart(2,"0")+"/"+year;
                }
            }
        }
    }
    if(start_valid&&end_valid){
        let sh=Number(start_hour.value);
        let sm=Number(start_minutes.value);
        let eh=Number(end_hour.value);
        let em=Number(end_minutes.value);
        if(start_ampm.value==="A.M."&&sh===12){
            sh=0;
        }
        if(start_ampm.value==="P.M."&&sh!==12){
            sh+=12;
        }
        if(end_ampm.value==="A.M."&&eh===12){
            eh=0;
        }
        if(end_ampm.value==="P.M."&&eh!==12){
            eh+=12;
        }
        const start_total_minutes=sh*60+sm;
        const end_total_minutes=eh*60+em;
        if(start_total_minutes===end_total_minutes){
            start_hour.value="";
            start_minutes.value="";
            end_hour.value="";
            end_minutes.value="";
            showError(start_time_section,"The blocking period cannot be 24 hours. Maximum allowed is 23 hours and 59 minutes.");
            has_error=true;
        }
        if(!has_error){
            const start_h=sh<10?"0"+sh:sh;
            const start_m=sm<10?"0"+sm:sm;
            const end_h=eh<10?"0"+eh:eh;
            const end_m=em<10?"0"+em:em;
            const start_time=start_h+":"+start_m;
            const end_time=end_h+":"+end_m;
            const selected_app=app_selector.value;
            const selected_days=[];
            if(schedule_type.value==="selected_days"){
                selected_days_section.querySelectorAll('input[type="checkbox"]:checked').forEach((checkbox)=>{
                    selected_days.push(checkbox.value);
                });
            }
            const schedule={
                "app":selected_app,
                "start":start_time,
                "end":end_time,
                "type":schedule_type.value,
                "days":selected_days,
                "date":selected_date
            };
            schedules.push(schedule);
            createScheduleBar(schedule);
            add_schedule_view.hidden=true;
            home_view.hidden=false;
            resetForm();
            status_message.textContent="Schedule saved successfully.";
        }
    }
});
function resetForm(){
    clearAllErrors();
    app_selector.selectedIndex=0;
    start_hour.value="";
    start_minutes.value="";
    start_ampm.selectedIndex=0;
    end_hour.value="";
    end_minutes.value="";
    end_ampm.selectedIndex=0;
    schedule_type.selectedIndex=0;
    specific_day.value="";
    specific_month.value="";
    specific_year.value="";
    selected_days_section.hidden=true;
    specific_date_section.hidden=true;
    selected_days_section.querySelectorAll('input[type="checkbox"]').forEach((checkbox)=>{
        checkbox.checked=false;
    });
}
function createScheduleBar(schedule){
    if(no_schedules_message){
        no_schedules_message.remove();
    }
    const schedule_bar=document.createElement("div");
    schedule_bar.classList.add("schedule_bar");
    const schedule_app=document.createElement("p");
    schedule_app.classList.add("schedule_app");
    schedule_app.textContent=schedule.app;
    const schedule_time=document.createElement("p");
    schedule_time.classList.add("schedule_time");
    schedule_time.textContent=convertToDisplayTime(schedule.start)+" → "+convertToDisplayTime(schedule.end);
    const schedule_type_text=document.createElement("p");
    schedule_type_text.classList.add("schedule_type");
    if(schedule.type==="today"){
        schedule_type_text.textContent="Today only";
    }
    else if(schedule.type==="specific_date"){
        schedule_type_text.textContent=schedule.date;
    }
    else if(schedule.type==="every_day"){
        schedule_type_text.textContent="Every day";
    }
    else if(schedule.type==="selected_days"){
        schedule_type_text.textContent=schedule.days.join(" • ");
    }
    schedule_bar.append(schedule_app);
    schedule_bar.append(schedule_time);
    schedule_bar.append(schedule_type_text);
    schedule_list.append(schedule_bar);
}
function convertToDisplayTime(time){
    const parts=time.split(":");
    let hour=Number(parts[0]);
    const minutes=parts[1];
    const ampm=hour>=12?"P.M.":"A.M.";
    if(hour===0){
        hour=12;
    }
    else if(hour>12){
        hour-=12;
    }
    return hour+":"+minutes+" "+ampm;
}