/*
    Program name: Script_1.js
    Author: Valentino Javier Salerni Longo
    Date created: 03/17/2025
    Date last edited:
    Version: 1.7
    Description: Script for homework 3. */

const d = new Date();

let year = d.getFullYear();
let month = d.getMonth() + 1;
let day = d.getDate();

document.getElementById("date").innerHTML = day + "/" + month + "/" + year;
// Obtained from https://www.geeksforgeeks.org/password-matching-using-javascript/ 
// Check passwords match
var pass_match = document.getElementById("match");
function checkPasswordsMatch() {
    let match = false;
    let password1 = document.getElementById("password").value;
    let password2 = document.getElementById("password2").value;
    if (password1 == password2) {
        pass_match.innerHTML = "✅Passwords match";
        pass_match.setAttribute("style", "color: rgb(0, 128, 0)");
        match = true;
    } else {
        pass_match.innerHTML = "❌Passwords do not match";
        pass_match.setAttribute("style", "color: rgb(204, 0, 0)");
    }
    return match;
}
/* From: https://www.w3schools.com/howto/howto_js_rangeslider.asp */
var slider = document.getElementById("pain");
var output = document.getElementById("pain_value");
output.innerHTML = "Value: " + slider.value;

slider.oninput = function () {
    output.innerHTML = "Value: " + this.value;
}

// Update dropbox and validate password conditions
// Can probably be done with a loop but I cannot be bothered to do it rn
let userIDcondition = false;
let uppercase = false;
let lowercase = false;
let number = false;
let special = false
let minLength = false;
const specialCharactersAllowed = /[!@#$%^&*()\-+={}[\]:;<>,.?\/|\\]/;
const specialCharactersForbidden = /["']/;
document.getElementById("password").addEventListener("input", checkPassword);
function checkPassword() {
    var allMet = true;
    let password = document.getElementById("password").value;
    let userID = document.getElementById("userID").value;
    let pass_userid = document.getElementById("pass_userid");
    let pass_upper = document.getElementById("pass_upper");
    let pass_lower = document.getElementById("pass_lower");
    let pass_number = document.getElementById("pass_number");
    let pass_special = document.getElementById("pass_special");
    let pass_length = document.getElementById("pass_length");
    if (!(password.includes(userID))) {
        pass_userid.setAttribute("style", "color: rgb(0, 128, 0)");
        pass_userid.innerHTML = "✅ Password does not contain user ID";
        userIDcondition = true;
    } else {
        pass_userid.setAttribute("style", "color: rgb(204, 0, 0)");
        pass_userid.innerHTML = "❌ Password contains user ID";
        userIDcondition = false;
        allMet = false;
    }
    if (password.search(/[A-Z]/) < 0) {
        pass_upper.setAttribute("style", "color: rgb(204, 0, 0)");
        pass_upper.innerHTML = "❌ Password does not contain uppercase letters";
        uppercase = false
        allMet = false;
    } else {
        pass_upper.setAttribute("style", "color: rgb(0, 128, 0)");
        pass_upper.innerHTML = "✅ Password contains uppercase letters";
        uppercase = true;
    }
    if (password.search(/[a-z]/) < 0) {
        pass_lower.setAttribute("style", "color: rgb(204, 0, 0)");
        pass_lower.innerHTML = "❌ Password does not contain lowercase letters";
        lowercase = false;
        allMet = false;
    } else {
        pass_lower.setAttribute("style", "color: rgb(0, 128, 0)");
        pass_lower.innerHTML = "✅ Password contains lowercase letters";
        lowercase = true;
    }
    if (password.search(/[0-9]/) < 0) {
        pass_number.setAttribute("style", "color: rgb(204, 0, 0)");
        pass_number.innerHTML = "❌ Password does not contain numbers";
        number = false;
        allMet = false;
    } else {
        pass_number.setAttribute("style", "color: rgb(0, 128, 0)");
        pass_number.innerHTML = "✅ Password contains numbers";
        number = true;
    }
    if (specialCharactersAllowed.test(password)) {
        pass_special.setAttribute("style", "color: rgb(0, 128, 0)");
        pass_special.innerHTML = "✅ Password contains special characters";
        special = true;
    } else {
        pass_special.setAttribute("style", "color: rgb(204, 0, 0)");
        pass_special.innerHTML = "❌ Password does not contain special characters";
        special = false;
        allMet = false;
    }
    if(specialCharactersForbidden.test(password)) {
        pass_special.setAttribute("style", "color: rgb(204, 0, 0)");
        pass_special.innerHTML = "❌ Password cannot contain quotes";
        special = false;
        allMet = false;
    }
    if (password.length < 8) {
        pass_length.setAttribute("style", "color: rgb(204, 0, 0)");
        pass_length.innerHTML = "❌ Password is less than 8 characters";
        minLength = false;
        allMet = false;
    }
    else {
        pass_length.setAttribute("style", "color: rgb(0, 128, 0)");
        pass_length.innerHTML = "✅ Password is at least 8 characters";
        minLength = true;
    }
    return allMet;
}
// Dropbox showing password conditions
function showConditions() {
    let allMet = checkPassword();
    let passwordField = document.getElementById("password");
    document.getElementById("conditions").classList.toggle("show");
    passwordField.onblur = function () {
        var passStillMatch = checkPasswordsMatch();
        document.getElementById("conditions").classList.remove("show");
        if (!allMet || !passStillMatch) {
            document.getElementById("password").style.borderColor = "red";
        } else {
            document.getElementById("password").style.borderColor = "";
        }
    }
}

// Again as I couldnt figure out how to do it for both separately
function showConditions2() {
    let passwordField2 = document.getElementById("password2");
    document.getElementById("match").classList.toggle("show");

    passwordField2.onblur = function () {
        var match = checkPasswordsMatch();
        document.getElementById("match").classList.remove("show")
        if (!match) {
            document.getElementById("password2").style.borderColor = "red";
        } else {
            document.getElementById("password2").style.borderColor = "";
            document.getElementById("password").style.borderColor = "";
        }
    }
}
// Check all conditions are met
function validate() {
    let match = checkPasswordsMatch();
    let hasErrors = checkErrors();
    let passwordConditions = checkPassword();
    let formContents = document.getElementById("signup");
    for(i = 0; i < formContents.length; i++){
        let id = formContents.elements[i].id;
        let inputElement = document.getElementById(id);
        if(!id) continue;
        if(inputElement.value == "" && inputElement.hasAttribute("required"))  {
            inputElement.style.borderColor = "red";
            hasErrors = true;
        }
        else {
            inputElement.style.borderColor = "";
        }
    }
    if (!passwordConditions || hasErrors || !match) {
        
        return false;
    }
    document.querySelector("input[type='submit']").disabled = false;
    return true;
}

// Preview functionality
// All popup build info obtained from: https://www.geeksforgeeks.org/how-to-create-a-popup-form-using-html-css-and-javascript/
const overlay = document.getElementById('popupOverlay');
function preview() {
    let formContents = document.getElementById("signup");
    let formOutput = '<div class="popup-box">';
    formOutput = formOutput + "<table class='table-container'><th>Field</th><th>Value</th>";
    let dataType;
    let i;
    for (i = 0; i < formContents.length; i++) {
        dataType = formContents.elements[i].type;
        switch (dataType) {
            case "checkbox":
                if (formContents.elements[i].checked) {
                    formOutput = formOutput + "<tr><td align='left'>" + formContents.elements[i].name + "</td>";
                    formOutput = formOutput + "<td>Checked</td></tr>";
                }
                break;
            case "radio":
                if (formContents.elements[i].checked) {
                    formOutput = formOutput + "<tr><td align='left'>" + formContents.elements[i].name + "</td>";
                    formOutput = formOutput + "<td>" + formContents.elements[i].value + "</td></tr>";
                }
                break;
            case "button": case "submit": case "reset":
                break;
            default:
                formOutput = formOutput + "<tr><td align='left'>" + formContents.elements[i].name + "</td>";
                if(formContents.elements[i].value == ""){
                formOutput = formOutput + "<td> Please fill out this field </td></tr>"
                } else {
                formOutput = formOutput + "<td>" + formContents.elements[i].value + "</td></tr>"; 
                }
        }
    }
    if (formOutput.length > 0) {
        formOutput = formOutput + '</table> <input type="button" value="Close" class="btn-close-popup" onclick="togglePopup()"</div>';
        overlay.innerHTML = formOutput
    }
    document.getElementById('popupOverlay').classList.toggle('show');
}


function togglePopup() {
    overlay.classList.remove("show");
}

//Max and min dates from https://stackoverflow.com/questions/32378590/set-date-input-fields-max-date-to-today

const birthDate = document.getElementById("birthdate");
const maxDate = d.toISOString().split("T")[0];
birthDate.setAttribute("max", maxDate);

const minD = new Date(d);
minD.setFullYear(d.getFullYear() - 120);
const minDate = minD.toISOString().split("T")[0];
birthDate.setAttribute("min", minDate);

// Check for errors in the whole form
// Accesibility errors obtained from: https://www.w3schools.com/accessibility/accessibility_errors.php
function checkErrors() {
    var hasErrors = false;
    const IDs = ["firstname", "lastname", "socialsecurity", "zip", "email",
         "userID", "password", "password2", "city", "address1", "phone"];
    const requirements = [/^[A-Za-z'-]+$/, /^[A-Za-z2-5-]+$/,
         /^([0-9]{3}-[0-9]{2}-[0-9]{4}|[0-9]{9})$/, 
         /^([0-9]{5}|[0-9]{5}-[0-9]{4})$/,
         /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/, 
         /^[a-zA-Z][a-zA-Z0-9]{4,29}$/,
         /^((?=.*\d)(?=.*[a-z])(?=.*[A-Z]).{8,30})$/, 
         /^((?=.*\d)(?=.*[a-z])(?=.*[A-Z]).{8,30})$/,
         /^[A-Za-z'-]+$/,
         /^[A-Za-z0-9'-]+$/,
         /^([0-9]{3}-[0-9]{3}-[0-9]{4}|[0-9]{10})$/
        ];
    const errorID = ["firstNameError", "lastNameError", "ssnError", "zipError",
         "emailError", "userIDError", "pass1Error", "pass2Error", "cityError",
         "address1Error", "phoneError"];
    var i;
    for (i = 0; i < IDs.length; i++) {
        let input = document.getElementById(IDs[i]).value;
        let err = document.getElementById(errorID[i]);
        let inputElement = document.getElementById(IDs[i]);
        if (input == "") {
            inputElement.style.borderColor = "red"; 
            hasErrors = true;
        } else if (!requirements[i].test(input)) {
            inputElement.style.borderColor = "red";
            hasErrors = true;
            err.style.display = "block";
            inputElement.setAttribute("aria-invalid", "true");
        } else {
            document.getElementById(IDs[i]).style.borderColor = "";
            err.style.display = "none";
            inputElement.setAttribute("aria-invalid", "false");
        }
    }
    return hasErrors;
}

function makeLowerCase(){
    let userID = document.getElementById("userID").value;
    let displayID = userID.toLowerCase();
    document.getElementById("convertedID").innerHTML = displayID;
}

function removeRedBorder(){
    let input = ["state", "birthdate"];
    for(i = 0; i < input.length; i++){
        let inputElement = document.getElementById(input[i]);
        if(inputElement.value == ""){
            inputElement.style.borderColor = "red";
        } else {
            inputElement.style.borderColor = "";
        }
    }
}