let currentFunction = '';
let imageCaptured = false;  // Track if an image has been captured
let stopSearching = false;  // Control variable to stop the search
let contacts = [];  // Stores all contacts


function resetFunction() {
   console.log("Resetting state...");  // Debugging line


   stopAI();  // Stop any ongoing AI processing


   stopSearching = true;  // Stop any ongoing search


   // Clear the input box
   document.getElementById('user-input').value = '';


   // Clear the function label
   document.getElementById('function-label').innerText = '';


   // Clear the status label
   document.getElementById('status-label').innerText = 'Waiting for command...';


   // Check if there's a captured image that hasn't been renamed
   const defaultFilename = document.getElementById('user-input').dataset.defaultFilename;
   if (imageCaptured && defaultFilename) {
       saveImageWithDefaultName(defaultFilename);  // Automatically save the image with the default name
   }


   // Clear any stored data
   document.getElementById('user-input').dataset.defaultFilename = '';
   imageCaptured = false;  // Reset the image captured flag


   // Reset video stream if it was stopped
   startVideoStream();


   // Reset the current function
   currentFunction = '';
}


function setFunction(functionName) {
   resetFunction();  // Reset everything before setting a new function


   const functionLabel = document.getElementById('function-label');
  
   if (functionName === 'audio') {
       functionLabel.innerText = "Function: Audio Interaction";
       document.getElementById('user-input').placeholder = "Enter your question...";
       document.getElementById('user-input').disabled = false;
       currentFunction = 'audio';
   } else if (functionName === 'find') {
       functionLabel.innerText = "Function: Find Object";
       document.getElementById('user-input').placeholder = "Enter object name...";
       document.getElementById('user-input').disabled = false;
       currentFunction = 'find';
   } else if (functionName === 'capture') {
       functionLabel.innerText = "Function: Capture Image";
       document.getElementById('user-input').placeholder = "Enter new name...";
       document.getElementById('user-input').disabled = false;  // Allow input for renaming
       captureImage();  // Trigger image capture
   } else {
       functionLabel.innerText = "";  // Clear function label if no function is active
       document.getElementById('user-input').disabled = true;  // Disable input box by default
       currentFunction = '';
   }


   console.log("Current function set to:", currentFunction);  // Debugging line
}


function findObject(objectName) {
   if (currentFunction !== 'find') {
       return;
   }


   stopSearching = false;  // Reset the stop flag


   function search() {
       if (stopSearching) {
           updateStatus("Search stopped.");
           return;
       }


       fetch('/find', {
           method: 'POST',
           headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
           body: new URLSearchParams({ 'object_name': objectName })
       })
       .then(response => response.json())
       .then(data => {
           if (data.status.includes("found")) {
               updateStatus(data.status);  // Display location and confirmation
               visuai.speak_text(data.status);  // Speak out the location
               stopSearching = true;  // Stop searching after finding the object
           } else {
               updateStatus(data.status);  // Display status
               setTimeout(() => stopSearching = true, 30000);  // Stop searching after 30 seconds
           }
       })
       .catch(error => {
           console.error('Error:', error);
           setTimeout(() => stopSearching = true, 30000);  // Stop searching even if an error occurs after 30 seconds
       });
   }


   search();  // Start the search
}






function handleInput() {
   const userInput = document.getElementById('user-input').value.trim();
   console.log("Handling input for function:", currentFunction);  // Debugging line


   if (!currentFunction) {
       updateStatus("Please select an action first.");
       return;
   }


   if (currentFunction === 'find') {
       if (userInput) {
           updateStatus(`Continue searching for "${userInput}"...`);
           findObject(userInput);  // Start the continuous search
       } else {
           updateStatus("Please enter the object name to find.");
       }
   } else if (currentFunction === 'capture') {
       if (!imageCaptured) {
           updateStatus("No image captured to rename.");
       } else if (userInput) {
           renameImage(userInput);  // Rename the captured image
       } else {
           updateStatus("Please enter a name to rename the image.");
       }
   } else if (currentFunction === 'audio') {
       if (userInput) {
           askAudioQuestion(userInput);
       } else {
           updateStatus("Please enter your question.");
       }
   } else {
       updateStatus("Unhandled function. Please try again.");
   }
}


function captureImage() {
   resetFunction();  // Automatically reset before capturing a new image


   fetch('/capture', { method: 'POST' })
       .then(response => response.json())
       .then(data => {
           if (data.status.includes("successfully")) {
               updateStatus("Image captured successfully. Please say 'name it' followed by the name you want to give this image.");
               document.getElementById('user-input').value = data.default_filename.split('.')[0]; // Pre-fill input with default name
               document.getElementById('user-input').dataset.defaultFilename = data.default_filename; // Store the default filename
               document.getElementById('user-input').disabled = false;  // Enable input box
               imageCaptured = true;  // Set flag that image has been captured
               currentFunction = 'capture';  // Set the function context to capture


               visuai.speak_text("Image captured successfully. Please say 'name it' followed by the name you want to give this image.");
              
               // Immediately start listening for the next command
               startSpeakCommand();
           } else {
               updateStatus(data.status);
           }
       })
       .catch(error => console.error('Error:', error));
}




function renameImage(customFilename) {
   const defaultFilename = document.getElementById('user-input').dataset.defaultFilename;


   if (!defaultFilename) {
       updateStatus("No image captured to rename.");
       return;
   }


   fetch('/rename_image', {
       method: 'POST',
       headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
       body: new URLSearchParams({ 'default_filename': defaultFilename, 'filename': customFilename })
   })
   .then(response => response.json())
   .then(data => {
       updateStatus(data.status);
       resetFunction();  // Reset the function after renaming
   })
   .catch(error => console.error('Error:', error));
}
function askAudioQuestion(question, continueInteraction = false) {
   fetch('/listen_and_respond', {
       method: 'POST',
       headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
       body: new URLSearchParams({ 'question': question })
   })
   .then(response => response.json())
   .then(data => {
       updateStatus(data.status);
       visuai.speak_text(data.status);


       if (continueInteraction) {
           // After responding, prompt the user to ask another question
           setTimeout(() => {
               visuai.speak_text("Can I help you with anything else?");
               startSpeakCommand();  // Continue listening for another question
           }, 1000);  // Small delay before prompting again
       }
   })
   .catch(error => console.error('Error:', error));
}








function stopAI() {
   // Stop any ongoing speech or AI processes
   try {
       // Stop pygame mixer if it's playing
       if (pygame.mixer.music.get_busy()) {
           pygame.mixer.music.stop();
       }
   } catch (error) {
       console.error('Error stopping AI:', error);
   }


   // Send a request to stop any AI processing on the server
   fetch('/stop_ai', { method: 'POST' })
       .then(response => response.json())
       .then(data => console.log("AI Stopped:", data.status))
       .catch(error => console.error('Error:', error));
}




function startVideoStream() {
   const video = document.getElementById('video');
   video.src = '/video_feed'; // Restart the video feed
}


function stopVideoStream() {
   const video = document.getElementById('video');
   video.src = ''; // Stop the video feed
}


function updateStatus(status) {
   document.getElementById('status-label').innerText = status;
}


function saveImageWithDefaultName(defaultFilename) {
   // Automatically save the image with the default name if the user didn't rename it
   fetch('/rename_image', {
       method: 'POST',
       headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
       body: new URLSearchParams({ 'default_filename': defaultFilename, 'filename': defaultFilename.split('.')[0] })
   })
   .then(response => response.json())
   .then(data => {
       console.log(data.status);  // Log or handle the status if needed
       imageCaptured = false;  // Reset the flag as the image is now saved
   })
   .catch(error => console.error('Error:', error));
}
function handleRecognizedCommand(command) {
   console.log("Processing command:", command);  // Debugging line


   fetch('/speak', {
       method: 'POST',
       headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
       body: new URLSearchParams({ 'command': command })
   })
   .then(response => response.json())
   .then(data => {
       console.log("Command response received:", data);  // Debugging line


       if (data.command === "reset") {
           resetFunction();
       } else if (data.command.includes("where is")) {
           const objectName = data.command.replace("where is", "").trim();
           setFunction('find');
           findObject(objectName);
       } else if (data.command.includes("capture")) {
           console.log("Capturing image...");  // Debugging line
           setFunction('capture');
       } else if (data.command === "add_contact_name") {
             visuai.speak_text("Please say the contact's name.");
            // Listen for the name and then the number
            startSpeakCommand();
        } else if (data.command === "call_contact") {
            // Extract the name and send it to the server to simulate a call
            const name = command.replace("call", "").trim();
            callContact(name);
           captureImage();  // Automatically prompts for "name it"
       } else if (data.command.includes("name it")) {
           const name = data.command.replace("name it", "").trim();
           renameImage(name);
       } else if (data.command.includes("about")) {
           setFunction('audio');
           const question = data.command.replace("about", "").trim();
           askAudioQuestion(question, true);  // Continue interaction
       } else if (data.command.includes("that's all")) {
           updateStatus("Audio interaction ended.");
           visuai.speak_text("Thank you! Ending the session.");
           resetFunction();  // End the audio interaction
       } else {
           console.log("Command not recognized:", data.command);
           updateStatus("Command not recognized. Please try again.");
       }
   })
   .then(() => {
       // Automatically restart speech recognition after AI response
       startSpeakCommand();
   })
   .catch(error => {
       console.error('Error processing command:', error);
       updateStatus("Error processing command.");
   });
}




function startSpeakCommand() {
   console.log("Speak command started.");


   if ('webkitSpeechRecognition' in window) {
       const recognition = new webkitSpeechRecognition();
       recognition.continuous = true;
       recognition.interimResults = true;
       recognition.lang = 'en-US';


       recognition.onstart = function() {
           console.log("Speech recognition started.");
           updateStatus("Listening...");
       };


       recognition.onresult = function(event) {
           let interim_transcript = '';
           for (let i = event.resultIndex; i < event.results.length; ++i) {
               if (event.results[i].isFinal) {
                   const final_transcript = event.results[i][0].transcript.trim();
                   document.getElementById('recognized-speech').innerText = `You said: ${final_transcript}`;
                   console.log("Final transcript captured:", final_transcript);  // Debugging line
                   recognition.stop();


                   // Send the final transcript to the server for processing
                   handleRecognizedCommand(final_transcript);
               } else {
                   interim_transcript += event.results[i][0].transcript;
                   document.getElementById('recognized-speech').innerText = `You said: ${interim_transcript}`;
                   console.log("Interim transcript:", interim_transcript);  // Debugging line
               }
           }
       };


       recognition.onerror = function(event) {
           console.error("Speech recognition error:", event.error);
           updateStatus("Error in speech recognition.");
       };


       recognition.onend = function() {
           console.log("Speech recognition ended.");
           updateStatus("Speech recognition ended.");
       };


       recognition.start();
   } else {
       updateStatus("Your browser does not support speech recognition.");
   }
}



document.getElementById('addContactForm').addEventListener('submit', function(event) {
    event.preventDefault();  // Prevent the form from submitting the traditional way

    const contactName = document.getElementById('contactName').value.trim();
    const contactPhone = document.getElementById('contactPhone').value.trim();

    if (contactName && contactPhone) {
        contacts.push({ name: contactName, phone: contactPhone });
        updateContactList();
        clearContactForm();  // Clear the form after adding a contact
    }
});

function updateContactList() {
    const contactList = document.getElementById('contactList');
    contactList.innerHTML = '';

    contacts.forEach((contact, index) => {
        const li = document.createElement('li');
        li.textContent = `${contact.name} - ${contact.phone}`;
        li.dataset.index = index;
        li.addEventListener('click', function() {
            callContact(contact.phone);
        });
        contactList.appendChild(li);
    });
}

function showEmergencyContacts() {
    // Show the contact list when the emergency button is clicked
    const contactList = document.getElementById('contactList');
    if (contacts.length > 0) {
        contactList.style.display = 'block';
    } else {
        alert('No contacts available.');
    }
}

function callContact(phone) {
    alert(`Calling ${phone}...`);
    // This is where you'd implement the actual call logic if applicable
}

function clearContactForm() {
    document.getElementById('contactName').value = '';
    document.getElementById('contactPhone').value = '';
}









function toggleBlindMode() {
   // Implement the logic to toggle blind mode
   console.log("Blind mode toggled.");
}




