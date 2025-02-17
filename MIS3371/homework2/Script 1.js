/*
    Program name: Script_1.js
    Author: Valentino Javier Salerni Longo
    Date created: 02/01/2025
    Date last edited:
    Version: 1.0
    Description: Script that shows the current date for homework 1. */

const d = new Date();

let year = d.getFullYear();
let month = d.getMonth() + 1;
let day = d.getDate();

document.getElementById ("date").innerHTML = day + "/" + month + "/" + year;
/*
function preview() {
    var formcontents = document.getElementById("signup");
    var formoutput;
    var datatype;
    var i;
    formoutput = "<table class='output'><th>Dataname</th><th>Type</th><th>Value</th>";

    for(i = 0; i < formcontents.elements.length; i++) {
        element = formcontents.elements[i];
        if (element.type != "submit" && element.type !== "button") {
            formoutput += "<tr><td>" + element.name + "</td><td>" 
            + element.type + "</td><td>" + element.value + "</td></tr>";
        }
    }
    formoutput += "</table>";

    document.getElementById("preview").innerHTML = formoutput;
}*/