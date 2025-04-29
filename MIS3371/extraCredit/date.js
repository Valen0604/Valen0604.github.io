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

var response;

function setCookie(cname, cvalue, exdays) {
    let checkbox = document.getElementById("remember");
    if (checkbox.checked == false) {
        document.cookie = cname + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        removeLocalStorage(cname);
    } else if (cvalue == "") {
        document.cookie = cname + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        removeLocalStorage(cname);
    } else {
        const d = new Date();
        d.setTime(d.getTime() + (exdays * 24 * 60 * 60 * 1000));
        let expires = "expires=" + d.toUTCString();
        if (cname == "firstname") {
            document.cookie = cname + "=" + cvalue + "; " + expires + "; path=/;";
        }
        setLocalStorage(cname, cvalue);
    }
}

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
        parent.openModal("Welcome again " + user + "\nDo you want to continue?");
        if (response == true) {
            for (i = 0; i < IDs.length; i++) {
                value = getLocalStorage(IDs[i]);
                document.getElementById(IDs[i]).value = value;
            }
        } else {
            for (let i = 0; i < IDs.length; i++) {
                document.cookie = IDs[i] + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                removeLocalStorage(IDs[i]);
            }
        }
    } else {
        parent.openModal("Welcome to the form! Please fill out the fields and click on submit when you are done.");
    }
}

function expireCookie() {
    let checkbox = document.getElementById("remember");
    if (!checkbox.checked) {
        for (let i = 0; i < IDs.length; i++) {
            document.cookie = IDs[i] + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
            removeLocalStorage(IDs[i]);
        }
    } else {
        for (let i = 0; i < IDs.length; i++) {
            if (document.getElementById(IDs[i]).value == "") {
                document.cookie = IDs[i] + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                removeLocalStorage(IDs[i]);
            } else {
                let value = document.getElementById(IDs[i]).value;
                setLocalStorage(IDs[i], value);
                setCookie("firstname", document.getElementById("firstname").value, 30);
            }
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

function openModal(message) {
    var modal = document.getElementById("myModal");
    var modalContent = document.getElementById("content");
    if(message == "Welcome to the form! Please fill out the fields and click on submit when you are done."){
    modalContent.innerHTML = message;
    modal.style.display = "block";
    } else {
        var div = document.getElementById("modalContent");
        div.innerHTML = "";
        div.innerHTML = '<p id="content"></p>;'
        modalContent.innerHTML = message;
        div.innerHTML += '<div id="modalClose"><input type="button" value="No" class="btn-close-popup" onclick="removeModal(); updateResponse(this.id)"></div>';
        div.innerHTML += '<div id="modalAccept"><input type="button" value="Yes" class="btn-accept-popup" onclick="removeModal(); updateResponse(this.id)"></div>';
        div.innerHTML += '<div id="modalContent"></div>';
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
        response = false;
    } else if (whoCalled == "modalAccept") {
        response = true;
    }
}
