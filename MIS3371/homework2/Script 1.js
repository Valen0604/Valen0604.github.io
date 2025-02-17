/*
    Program name: Script_1.js
    Author: Valentino Javier Salerni Longo
    Date created: 02/17/2025
    Date last edited:
    Version: 1.0
    Description: Script that shows the current date for homework 2. */

const d = new Date();

let year = d.getFullYear();
let month = d.getMonth() + 1;
let day = d.getDate();

document.getElementById("date").innerHTML = day + "/" + month + "/" + year;

/* Obtained from https://www.geeksforgeeks.org/password-matching-using-javascript/ */

function checkPassword(form) {
    password1 = form.password.value;
    password2 = form.password2.value;

    if(password1 == "")
        alert("Please enter a password.");
    else if(password2 == "")
        alert("Please enter the password again.");
    else if(password1 != password2){
        alert("The passwords do not match. Please try again.");
        return false;
    }
    else {
        return true;
    }
}
/* From: https://www.w3schools.com/howto/howto_js_rangeslider.asp */
var slider = document.getElementById("pain");
var output = document.getElementById("pain_value");
output.innerHTML = slider.value;

slider.oninput = function() {
    output.innerHTML = this.value;
}
