/**
 * Created by dolbin on 4/18/17.
 */

//////////////////////////
//                      //
//  CLOCK FUNCTIONS     //
//                      //
//////////////////////////

function setUpClock(){
    let today = new Date();
    let day = today.getDay();
    let daynum = today.getDate();
    let month = today.getMonth();
    let year = today.getFullYear();
    let dayName = disambiguateDay(day);
    let monthName = disambuguateMonth(month);
    let hours = today.getHours();
    let minutes = today.getMinutes();
    let seconds = today.getSeconds();
    let ampm = hours >= 12 ? 'PM' : 'AM';

    hours = hours % 12;
    hours = hours ? hours : 12; // the hour '0' should be '12'

    // add a zero in front of numbers<10
    minutes = checkTime(minutes);
    seconds = checkTime(seconds);
    document.getElementById('clockTime').innerHTML = hours + ":" + minutes + ":" + seconds + " "+ampm;
    document.getElementById('writtenTime').innerHTML = dayName + " " + monthName + " " + daynum +  ", " + year ;
    let t = setTimeout(setUpClock, 500);
}
function checkTime(i) {
    //add zeros in front of time values less than 10
    if (i < 10) {
        i = "0" + i;
    }
    return i;
}
function disambiguateDay(day) {

    let dayName = "";

    switch (day) {
        case 0:
            dayName = "Sunday";
            break;
        case 1:
            dayName = "Monday";
            break;
        case 2:
            dayName = "Tuesday";
            break;
        case 3:
            dayName = "Wednesday";
            break;
        case 4:
            dayName = "Thursday";
            break;
        case 5:
            dayName = "Friday";
            break;
        case 6:
            dayName = "Saturday";
            break;
        default:
            dayName = "Error: Day Field not in [0,6] ";
            break;
    }
    return dayName;
}
function disambuguateMonth(month) {
    let monthName = "";
    switch (month) {
        case 0:
            monthName = "January";
            break;
        case 1:
            monthName = "February";
            break;
        case 2:
            monthName = "March";
            break;
        case 3:
            monthName = "April";
            break;
        case 4:
            monthName = "May";
            break;
        case 5:
            monthName = "June";
            break;
        case 6:
            monthName = "July";
            break;
        case 7:
            monthName = "August";
            break;
        case 8:
            monthName = "September";
            break;
        case 9:
            monthName = "October";
            break;
        case 10:
            monthName = "November";
            break;
        case 11:
            monthName = "December";
            break;
        default:
            monthName = "Error: Month Field not in [1,12] ";
            break;
    }
    return monthName;
}

////////////////////////
//                    //
//     STATEMENTS     //
//                    //
////////////////////////
window.onload = setUpClock();

