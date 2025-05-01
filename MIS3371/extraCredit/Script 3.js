/*
    Program name: Script_1.js
    Author: Valentino Javier Salerni Longo
    Date created: 04/19/2025
    Date last edited:
    Version: 1.3
    Description: Script for extra credit */


const IDs = ["firstname", "lastname", "socialsecurity", "zip", "email",
    "userID", "password", "password2", "city", "address1", "phone", "socialsecurity2",
    "socialsecurity3", "phone2", "phone3"];


const d = new Date();

let year = d.getFullYear();
let month = d.getMonth() + 1;
let day = d.getDate();

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
    if (specialCharactersForbidden.test(password)) {
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
    let optionalFields = checkOptionalFields();
    let formContents = document.getElementById("signup");
    for (i = 0; i < formContents.length; i++) {
        let id = formContents.elements[i].id;
        let inputElement = document.getElementById(id);
        if (!id) continue;
        if (inputElement.value == "" && inputElement.hasAttribute("required")) {
            inputElement.style.borderColor = "red";
            hasErrors = true;
        }
        else if (inputElement.style.borderColor == "red") {
            hasErrors = true;
        }
        else {
            inputElement.style.borderColor = "";
        }
    }
    if (!passwordConditions || hasErrors || !match || !optionalFields) {
        document.querySelector("input[type='submit']").hidden = true;
        return false;
    }
    document.querySelector("input[type='submit']").hidden = false;
    return true;
}

// Preview functionality
// All popup build info obtained from: https://www.geeksforgeeks.org/how-to-create-a-popup-form-using-html-css-and-javascript/
const overlay = document.getElementById('popupOverlay');
function preview() {
    let formContents = document.getElementById("signup");
    let formOutput = '<div class="modal-content" id="previewModalContent">';
    formOutput = formOutput + "<table class='table-container'><th>Field</th><th>Value</th>";
    let dataType;
    let i;
    let text = "";
    for (i = 0; i < formContents.length; i++) {
        dataType = formContents.elements[i].type;
        const fieldID = formContents.elements[i].id;
        if (fieldID == "remember" || fieldID == "socialsecurity" || fieldID == "socialsecurity2" || fieldID == "socialsecurity3" || fieldID == "password" || fieldID == "password2") {
            continue;
        }

        if (formContents.elements[i].name == "g-recaptcha-response") {
            continue;
        }

        if (fieldID == "phone" || fieldID == "phone2") {
            text += formContents.elements[i].value + "-";
        }

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
            case "tel":
                if (fieldID == "phone3") {
                    text += formContents.elements[i].value;
                    formOutput = formOutput + "<tr><td align='left'>" + formContents.elements[i].name + "</td>";
                    formOutput = formOutput + "<td>" + text + "</td></tr>";
                }
                break;
            default:
                formOutput = formOutput + "<tr><td align='left'>" + formContents.elements[i].name + "</td>";
                if (formContents.elements[i].value == "") {
                    formOutput = formOutput + "<td> Please fill out this field </td></tr>"
                } else {
                    formOutput = formOutput + "<td>" + formContents.elements[i].value + "</td></tr>";
                }
        }
    }
    if (formOutput.length > 0) {
        formOutput += '</table>';
        formOutput += '<div style="text-align: center; margin-top: 20px;">';
        formOutput += '<input type="button" value="Close" class="btn-close-popup" onclick="closeModal()">';
        formOutput += '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;';
        formOutput += '<input type="submit" value="Submit" class="btn-submit-popup" onclick="validate(); closeModal()">';
        formOutput += '</div>';
        formOutput += '</div>';
    }

    const modal = document.getElementById("previewModal");
    const modalContent = document.getElementById("previewModalContent");
    modalContent.innerHTML = formOutput;
    modal.style.display = "block";
}

function closeModal() {
    const modal = document.getElementById("previewModal");
    modal.style.display = "none";
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

    const requirements = [/^[A-Za-z'-]+$/, /^[A-Za-z2-5-]+$/,
        /^([0-9]{3})$/,
        /^([0-9]{5}|[0-9]{5}-[0-9]{4})$/,
        /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,
        /^[a-zA-Z][a-zA-Z0-9]{4,29}$/,
        /^((?=.*\d)(?=.*[a-z])(?=.*[A-Z]).{8,30})$/,
        /^((?=.*\d)(?=.*[a-z])(?=.*[A-Z]).{8,30})$/,
        /^[A-Za-z'-]+$/,
        /^[A-Za-z0-9' -]+$/,
        /^([0-9]{3})$/,
        /^([0-9]{2})$/, /^([0-9]{4})$/,
        /^([0-9]{3})$/,
        /^([0-9]{4})$/,
    ];
    const errorID = ["firstNameError", "lastNameError", "ssnError", "zipError",
        "emailError", "userIDError", "pass1Error", "pass2Error", "cityError",
        "address1Error", "phoneError", "ssnError", "ssnError", "phoneError",
        "phoneError"];
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
    if (hasErrors) {
        document.querySelector("input[type='submit']").hidden = true;
        return false;
    }
    return hasErrors;
}

function makeLowerCase() {
    let userID = document.getElementById("userID").value;
    let displayID = userID.toLowerCase();
    document.getElementById("convertedID").innerHTML = displayID;
}

function removeRedBorder() {
    let input = ["state", "birthdate"];
    for (i = 0; i < input.length; i++) {
        let inputElement = document.getElementById(input[i]);
        if (inputElement.value == "") {
            inputElement.style.borderColor = "red";
        } else {
            inputElement.style.borderColor = "";
        }
    }
}

checkOptionalFields = function () {
    let input = ["address2", "middleinitial"];
    const requirements = [/^[A-Za-z0-9' -]+$/, /^[A-Z]+$/];
    const errorID = ["address2Error", "middleInitialError"];
    for (i = 0; i < input.length; i++) {
        let inputElement = document.getElementById(input[i]);
        let err = document.getElementById(errorID[i]);
        if (inputElement.value !== "" && !requirements[i].test(inputElement.value)) {
            inputElement.style.borderColor = "red";
            err.style.display = "block";
            inputElement.setAttribute("aria-invalid", "true");
            return false;
        } else {
            inputElement.style.borderColor = "";
            err.style.display = "none";
            inputElement.setAttribute("aria-invalid", "false");
        }
    }
    return true;
}
// from https://www.youtube.com/watch?v=cOsuSrN8BJI&ab_channel=kudvenkat
function moveCursor(from, to) {
    var lenght = from.value.length;
    var maxLength = from.getAttribute("maxlength");

    if (lenght == maxLength) {
        document.getElementById(to).focus();
    }
}
// from https://www.w3schools.com/js/tryit.asp?filename=tryjs_cookie_username

function checkCookie() {
    let user = getCookie("firstname");
    if (user != "") {
        openModal("Welcome again " + user + ", do you want to continue from where you left off?");
    } else {
        openModal("Welcome to the form! Please fill out the fields and click on submit when you are done.");
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

function openModal(message) {
    var modal = document.getElementById("myModal");
    var modalContent = document.getElementById("content");
    if (message == "Welcome to the form! Please fill out the fields and click on submit when you are done.") {
        modalContent.innerHTML = message;
        modal.style.display = "block";
    } else if (message == "You have been inactive for 3 minutes. Please fill out the form or it will be closed.") {
        var div = document.getElementById("modalContent");
        div.innerHTML = ""; // Clear existing content
        div.innerHTML = `<p id="content">${message}</p>`;
        div.innerHTML += `<div style="display: flex; justify-content: center; gap: 10px; margin-top: 10px;">
                <input type="button" id="modalClose" value="No" class="btn-close-popup" onclick="removeModal()"></input>
                </div`;
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

function setCookie(cname, cvalue, exdays) {
    let checkbox = document.getElementById("remember");
    if (checkbox.checked == false || getCookie("cookieAccepted") == "false") {
        document.cookie = cname + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
        removeLocalStorage(cname);
        document.getElementById(cname).value = "";
        removeModal();
        openModal("Welcome to the form! Please fill out the fields and click on submit when you are done.");
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

function updateResponse(caller) {
    var whoCalled = caller;
    if (whoCalled == "modalClose") {
        for (let i = 0; i < IDs.length; i++) {
            setCookie(IDs[i], "", -1);
            removeLocalStorage(IDs[i]);
        }
    } else if (whoCalled == "modalAccept") {
        for (i = 0; i < IDs.length; i++) {
            let value = getLocalStorage(IDs[i]);
            if (value) {
                document.getElementById(IDs[i]).value = value;
                setCookie(IDs[i], value, 1);
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
//from Google

// If reCAPTCHA is still loading, grecaptcha will be undefined.
grecaptcha.ready(function () {
    grecaptcha.render("container", {
        sitekey: "6Lfl7ygrAAAAAHtSLQeUqtAkCmsMJWrvXctqaNcu"
    });
});

function removeHidden(id1, id2, id3, id4) {
    let input1 = document.getElementById(id1);
    let input2 = document.getElementById(id2);
    let input3 = document.getElementById(id3);
    let buttonText = document.getElementById(id4);
    if (input1.type == "password") {
        input1.type = "text";
        input2.type = "text";
        input3.type = "text";
        buttonText.value = " Hide ";
    }
    else {
        input1.type = "password";
        input2.type = "password";
        input3.type = "password";
        buttonText.value = "Show";
    }
}

function removeHidden2(id1, id2) {
    let input1 = document.getElementById(id1);
    let buttonText = document.getElementById(id2);
    if (input1.type == "password") {
        input1.type = "text";
        buttonText.value = " Hide ";
    }
    else {
        input1.type = "password";
        buttonText.value = "Show";
    }
}

// from https://stackoverflow.com/questions/667555/how-to-detect-idle-time-in-javascript

window.onload = function () {
    inactivityTime();
}

function inactivityTime() {
    var time;
    var audio = document.getElementById("audio");
    var events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'onclick'];
    events.forEach(function (name) {
        document.addEventListener(name, resetTimer, true);
    });

    function logout() {
        alert("You are now logged out.")
        let checkbox = document.getElementById("remember");
        checkbox.checked = false;
        expireCookie();
        location.href = "form.html";
    }

    function resetTimer() {
        clearTimeout(time);

        if (!audio.paused) {
            audio.pause();
            audio.currentTime = 0;
        }

        audioPlayed = false;

        time = setTimeout(logout, 1000 * 60 * 10); // 10 minutes

        setTimeout(function () {
            openModal("You have been inactive for 3 minutes. Please fill out the form or it will be closed.");
            audio.play();
            audioPlayed = true;
        }, 1000 * 60 * 3); // 3 minutes
        // 1000 milliseconds = 1 second
    }
};

/* ADDITIONAL ENHANCEMENTS

    1. Added a show button on any obscured field.
    2. Added autotab on the phone number fields.
    3. Added a timeout so cookies are cleared and the form is 
    reset after 10 minutes of inactivity
    4. Ask the user if they allow to collect cookies, on date.js.
    5. Added a favicon to the page so the user can detect it easily if they have multiple tabs open.
    6. Play audio after 3 minutes of inactivity to remind the user the form is still open.

*/
