/*
    Program name: Script_1.js
    Author: Valentino Javier Salerni Longo
    Date created: 02/17/2025
    Date last edited:
    Version: 1.2
    Description: Script for homework 2. */

    const d = new Date();

    let year = d.getFullYear();
    let month = d.getMonth() + 1;
    let day = d.getDate();
    
    document.getElementById("date").innerHTML = day + "/" + month + "/" + year;
    // Obtained from https://www.geeksforgeeks.org/password-matching-using-javascript/ 
    // Check passwords match
    var pass_match = document.getElementById("match");
    var match = false;
    function checkPasswordsMatch() {
        var password1 = document.getElementById("password").value;
        var password2 = document.getElementById("password2").value;
        if(password1 == password2) {
            pass_match.innerHTML = "✅Passwords match";
            pass_match.setAttribute("style", "color: rgb(0, 128, 0)");
            match = true;
        } else {
            pass_match.innerHTML = "❌Passwords do not match";
            pass_match.setAttribute("style", "color: rgb(204, 0, 0)");
        }
    }
    /* From: https://www.w3schools.com/howto/howto_js_rangeslider.asp */
    var slider = document.getElementById("pain");
    var output = document.getElementById("pain_value");
    output.innerHTML = "Value: " + slider.value;
    
    slider.oninput = function() {
        output.innerHTML = "Value: " + this.value;
    }
    
    // Update dropbox and validate password conditions
    // Can probably be done with a loop but I cannot be bothered to do it rn
    var userID = false;
    var uppercase = false;
    var lowercase = false;
    var number = false;
    var special = false
    var minLength = false;
    var allMet = true;
    const specialCharacters = /[!@#$%^&*()\-+={}[\]:;"'<>,.?\/|\\]/;
    document.getElementById("password").addEventListener("input", checkPassword);
    function checkPassword(){
        allMet = true;
        var password = document.getElementById("password").value;
        var userID = document.getElementById("userID").value;
        var pass_userid = document.getElementById("pass_userid");
        var pass_upper = document.getElementById("pass_upper");
        var pass_lower = document.getElementById("pass_lower");
        var pass_number = document.getElementById("pass_number");
        var pass_special = document.getElementById("pass_special");
        var pass_length = document.getElementById("pass_length");
        if (!(password.includes(userID))) {
            pass_userid.setAttribute("style", "color: rgb(0, 128, 0)");
            pass_userid.innerHTML = "✅ Password does not contain user ID";
            userID = true;
        } else {
            pass_userid.setAttribute("style", "color: rgb(204, 0, 0)");
            pass_userid.innerHTML = "❌ Password contains user ID";
            allMet = false;
        }
        if (password.search(/[A-Z]/) < 0) {
            pass_upper.setAttribute("style", "color: rgb(204, 0, 0)");
            pass_upper.innerHTML = "❌ Password does not contain uppercase letters";
            allMet = false;
        } else {
            pass_upper.setAttribute("style", "color: rgb(0, 128, 0)");
            pass_upper.innerHTML = "✅ Password contains uppercase letters";
            uppercase = true;
        }
        if (password.search(/[a-z]/) < 0) {
            pass_lower.setAttribute("style", "color: rgb(204, 0, 0)");
            pass_lower.innerHTML = "❌ Password does not contain lowercase letters";
            allMet = false;
        } else {
            pass_lower.setAttribute("style", "color: rgb(0, 128, 0)");
            pass_lower.innerHTML = "✅ Password contains lowercase letters";
            lowercase = true;
        }
        if (password.search(/[0-9]/) < 0) {
            pass_number.setAttribute("style", "color: rgb(204, 0, 0)");
            pass_number.innerHTML = "❌ Password does not contain numbers";
            allMet = false;
        } else {
            pass_number.setAttribute("style", "color: rgb(0, 128, 0)");
            pass_number.innerHTML = "✅ Password contains numbers";
            number = true;
        }
        if (password.search(specialCharacters) < 0) {
            pass_special.setAttribute("style", "color: rgb(204, 0, 0)");
            pass_special.innerHTML = "❌ Password does not contain special characters";
            allMet = false;
        }
        else {
            pass_special.setAttribute("style", "color: rgb(0, 128, 0)");
            pass_special.innerHTML = "✅ Password contains special characters";
            special = true;
        }
        if (password.length < 8) {
            pass_length.setAttribute("style", "color: rgb(204, 0, 0)");
            pass_length.innerHTML = "❌ Password is less than 8 characters";
            allMet = false;
        }
        else {
            pass_length.setAttribute("style", "color: rgb(0, 128, 0)");
            pass_length.innerHTML = "✅ Password is at least 8 characters";
            minLength = true;
        }
    }
    // Dropbox showing password conditions
    function showConditions(){
        var passwordField = document.getElementById("password");
        document.getElementById("conditions").classList.toggle("show");
    
        passwordField.onblur = function (){
            document.getElementById("conditions").classList.remove("show");
            if (!allMet){
                document.getElementById("password").style.borderColor = "red";
            } else {
                document.getElementById("password").style.borderColor = "";
            }
        }
    }

    // Again as I couldnt figure out how to do it for both separately
    function showConditions2(){
        var passwordField2 = document.getElementById("password2");
        document.getElementById("match").classList.toggle("show");
    
        passwordField2.onblur = function (){
            document.getElementById("match").classList.remove("show")
            if(!match){
                document.getElementById("password2").style.borderColor = "red";
            } else {
                document.getElementById("password2").style.borderColor = "";
            }
        }
    }
    // Check all conditions are met
    function validate(){
        var alertShown = "";
        if (match && userID && uppercase && lowercase && number && special && minLength){
            return true;
        } else {
            if (!match){
                alertShown += "Passwords do not match\n";
            }
            alert(alertShown);
            return false;
        }
    }
    // Preview functionality
    // Primero ver que el popup funcione y despues ver como hago para popularlo
    function preview(){
        
    }

