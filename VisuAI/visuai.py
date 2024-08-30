from flask import Flask, render_template, Response, request, jsonify
import cv2
from ultralytics import YOLO
import numpy as np
from g4f.client import Client
import time
import os
from gtts import gTTS
import speech_recognition as sr
import pygame
import threading
import datetime
import sounddevice as sd
from scipy.io.wavfile import write
from flask import session


app = Flask(__name__)

app.secret_key = '100'

class VisuAI:
   def __init__(self):
       self.model = YOLO('yolov8n.pt')  # Correctly assign the model to self
       self.cap = cv2.VideoCapture(0)
       self.saved_images_folder = './saved_images'
       self.contacts = {}  # Store contacts in a dictionary
       self.client = Client()  # Initialize the client without specifying a model provider
       pygame.mixer.init()  # Initialize pygame mixer for audio


       if not os.path.exists(self.saved_images_folder):
           os.makedirs(self.saved_images_folder)

   def add_contact(self, name, number):
        self.contacts[name.lower()] = number

   def get_contact_number(self, name):
        return self.contacts.get(name.lower())

   def list_contacts(self):
        return self.contacts

   def find_object_in_frame(self, results, object_name):
           object_name = object_name.lower()  # Ensure comparison is case-insensitive


           # Search for the specified object in the frame
           for result in results:
               for i in range(result.boxes.xyxy.shape[0]):
                   class_id = result.boxes.cls[i].cpu().numpy()
                   class_name = self.model.names[int(class_id)].lower()  # Make sure class_name is lowercase


                   if class_name == object_name:
                       bbox = result.boxes.xyxy[i].cpu().numpy()
                       center_x = (bbox[0] + bbox[2]) / 2
                       center_y = (bbox[1] + bbox[3]) / 2
                       position_description = self.describe_position(
                           center_x, center_y,
                           int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                           int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                       )
                       return position_description
           return None




   def listen_for_command(self):
       recognizer = sr.Recognizer()
       fs = 16000  # Sample rate
       duration = 5  # Duration of recording in seconds


       print("Listening for command...")


       # Record the audio
       audio_data = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
       sd.wait()  # Wait until the recording is finished
       audio_data = np.squeeze(audio_data)


       # Convert the NumPy array to an AudioData object
       audio = sr.AudioData(audio_data.tobytes(), fs, 2)


       try:
           command = recognizer.recognize_google(audio).lower()
           print(f"Command received: {command}")
           return command
       except sr.UnknownValueError:
           print("Sorry, I did not understand the command.")
           return None
       except sr.RequestError as e:
           print(f"Could not request results from Google Speech Recognition service; {e}")
           return None


   def speak_text(self, text):
       tts = gTTS(text=text, lang='en')
       audio_file = "response.mp3"
       tts.save(audio_file)
       self.play_audio(audio_file)


   def play_audio(self, file):
       try:
           pygame.mixer.music.load(file)
           pygame.mixer.music.play()
           while pygame.mixer.music.get_busy():
               pygame.time.Clock().tick(10)
       except pygame.error as e:
           print(f"Error playing audio: {e}")


   def get_object_color(self, frame, bbox):
       x1, y1, x2, y2 = bbox
       object_region = frame[int(y1):int(y2), int(x1):int(x2)]
       mean_color = cv2.mean(object_region)[:3]
       return mean_color


   def color_to_description(self, color):
       color = np.array(color)
       if np.all(color < [50, 50, 50]):
           return "very dark"
       elif np.all(color < [100, 100, 100]):
           return "dark"
       elif np.all(color < [150, 150, 150]):
           return "medium"
       elif np.all(color < [200, 200, 200]):
           return "light"
       else:
           return "very light"


   def calculate_angle(self, position, fov, frame_size):
       if frame_size == 0:  # Check to prevent division by zero
           return 0
       center = frame_size / 2
       relative_position = position - center
       angle = (relative_position / center) * (fov / 2)
       return angle


   def describe_position(self, center_x, center_y, frame_width, frame_height):
       horizontal_pos = "center"
       vertical_pos = "center"
       if center_x < frame_width / 3:
           horizontal_pos = "left"
       elif center_x > 2 * frame_width / 3:
           horizontal_pos = "right"
       if center_y < frame_height / 3:
           vertical_pos = "top"
       elif center_y > 2 * frame_height / 3:
           vertical_pos = "bottom"
       return f"{vertical_pos} {horizontal_pos}"


   def size_description(self, width, height, frame_width, frame_height):
       if frame_width == 0 or frame_height == 0:  # Check to prevent division by zero
           return "undefined size"  # Return a default value
       object_area = width * height
       frame_area = frame_width * frame_height
       size_ratio = object_area / frame_area
       if size_ratio < 0.05:
           return "small"
       elif size_ratio < 0.2:
           return "medium"
       else:
           return "large"


   def draw_boxes(self, frame, results, h_fov, frame_width, frame_height):
       if frame_width == 0 or frame_height == 0:
           return  # Prevent further processing if dimensions are zero


       object_descriptions = []
       class_counts = {}
       objects_detected = []


       for result in results:
           if result.boxes.xyxy.shape[0] == 0:
               continue
           for i in range(result.boxes.xyxy.shape[0]):
               bbox = result.boxes.xyxy[i].cpu().numpy()
               confidence = result.boxes.conf[i].cpu().numpy()
               class_id = result.boxes.cls[i].cpu().numpy()
               class_name = self.model.names[int(class_id)]
               color = (0, 255, 0) if class_name != "mouse" else (255, 0, 0)
               cv2.rectangle(frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), color, 2)
               label = f"{class_name} {confidence:.2f}"
               cv2.putText(frame, label, (int(bbox[0]), int(bbox[1]) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)


               mean_color = self.get_object_color(frame, bbox)
               color_description = self.color_to_description(mean_color)
               object_width = bbox[2] - bbox[0]
               object_height = bbox[3] - bbox[1]
               size_desc = self.size_description(object_width, object_height, frame_width, frame_height)
               center_x = (bbox[0] + bbox[2]) / 2
               center_y = (bbox[1] + bbox[3]) / 2
               h_angle = self.calculate_angle(center_x, h_fov, frame_width)
               v_angle = self.calculate_angle(center_y, h_fov * (frame_height / frame_width), frame_height)
               direction = self.describe_position(center_x, center_y, frame_width, frame_height)
               description = (f"I see a {size_desc} {class_name} at the {direction}. "
                              f"The color of the object is {color_description}. It is positioned at an angle of {h_angle:.2f} degrees horizontally and "
                              f"{v_angle:.2f} degrees vertically.")
               object_descriptions.append(description)


               objects_detected.append((class_name, description))  # Save detected object info


               if class_name in class_counts:
                   class_counts[class_name] += 1
               else:
                   class_counts[class_name] = 1


       scene_summary = "Here's what I see: " + ", ".join([f"{count} {name}(s)" for name, count in class_counts.items()])
       return object_descriptions, scene_summary, objects_detected


   def generate_scene_description(self, object_descriptions, scene_summary):
       scene_description_prompt = (f"Based on the detected objects, here is a summary of the scene:\n"
                                   f"{scene_summary}\n"
                                   f"Detailed descriptions of the objects:\n" + "\n".join(object_descriptions) + "\n"
                                   f"You are a helpful assistant that will take the summary of the scene and output a brief but descriptive response. I am a blind person that needs to know the basics of the environment and what the current scene entails. Please describe the scene in a natural, brief, but all-encompassing manner.")
       response = self.client.chat.completions.create(
           model="gpt-3.5-turbo",  # Use the appropriate model
           messages=[{"role": "user", "content": scene_description_prompt}]
       )
       return response.choices[0].message.content


   def interact_with_user(self, question, objects_detected):
       # Use detected objects and question to generate an interactive response
       object_names = [obj[0] for obj in objects_detected]
       descriptions = [obj[1] for obj in objects_detected]
      
       prompt = f"You are an interactive AI assistant. The current scene includes: {', '.join(object_names)}. "
       prompt += f"User asked: '{question}'. Based on the scene, provide an informative response. Object descriptions: {'; '.join(descriptions)}."


       response = self.client.chat.completions.create(
           model="gpt-3.5-turbo",  # Use the appropriate model
           messages=[{"role": "user", "content": prompt}]
       )
       return response.choices[0].message.content


   def process_frame(self):
       ret, frame = self.cap.read()
       if not ret:
           return None, None, []
       frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
       frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
       h_fov = 70.0  # Default horizontal field of view
       results = self.model(frame, agnostic_nms=True)


       if results:
           object_descriptions, scene_summary, objects_detected = self.draw_boxes(frame, results, h_fov, frame_width, frame_height)
           return object_descriptions, scene_summary, objects_detected
       return None, None, []
   def call_contact_route(name):
        contact_number = visuai.get_contact_number(name)
        if contact_number:
            visuai.speak_text(f"Calling {name.capitalize()} at {contact_number}.")
            return jsonify(status=f"Calling {name.capitalize()}..."), 200
        return jsonify(status=f"Contact {name.capitalize()} not found."), 400


   def release(self):
       self.cap.release()
       pygame.mixer.quit()  # Quit pygame mixer when done
       cv2.destroyAllWindows()




visuai = VisuAI()


@app.route('/')
def index():
   return render_template('visuai.html')


@app.route('/video_feed')
def video_feed():
   return Response(stream_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/listen_for_object', methods=['POST'])
def listen_for_object():
   # Listen for the user's speech command
   object_name = visuai.listen_for_command()
  
   if object_name:
       return jsonify(object_name=object_name)
   else:
       return jsonify(status="Failed to understand the command."), 400


def stream_frames():
   while True:
       ret, frame = visuai.cap.read()
       if not ret:
           break


       results = visuai.model(frame, agnostic_nms=True)
       frame_width = int(visuai.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
       frame_height = int(visuai.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))


       if results:
           visuai.draw_boxes(frame, results, 70.0, frame_width, frame_height)


       ret, buffer = cv2.imencode('.jpg', frame)
       frame = buffer.tobytes()
       yield (b'--frame\r\n'
              b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')




@app.route('/reset', methods=['POST'])
def reset_image():
   # Just clear the input fields and reset the status without releasing the camera
   return jsonify(status="Reset successful, all functions cleared.")


@app.route('/capture', methods=['POST'])
def capture_image():
   # Capture the image immediately
   ret, frame = visuai.cap.read()
   if ret:
       timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
       default_filename = f"captured_image_{timestamp}.jpg"
       filepath = os.path.join(visuai.saved_images_folder, default_filename)
       cv2.imwrite(filepath, frame)


       # After capturing, prompt the user to name the image
       visuai.speak_text("Image captured successfully. Please say 'name it' followed by the name you want to give this image.")


       return jsonify(status="Image captured successfully. Now please name the image.", default_filename=default_filename)
   return jsonify(status="Failed to capture image."), 500




@app.route('/rename_image', methods=['POST'])
def rename_image():
   default_filename = request.form.get('default_filename')
   new_filename = request.form.get('filename')
   if not default_filename or not new_filename:
       return jsonify(status="Both default and new filenames are required."), 400


   old_filepath = os.path.join(visuai.saved_images_folder, default_filename)
   new_filepath = os.path.join(visuai.saved_images_folder, f"{new_filename}.jpg")
   if os.path.exists(old_filepath):
       os.rename(old_filepath, new_filepath)
       return jsonify(status=f"Image renamed successfully as {new_filename}.jpg.")
   return jsonify(status="Failed to rename image."), 500




@app.route('/find', methods=['POST'])
def find_object():
   object_name = request.form.get('object_name').lower()
   if not object_name:
       return jsonify(status="Object name is required."), 400


   start_time = time.time()
   while time.time() - start_time < 30:  # Search for 30 seconds
       ret, frame = visuai.cap.read()
       if not ret:
           return jsonify(status="Failed to capture frame."), 500


       results = visuai.model(frame, agnostic_nms=True)
       found_position = visuai.find_object_in_frame(results, object_name)


       if found_position:
           location_message = f"{object_name.capitalize()} found at {found_position}."
           visuai.speak_text(location_message)
           return jsonify(status=location_message)


   return jsonify(status=f"{object_name.capitalize()} not found within 30 seconds."), 400




@app.route('/speak', methods=['POST'])
def speak_command():
   command = request.form.get('command')
   print(f"Received command: {command}")  # Debugging line
  
   if not command:
       return jsonify(command="unknown"), 400
  
   if "reset" in command:
       return jsonify(command="reset")
   elif "where is" in command:
       return jsonify(command=command)  # Pass the entire command for object search
   elif "capture" in command:
       print("Capture command received")  # Debugging line
       return jsonify(command="capture")  # Command to capture an image
   elif "name it" in command:
       return jsonify(command=command)  # Command to rename an image
   elif "about" in command:
       # Respond and continue the interaction
       return jsonify(command=command, continue_interaction=True)  # Command to ask about something
   if "add contact" in command:
        # Ask for name and number, and add contact
        name = command.replace("add contact", "").strip()
        visuai.speak_text(f"What is the contact's name?")
        # The contact name will be captured in the next input and handled
        return jsonify(command="add_contact_name"), 200

   elif "call" in command:
        # Extract name and simulate a call
        name = command.replace("call", "").strip()
        return visuai.call_contact_route(name)
   else:
       return jsonify(command="unknown"), 400












@app.route('/listen_and_respond', methods=['POST'])
def listen_and_respond():
   question = request.form.get('question')
   continue_interaction = request.form.get('continue_interaction', 'false').lower() == 'true'
  
   if not question:
       return jsonify(status="Question is required."), 400
  
   ret, frame = visuai.cap.read()
   if not ret:
       return jsonify(status="Failed to capture frame"), 500
  
   object_descriptions, scene_summary, objects_detected = visuai.process_frame()
   if not object_descriptions or not scene_summary:
       return jsonify(status="No objects detected"), 500


   response = visuai.interact_with_user(question, objects_detected)
   visuai.speak_text(response)


   if continue_interaction:
       return jsonify(status=response, continue_interaction=True)
   else:
       return jsonify(status=response)




if __name__ == '__main__':
   app.run()




@app.route('/stop_ai', methods=['POST'])
def stop_ai():
   # Here you should implement a mechanism to stop all ongoing processes related to AI
   # For example, you could stop any ongoing speech recognition or audio playback
   visuai.release()  # Stop all ongoing processes and release resources
   return jsonify(status="AI stopped successfully.")


@app.route('/listen_for_command', methods=['POST'])
def listen_for_command():
   command = visuai.listen_for_command()
  
   if command:
       return jsonify(status="success", command=command)
   else:
       return jsonify(status="failure"), 400

# Extend the Flask app routes

@app.route('/add_contact', methods=['POST'])
def add_contact():
    # Example route if you want to handle contact storage server-side
    contact_name = request.form.get('name')
    contact_phone = request.form.get('phone')

    if contact_name and contact_phone:
        # Store contacts in a session, database, or any other preferred method
        return jsonify(status="Contact added successfully."), 200
    return jsonify(status="Failed to add contact."), 400

@app.route('/call_contact', methods=['POST'])
def call_contact():
    contact_name = request.form.get('name').strip().lower()

    contact_number = visuai.get_contact_number(contact_name)
    if contact_number:
        # Simulate calling the contact
        visuai.speak_text(f"Calling {contact_name.capitalize()} at {contact_number}.")
        return jsonify(status=f"Calling {contact_name.capitalize()}..."), 200
    return jsonify(status=f"Contact {contact_name.capitalize()} not found."), 400

@app.route('/process_command', methods=['POST'])
def process_command():
    command = request.json.get('command')

    if "add contact" in command.lower():
        visuai.speak_text("Please say the contact's name.")
        return jsonify(response="Please say the contact's name.", next_action="name")

    elif "save" in command.lower():
        if 'name' in session and 'phone' in session:
            visuai.contacts[session['name']] = session['phone']
            visuai.speak_text(f"Contact {session['name']} with phone number {session['phone']} saved successfully.")
            session.pop('name', None)
            session.pop('phone', None)
            return jsonify(response="Contact saved successfully.", next_action="stop")
        else:
            visuai.speak_text("Please provide both a name and a phone number before saving.")
            return jsonify(response="Please provide both a name and a phone number before saving.", next_action="listen")

    elif "name" in session and 'phone' not in session:
        session['name'] = command
        visuai.speak_text("Please say the contact's phone number.")
        return jsonify(response="Please say the contact's phone number.", next_action="phone")

    elif 'name' in session and 'phone' not in session:
        session['phone'] = command
        visuai.speak_text(f"You said the name is {session['name']} and the number is {session['phone']}. Say 'save' to confirm.")
        return jsonify(response=f"You said the name is {session['name']} and the number is {session['phone']}. Say 'save' to confirm.", next_action="listen")

    return jsonify(response="Unknown command.", next_action="listen")
