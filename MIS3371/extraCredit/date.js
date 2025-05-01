/*
    Program name: Script_1.js
    Author: Valentino Javier Salerni Longo
    Date created: 04/19/2025
    Date last edited:
    Version: 1.0
    Description: Date Script. */
const a = new Date();

let year2 = a.getFullYear();
let month2 = a.getMonth() + 1;
let day2 = a.getDate();

document.getElementById("date").innerHTML = day2 + "/" + month2 + "/" + year2;

function removeModal(whoCalled) {
    var modal = document.getElementById("myModal");
    modal.style.display = "none";

    if(whoCalled == "modalAccept") {
        document.cookie = "cookieAccepted=true; max-age=31536000; path=/";
    } else {
        document.cookie = "cookieAccepted=false; max-age=31536000; path=/";
    }

}

function openModal() {
    var modal = document.getElementById("myModal");
    modal.style.display = "block";
}

function askCookie() {
    if (document.cookie.indexOf("cookieAccepted") == -1) {
        openModal();
    }
}
