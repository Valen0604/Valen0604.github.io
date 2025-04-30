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

// from https://www.w3schools.com/js/tryit.asp?filename=tryjs_cookie_username

var response = true;
const IDs = ["firstname", "lastname", "socialsecurity", "zip", "email",
    "userID", "password", "password2", "city", "address1", "phone", "socialsecurity2",
    "socialsecurity3"];

function getCookie(cname) {
    let name = cname + "=";
    let decodedCookie = decodeURIComponent(document.cookie);
    let ca = decodedCookie.split(';');
    for (let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) == ' ') {
            c = c.substring(1);
        }
        if (c.indexOf(name) == 0) {
            return c.substring(name.length, c.length);
        }
    }
    return "";
}

function checkCookie() {
    let user = getCookie("firstname");
    console.log("cookie: " + user);
    if (user != "") {
        openModal("Welcome again " + user + ", do you want to continue from where you left off?");  
    } else {
        openModal("Welcome to the form! Please fill out the fields and click on submit when you are done.");
    }
}

function openModal(message) {
    var modal = document.getElementById("myModal");
    var modalContent = document.getElementById("content");
    if(message == "Welcome to the form! Please fill out the fields and click on submit when you are done."){
    modalContent.innerHTML = message;
    modal.style.display = "block";
    } else {
        var div = document.getElementById("modalContent");
        div.innerHTML = ""; // Clear existing content
        div.innerHTML = `<p id="content">${message}</p>`;
        div.innerHTML += `
            <div style="display: flex; justify-content: center; gap: 10px; margin-top: 10px;">
                <input type="button" id="modalClose" value="No" class="btn-close-popup" onclick="updateResponse(this.id); removeModal()">
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                <input type="button" id="modalAccept" value="Yes" class="btn-accept-popup" onclick="updateResponse(this.id); removeModal()">
            </div>`;
        modal.style.display = "block";
    }
}

function removeModal() {
    var modal = document.getElementById("myModal");
    modal.style.display = "none";
}

function updateResponse(caller) {
    var whoCalled = caller;
    if (whoCalled == "modalClose") {
        for (let i = 0; i < IDs.length; i++) {
            setCookie(IDs[i], getLocalStorage(IDs[i]), -1);
        }
    } else if (whoCalled == "modalAccept") {
        for (i = 0; i < IDs.length; i++) {
            setCookie(IDs[i], getLocalStorage(IDs[i]), 1);
        }
    }
}

function setLocalStorage(name, value) {
    let checkbox = document.getElementById("remember");
    if (!checkbox.checked || value == "") {
        removeLocalStorage(name);
    } else {
        localStorage.setItem(name, value);
    }
}

function getLocalStorage(name) {
    return localStorage.getItem(name);
}

function removeLocalStorage(name) {
    localStorage.removeItem(name);
}
