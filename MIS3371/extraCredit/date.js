/*
    Program name: Script_1.js
    Author: Valentino Javier Salerni Longo
    Date created: 04/19/2025
    Date last edited:
    Version: 1.0
    Description: Date Script. */
const d = new Date();

let year = d.getFullYear();
let month = d.getMonth() + 1;
let day = d.getDate();

document.getElementById("date").innerHTML = day + "/" + month + "/" + year;

function openModal(message) {
    var modal = document.getElementById("myModal");
    var modalContent = document.getElementById("content");
    modalContent.innerHTML = message;
    modal.style.display = "block";
}

function removeModal() {
    var modal = document.getElementById("myModal");
    modal.style.display = "none";
}
