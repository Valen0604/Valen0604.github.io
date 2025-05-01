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

    if (whoCalled == "modalAccept") {
        document.cookie = "cookieAccepted=true; max-age=31536000; path=/";
    } else {
        document.cookie = "cookieAccepted=false; max-age=31536000; path=/";
        expireCookie();
    }

}

const IDs = ["firstname", "lastname", "socialsecurity", "zip", "email",
    "userID", "password", "password2", "city", "address1", "phone", "socialsecurity2",
    "socialsecurity3", "phone2", "phone3"];

function openModal() {
    var modal = document.getElementById("myModal");
    modal.style.display = "block";
}

function askCookie() {
    if (document.cookie.indexOf("cookieAccepted") == -1) {
        openModal();
    }
}

function expireCookie() {
    for (i = 0; i < IDs.length; i++) {
        document.cookie = IDs[i] + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        removeLocalStorage(IDs[i]);
    }
}

function removeLocalStorage(name) {
    localStorage.removeItem(name);
}
