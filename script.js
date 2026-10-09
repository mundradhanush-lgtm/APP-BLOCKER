
const app_selector = document.querySelector("#app_selector");
const status_message = document.querySelector("#status_message");
const home_view = document.querySelector("#home_view");
const add_schedule_view = document.querySelector("#add_schedule_view");
const add_schedule_button = document.querySelector("#add_schedule_button");
const save_schedule_button = document.querySelector("#save_schedule_button");
const cancel_schedule_button = document.querySelector("#cancel_schedule_button");
const schedule_list = document.querySelector("#schedule_list");
const no_schedules_message = document.querySelector("#no_schedules_message");
const schedule_type = document.querySelector("#schedule_type");
const selected_days_section = document.querySelector("#selected_days_section");
const specific_date_section = document.querySelector("#specific_date_section");
const specific_day = document.querySelector("#specific_day");
const specific_month = document.querySelector("#specific_month");
const specific_year = document.querySelector("#specific_year");
const start_time_section = document.querySelector("#start_time");
const end_time_section = document.querySelector("#end_time");
const start_hour = document.querySelector("#start_hour");
const start_minutes = document.querySelector("#start_minutes");
const start_ampm = document.querySelector("#start_ampm");
const end_hour = document.querySelector("#end_hour");
const end_minutes = document.querySelector("#end_minutes");
const end_ampm = document.querySelector("#end_ampm");

let schedules = [];
let selected_app_for_another_schedule = null;
let editing_schedule_id = null;

const error_style = document.createElement("style");

error_style.textContent = `
    .validation_error {
        margin: 0 0 0.75rem;
        color: #FF5C5C;
        font-size: 0.875rem;
        font-weight: 600;
    }

    .schedule_bar {
        position: relative;
    }

    .schedule_menu_button {
        position: absolute;
        top: 0.75rem;
        right: 0.75rem;
        width: 2rem;
        height: 2rem;
        margin: 0;
        padding: 0;
        background: transparent;
        color: #AEBBCB;
        font-size: 1.5rem;
        font-weight: 700;
        line-height: 1;
        border: none;
        border-radius: 0.375rem;
    }

    .schedule_menu_button:hover {
        background-color: #304863;
        color: #F5F7FB;
    }

    .schedule_menu_button:active {
        transform: none;
    }

    .schedule_menu {
        position: absolute;
        top: 3rem;
        right: 0.75rem;
        z-index: 10;
        min-width: 8.5rem;
        padding: 0.375rem;
        background-color: #17263B;
        border: 1px solid #304863;
        border-radius: 0.5rem;
        box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.3);
    }

    .schedule_menu button {
        height: 2.25rem;
        margin: 0;
        background: transparent;
        color: #F5F7FB;
        text-align: left;
        font-size: 0.875rem;
        font-weight: 500;
    }

    .schedule_menu button:hover {
        background-color: #304863;
    }

    .schedule_menu button:active {
        transform: none;
    }

    .schedule_disabled {
        opacity: 0.55;
    }

    .schedule_status {
        margin: 0.375rem 0 0;
        color: #FF5C5C;
        font-size: 0.8125rem;
        font-weight: 600;
    }

    .schedule_disabled .schedule_time {
        color: #AEBBCB;
    }
`;

document.head.append(error_style);

const add_another_schedule_button = document.createElement("button");

add_another_schedule_button.id = "add_another_schedule_button";
add_another_schedule_button.textContent = "+ ADD ANOTHER SCHEDULE";
add_another_schedule_button.type = "button";

add_schedule_view
    .querySelector("section:last-child")
    .insertBefore(add_another_schedule_button, save_schedule_button);

function showError(element, message) {
    removeError(element);

    const error = document.createElement("p");

    error.classList.add("validation_error");
    error.textContent = message;

    element.parentNode.insertBefore(error, element);
}

function removeError(element) {
    const previous = element.previousElementSibling;

    if (previous && previous.classList.contains("validation_error")) {
        previous.remove();
    }
}

function clearAllErrors() {
    document.querySelectorAll(".validation_error").forEach((error) => {
        error.remove();
    });
}

function getTimeInMinutes(hour, minutes, ampm) {
    let converted_hour = Number(hour);

    if (ampm === "A.M." && converted_hour === 12) {
        converted_hour = 0;
    }

    if (ampm === "P.M." && converted_hour !== 12) {
        converted_hour += 12;
    }

    return converted_hour * 60 + Number(minutes);
}

function timeStringToMinutes(time) {
    const parts = time.split(":");

    return Number(parts[0]) * 60 + Number(parts[1]);
}

function minutesToTimeString(minutes) {
    minutes = ((minutes % 1440) + 1440) % 1440;

    const hour = Math.floor(minutes / 60);
    const minute = minutes % 60;

    return String(hour).padStart(2, "0") + ":" +
        String(minute).padStart(2, "0");
}

function getDateFromString(date_string) {
    const parts = date_string.split("/");

    return new Date(
        Number(parts[2]),
        Number(parts[1]) - 1,
        Number(parts[0])
    );
}

function formatDate(date) {
    return String(date.getDate()).padStart(2, "0") + "/" +
        String(date.getMonth() + 1).padStart(2, "0") + "/" +
        date.getFullYear();
}

function dateOnly(date) {
    return new Date(
        date.getFullYear(),
        date.getMonth(),
        date.getDate()
    );
}

function addDays(date, days) {
    const result = new Date(date);

    result.setDate(result.getDate() + days);

    return dateOnly(result);
}

function getWeekdayName(date) {
    return [
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday"
    ][date.getDay()];
}

function scheduleStartsOnDate(schedule, date) {
    if (schedule.enabled === false) {
        return false;
    }

    const normalized_date = dateOnly(date);
    const weekday = getWeekdayName(normalized_date);

    if (schedule.type === "every_day") {
        return true;
    }

    if (schedule.type === "today") {
        return schedule.date === formatDate(normalized_date);
    }

    if (schedule.type === "specific_date") {
        return schedule.date === formatDate(normalized_date);
    }

    if (schedule.type === "selected_days") {
        return Array.isArray(schedule.days) &&
            schedule.days.includes(weekday);
    }

    return false;
}

function getIntervalsForDate(schedule, date) {
    const intervals = [];
    const date_without_time = dateOnly(date);
    const previous_date = addDays(date_without_time, -1);

    const start = timeStringToMinutes(schedule.start);
    const end = timeStringToMinutes(schedule.end);

    if (scheduleStartsOnDate(schedule, date_without_time)) {
        if (start < end) {
            intervals.push([start, end]);
        } else {
            intervals.push([start, 1440]);
        }
    }

    if (
        scheduleStartsOnDate(schedule, previous_date) &&
        start > end
    ) {
        intervals.push([0, end]);
    }

    return intervals;
}

function intervalsOverlap(first, second) {
    return first[0] < second[1] &&
        second[0] < first[1];
}

function getCandidateDates(first, second) {
    const dates = [];
    const today = dateOnly(new Date());

    const addCandidate = (date) => {
        const key = formatDate(date);

        if (!dates.some((item) => formatDate(item) === key)) {
            dates.push(date);
        }
    };

    const addAround = (date) => {
        addCandidate(addDays(date, -1));
        addCandidate(date);
        addCandidate(addDays(date, 1));
    };

    const addScheduleDates = (schedule) => {
        if (
            schedule.type === "today" ||
            schedule.type === "specific_date"
        ) {
            if (schedule.date) {
                addAround(getDateFromString(schedule.date));
            }

            return;
        }

        for (let i = -14; i <= 28; i++) {
            addCandidate(addDays(today, i));
        }
    };

    addScheduleDates(first);
    addScheduleDates(second);

    return dates;
}

function schedulesHaveExactConflict(existing, new_schedule) {
    if (existing.id === new_schedule.id) {
        return false;
    }

    if (existing.app !== new_schedule.app) {
        return false;
    }

    const candidate_dates = getCandidateDates(
        existing,
        new_schedule
    );

    return candidate_dates.some((date) => {
        const existing_intervals = getIntervalsForDate(
            existing,
            date
        );

        const new_intervals = getIntervalsForDate(
            new_schedule,
            date
        );

        return existing_intervals.some((first_interval) =>
            new_intervals.some((second_interval) =>
                intervalsOverlap(first_interval, second_interval)
            )
        );
    });
}

function getConflictMessage(existing, new_schedule) {
    return "This schedule overlaps with an existing blocking schedule for " +
        existing.app +
        ". Choose a different time or schedule period.";
}

function findScheduleConflict(new_schedule) {
    for (const existing_schedule of schedules) {
        if (
            schedulesHaveExactConflict(
                existing_schedule,
                new_schedule
            )
        ) {
            return existing_schedule;
        }
    }

    return null;
}

function renderScheduleList() {
    schedule_list.innerHTML = "";

    const sorted_schedules = [...schedules].sort((a, b) => {
        const app_compare = a.app.localeCompare(
            b.app,
            undefined,
            { sensitivity: "base" }
        );

        if (app_compare !== 0) {
            return app_compare;
        }

        return timeStringToMinutes(a.start) -
            timeStringToMinutes(b.start);
    });

    if (sorted_schedules.length === 0) {
        const message = document.createElement("p");

        message.id = "no_schedules_message";
        message.textContent = "No schedules have been created yet.";

        schedule_list.append(message);

        return;
    }

    sorted_schedules.forEach((schedule) => {
        createScheduleBar(schedule);
    });
}

window.electronAPI.receiveApps((app_list) => {
    if (!Array.isArray(app_list)) {
        status_message.textContent =
            "Could not load the application list.";

        return;
    }

    app_selector.innerHTML = "";

    const placeholder = document.createElement("option");

    placeholder.value = "";
    placeholder.textContent = "Select an application";
    app_selector.append(placeholder);

    app_list.sort((a, b) => {
        const app_a = Array.isArray(a) ? a[0] : a;
        const app_b = Array.isArray(b) ? b[0] : b;

        return app_a.localeCompare(
            app_b,
            undefined,
            { sensitivity: "base" }
        );
    });

    app_list.forEach((event) => {
        const option = document.createElement("option");

        if (Array.isArray(event)) {
            option.textContent = event[0] + " | " + event[1];
            option.value = event[0] + " | " + event[1];
        } else {
            option.textContent = event;
            option.value = event;
        }

        app_selector.append(option);
    });

    if (app_list.length > 0) {
        status_message.textContent =
            "Applications loaded. Add a schedule to begin.";
    } else {
        status_message.textContent =
            "No applications were found.";
    }
});

window.electronAPI.receiveSchedules((saved_schedules) => {
    if (Array.isArray(saved_schedules)) {
        schedules = saved_schedules;
        renderScheduleList();
    }
});

window.electronAPI.receiveBlockerStatus((message) => {
    status_message.textContent = message;
});

window.electronAPI.receiveBlockerError((message) => {
    status_message.textContent = message;
});

window.electronAPI.receiveBlockerEnded((message) => {
    status_message.textContent = message;
});

schedule_type.addEventListener("change", () => {
    clearAllErrors();

    selected_days_section.hidden =
        schedule_type.value !== "selected_days";

    specific_date_section.hidden =
        schedule_type.value !== "specific_date";
});

add_schedule_button.addEventListener("click", () => {
    selected_app_for_another_schedule = null;
    editing_schedule_id = null;

    save_schedule_button.textContent = "SAVE SCHEDULE";
    add_another_schedule_button.hidden = false;

    home_view.hidden = true;
    add_schedule_view.hidden = false;

    resetForm();

    status_message.textContent =
        "Create a schedule for an application.";
});

add_another_schedule_button.addEventListener("click", () => {
    saveCurrentSchedule(false);
});

cancel_schedule_button.addEventListener("click", () => {
    add_schedule_view.hidden = true;
    home_view.hidden = false;

    selected_app_for_another_schedule = null;
    editing_schedule_id = null;

    save_schedule_button.textContent = "SAVE SCHEDULE";
    add_another_schedule_button.hidden = false;

    resetForm();

    status_message.textContent = "No changes were made.";
});

save_schedule_button.addEventListener("click", () => {
    saveCurrentSchedule(true);
});

function saveCurrentSchedule(return_home) {
    clearAllErrors();

    let has_error = false;

    if (app_selector.value === "") {
        showError(app_selector, "Please select an application.");
        has_error = true;
    }

    let start_valid = true;
    let end_valid = true;

    if (start_hour.value === "" || start_minutes.value === "") {
        showError(
            start_time_section,
            "Please enter a complete start time."
        );

        has_error = true;
        start_valid = false;
    } else if (
        Number(start_hour.value) < 1 ||
        Number(start_hour.value) > 12 ||
        Number(start_minutes.value) < 0 ||
        Number(start_minutes.value) > 59
    ) {
        start_hour.value = "";
        start_minutes.value = "";

        showError(
            start_time_section,
            "Please enter a valid start time."
        );

        has_error = true;
        start_valid = false;
    }

    if (end_hour.value === "" || end_minutes.value === "") {
        showError(
            end_time_section,
            "Please enter a complete end time."
        );

        has_error = true;
        end_valid = false;
    } else if (
        Number(end_hour.value) < 1 ||
        Number(end_hour.value) > 12 ||
        Number(end_minutes.value) < 0 ||
        Number(end_minutes.value) > 59
    ) {
        end_hour.value = "";
        end_minutes.value = "";

        showError(
            end_time_section,
            "Please enter a valid end time."
        );

        has_error = true;
        end_valid = false;
    }

    if (schedule_type.value === "selected_days") {
        const day_checkboxes =
            selected_days_section.querySelectorAll(
                'input[type="checkbox"]:checked'
            );

        if (day_checkboxes.length === 0) {
            showError(
                selected_days_section,
                "Please select at least one day."
            );

            has_error = true;
        }
    }

    let selected_date = null;

    if (schedule_type.value === "today") {
        selected_date = formatDate(new Date());
    }

    if (schedule_type.value === "specific_date") {
        if (
            specific_day.value === "" ||
            specific_month.value === "" ||
            specific_year.value === ""
        ) {
            specific_day.value = "";
            specific_month.value = "";
            specific_year.value = "";

            showError(
                specific_date_section,
                "Please enter a complete date."
            );

            has_error = true;
        } else {
            const day = Number(specific_day.value);
            const month = Number(specific_month.value);
            const year = Number(specific_year.value);

            const selected_date_object =
                new Date(year, month - 1, day);

            const today = new Date();

            today.setHours(0, 0, 0, 0);

            if (
                !Number.isInteger(day) ||
                !Number.isInteger(month) ||
                !Number.isInteger(year) ||
                String(year).length !== 4 ||
                selected_date_object.getFullYear() !== year ||
                selected_date_object.getMonth() !== month - 1 ||
                selected_date_object.getDate() !== day
            ) {
                specific_day.value = "";
                specific_month.value = "";
                specific_year.value = "";

                showError(
                    specific_date_section,
                    "Please enter a valid date."
                );

                has_error = true;
            } else {
                selected_date_object.setHours(0, 0, 0, 0);

                if (selected_date_object < today) {
                    specific_day.value = "";
                    specific_month.value = "";
                    specific_year.value = "";

                    showError(
                        specific_date_section,
                        "The selected date cannot be before today."
                    );

                    has_error = true;
                } else {
                    selected_date =
                        String(day).padStart(2, "0") + "/" +
                        String(month).padStart(2, "0") + "/" +
                        year;
                }
            }
        }
    }

    if (has_error || !start_valid || !end_valid) {
        return false;
    }

    const start_total_minutes = getTimeInMinutes(
        start_hour.value,
        start_minutes.value,
        start_ampm.value
    );

    const end_total_minutes = getTimeInMinutes(
        end_hour.value,
        end_minutes.value,
        end_ampm.value
    );

    if (start_total_minutes === end_total_minutes) {
        start_hour.value = "";
        start_minutes.value = "";
        end_hour.value = "";
        end_minutes.value = "";

        showError(
            start_time_section,
            "The blocking period cannot be 24 hours. " +
            "Maximum allowed is 23 hours and 59 minutes."
        );

        return false;
    }

    const start_h = Math.floor(start_total_minutes / 60);
    const start_m = start_total_minutes % 60;

    const end_h = Math.floor(end_total_minutes / 60);
    const end_m = end_total_minutes % 60;

    const start_time =
        String(start_h).padStart(2, "0") + ":" +
        String(start_m).padStart(2, "0");

    const end_time =
        String(end_h).padStart(2, "0") + ":" +
        String(end_m).padStart(2, "0");

    const selected_app = app_selector.value;
    const selected_days = [];

    if (schedule_type.value === "selected_days") {
        selected_days_section
            .querySelectorAll('input[type="checkbox"]:checked')
            .forEach((checkbox) => {
                selected_days.push(checkbox.value);
            });
    }

    const was_editing = editing_schedule_id !== null;

    const new_schedule = {
        id: editing_schedule_id ||
            Date.now().toString() +
            Math.random().toString(36).slice(2),

        app: selected_app,
        start: start_time,
        end: end_time,
        type: schedule_type.value,
        days: selected_days,
        date: selected_date,

        enabled: editing_schedule_id
            ? getExistingEnabledState(editing_schedule_id)
            : true
    };

    const conflict = findScheduleConflict(new_schedule);

    if (conflict) {
        showError(
            schedule_type,
            getConflictMessage(conflict, new_schedule)
        );

        return false;
    }

    if (editing_schedule_id) {
        const index = schedules.findIndex(
            (schedule) => schedule.id === editing_schedule_id
        );

        if (index !== -1) {
            schedules[index] = new_schedule;
        }
    } else {
        schedules.push(new_schedule);
    }

    renderScheduleList();

    window.electronAPI.sendAppData({
        schedules: schedules
    });

    selected_app_for_another_schedule = selected_app;

    if (return_home) {
        add_schedule_view.hidden = true;
        home_view.hidden = false;

        editing_schedule_id = null;

        save_schedule_button.textContent = "SAVE SCHEDULE";
        add_another_schedule_button.hidden = false;

        resetForm();

        status_message.textContent = was_editing
            ? "Schedule updated successfully."
            : "Schedule saved successfully.";
    } else {
        editing_schedule_id = null;

        save_schedule_button.textContent = "SAVE SCHEDULE";
        add_another_schedule_button.hidden = false;

        resetForm();

        app_selector.value = selected_app;

        add_schedule_view.hidden = false;
        home_view.hidden = true;

        status_message.textContent =
            "Schedule saved. Create another schedule for " +
            selected_app + ".";
    }

    return true;
}

function getExistingEnabledState(id) {
    const existing = schedules.find(
        (schedule) => schedule.id === id
    );

    return existing ? existing.enabled !== false : true;
}

function resetForm() {
    clearAllErrors();

    if (selected_app_for_another_schedule) {
        app_selector.value = selected_app_for_another_schedule;
    } else {
        app_selector.selectedIndex = 0;
    }

    start_hour.value = "";
    start_minutes.value = "";
    start_ampm.selectedIndex = 0;

    end_hour.value = "";
    end_minutes.value = "";
    end_ampm.selectedIndex = 0;

    schedule_type.selectedIndex = 0;

    specific_day.value = "";
    specific_month.value = "";
    specific_year.value = "";

    selected_days_section.hidden = true;
    specific_date_section.hidden = true;

    selected_days_section
        .querySelectorAll('input[type="checkbox"]')
        .forEach((checkbox) => {
            checkbox.checked = false;
        });
}

function createScheduleBar(schedule) {
    const schedule_bar = document.createElement("div");

    schedule_bar.classList.add("schedule_bar");

    if (schedule.enabled === false) {
        schedule_bar.classList.add("schedule_disabled");
    }

    const schedule_app = document.createElement("p");

    schedule_app.classList.add("schedule_app");
    schedule_app.textContent = schedule.app;

    const schedule_time = document.createElement("p");

    schedule_time.classList.add("schedule_time");
    schedule_time.textContent =
        convertToDisplayTime(schedule.start) +
        " → " +
        convertToDisplayTime(schedule.end);

    const schedule_type_text = document.createElement("p");

    schedule_type_text.classList.add("schedule_type");

    if (schedule.type === "today") {
        schedule_type_text.textContent =
            "Today only • " + schedule.date;
    } else if (schedule.type === "specific_date") {
        schedule_type_text.textContent = schedule.date;
    } else if (schedule.type === "every_day") {
        schedule_type_text.textContent = "Every day";
    } else if (schedule.type === "selected_days") {
        schedule_type_text.textContent =
            schedule.days.join(" • ");
    }

    if (schedule.enabled === false) {
        const disabled_status = document.createElement("p");

        disabled_status.classList.add("schedule_status");
        disabled_status.textContent = "DISABLED";

        schedule_bar.append(disabled_status);
    }

    const menu_button = document.createElement("button");

    menu_button.classList.add("schedule_menu_button");
    menu_button.type = "button";
    menu_button.textContent = "⋮";
    menu_button.setAttribute("aria-label", "Schedule options");

    const menu = document.createElement("div");

    menu.classList.add("schedule_menu");
    menu.hidden = true;

    const disable_button = document.createElement("button");

    disable_button.type = "button";
    disable_button.textContent =
        schedule.enabled === false ? "Enable" : "Disable";

    const edit_button = document.createElement("button");

    edit_button.type = "button";
    edit_button.textContent = "Edit";

    const delete_button = document.createElement("button");

    delete_button.type = "button";
    delete_button.textContent = "Delete";

    menu.append(disable_button, edit_button, delete_button);

    menu_button.addEventListener("click", (event) => {
        event.stopPropagation();

        document.querySelectorAll(".schedule_menu").forEach(
            (other_menu) => {
                if (other_menu !== menu) {
                    other_menu.hidden = true;
                }
            }
        );

        menu.hidden = !menu.hidden;
    });

    menu.addEventListener("click", (event) => {
        event.stopPropagation();
    });

    disable_button.addEventListener("click", () => {
        toggleSchedule(schedule.id);
        menu.hidden = true;
    });

    edit_button.addEventListener("click", () => {
        editSchedule(schedule.id);
        menu.hidden = true;
    });

    delete_button.addEventListener("click", () => {
        deleteSchedule(schedule.id);
        menu.hidden = true;
    });

    schedule_bar.append(
        menu_button,
        menu,
        schedule_app,
        schedule_time,
        schedule_type_text
    );

    schedule_list.append(schedule_bar);
}

function toggleSchedule(id) {
    const schedule = schedules.find(
        (item) => item.id === id
    );

    if (!schedule) {
        return;
    }

    schedule.enabled = schedule.enabled === false;

    window.electronAPI.sendAppData({
        schedules: schedules
    });

    renderScheduleList();

    status_message.textContent = schedule.enabled
        ? "Schedule enabled for " + schedule.app + "."
        : "Schedule disabled for " + schedule.app + ".";
}

function editSchedule(id) {
    const schedule = schedules.find(
        (item) => item.id === id
    );

    if (!schedule) {
        return;
    }

    editing_schedule_id = id;
    selected_app_for_another_schedule = null;

    home_view.hidden = true;
    add_schedule_view.hidden = false;

    save_schedule_button.textContent = "UPDATE SCHEDULE";
    add_another_schedule_button.hidden = true;

    app_selector.value = schedule.app;

    const start_minutes_total =
        timeStringToMinutes(schedule.start);

    const end_minutes_total =
        timeStringToMinutes(schedule.end);

    fillTimeFields(
        start_minutes_total,
        start_hour,
        start_minutes,
        start_ampm
    );

    fillTimeFields(
        end_minutes_total,
        end_hour,
        end_minutes,
        end_ampm
    );

    schedule_type.value = schedule.type;

    selected_days_section.hidden =
        schedule.type !== "selected_days";

    specific_date_section.hidden =
        schedule.type !== "specific_date";

    selected_days_section
        .querySelectorAll('input[type="checkbox"]')
        .forEach((checkbox) => {
            checkbox.checked =
                Array.isArray(schedule.days) &&
                schedule.days.includes(checkbox.value);
        });

    if (schedule.type === "specific_date" && schedule.date) {
        const parts = schedule.date.split("/");

        specific_day.value = Number(parts[0]);
        specific_month.value = Number(parts[1]);
        specific_year.value = Number(parts[2]);
    } else {
        specific_day.value = "";
        specific_month.value = "";
        specific_year.value = "";
    }

    clearAllErrors();

    status_message.textContent =
        "Editing schedule for " + schedule.app + ".";
}

function fillTimeFields(
    total_minutes,
    hour_element,
    minute_element,
    ampm_element
) {
    const hour_24 = Math.floor(total_minutes / 60);
    const minute = total_minutes % 60;

    const ampm = hour_24 >= 12 ? "P.M." : "A.M.";

    let hour = hour_24 % 12;

    if (hour === 0) {
        hour = 12;
    }

    hour_element.value = hour;
    minute_element.value = minute;
    ampm_element.value = ampm;
}

function deleteSchedule(id) {
    const schedule = schedules.find(
        (item) => item.id === id
    );

    if (!schedule) {
        return;
    }

    const confirmed = window.confirm(
        "Delete the schedule for " + schedule.app + "?"
    );

    if (!confirmed) {
        return;
    }

    schedules = schedules.filter(
        (item) => item.id !== id
    );

    window.electronAPI.sendAppData({
        schedules: schedules
    });

    renderScheduleList();

    status_message.textContent = "Schedule deleted.";
}

document.addEventListener("click", () => {
    document.querySelectorAll(".schedule_menu").forEach(
        (menu) => {
            menu.hidden = true;
        }
    );
});

function convertToDisplayTime(time) {
    const parts = time.split(":");

    let hour = Number(parts[0]);
    const minutes = parts[1];

    const ampm = hour >= 12 ? "P.M." : "A.M.";

    if (hour === 0) {
        hour = 12;
    } else if (hour > 12) {
        hour -= 12;
    }
    return hour + ":" + minutes + " " + ampm;
}
window.electronAPI.requestSchedules();