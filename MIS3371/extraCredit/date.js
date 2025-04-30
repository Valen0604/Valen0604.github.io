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
