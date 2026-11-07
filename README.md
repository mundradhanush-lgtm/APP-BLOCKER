# APP BLCOKER(macOS)

This is my first app, Multi-App-Blocker.
So, this an application that only runs only on macOS which blocks apps according to the time schedule set by the user. I made this app because I saw a lot of children, including myself spending a lot of time on their laptops doing unproductive activities. So, I took the initiative and built this APP BLOCKER that can also act as a children's lock in many parents' life.

## FEATURES

So, there are many features of App Blocker and they are:-

- It shows all the downloaded applications of your mac in the dropdown from where you can select the app which you want to block.

![picture showing a dropdown of all the downloaded applications in your mac that can be blocked](DROPDOWN_OF_APPS.jpg) 

So, this is the dropdown of all the downloaded applications on your mac that can be blocked.

- You can set time according to you. The maximum limit of the time schedule is 23 hours and 59 minutes, so you cannot block the app for more than this time period.

![a picture showing the placeholders for start and end time](TIME_PLACEHOLDERS.jpg)

- You can select the type of schedule also. There would be a dropdown where you have to just click and you would see options like ***Every day***, ***Today only***, ***Select Date***, and ***Select Day***

![picture showing the dropdown of schedule types](DROPDOWN_OF_SCHEDULE_TYPE.jpg)

- The coolest feature is that you can add multiple schedules for a single application, but the schedules should not overlap the previous schedules of the same app.

![adding multiple schedules feature screenshot](ADD_ANOTHER_SCHEDULE_BUTTON.jpg)

So, this is the button from where you can add another scedule for the same app.

![the interface after clicking on the *Add another schedule* button](INTERFACE_AFTER_ADD_ANOTHER_SCHEDULE.jpg)
 
So, in this image, you can see the interface which would be shown just after you click on *Add another schedule* button.

![picture of the screen which comes after you have completed the details of the other schedules also and clicked on the *Save* button](INTERFACE_AFTER_MULTIPLE_SCHEDULES_ARE_SAVED.jpg)

So, in this image, you can see the interface that appears when you have completed the details of the other schedules as well and click on save.

- Another feature is that it can even run while you have your App Blocker closed or you have just restarted the system. However one condition is this that if you have a schedule that is blocking an app currently and you restrt your system or turn on your system after shutting down, then the App Blocker would take around 5-10 minutes to block the app.

## Installation

Downloading and Installing App Blocker is very simple. Basically you have to click [here](https://github.com/mundradhanush-lgtm/APP-BLOCKER/releases/download/v1.0.0/App.Blocker-1.0.0-arm64.dmg) to download the .dmg file of app blocker and as you're on mac, you can just drag it to the applications folder to install it and turn it into a real application and your App Blocker is ready to be used!

## How To Use

1. Open App Blocker.
2. Click on **Add an App to Block** button.
3. Select the application you want to block from the dropdown menu.
4. Set the start time and the end time.
5. Choose the schedule type.
6. If you want more than one schedule for the same application, then you can click on **Add Another Schedule** button and enter the additional schedule details.
7. Click on **Save Schedule** button to save your schedules.

## Technologies Used

To make this App Blocker, I used ***Python***, ***JavaScript*** and ***JSON*** for the backend and ***HTML***, ***CSS***, ***JavaScript*** and ***JSON*** for the frontend. I wrote the code of json and some code of javascript because I built App Blocker with the help of ***Electron***.

## Feature Planned

In the future, I am planning to safelock this app with the help of a password that the user can set because of the security reasons. Also as this app acts as a. children's lock, it needs to be protected be the children and for that password is the best solution.

Thank You so much for reading it till here.