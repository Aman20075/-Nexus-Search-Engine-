import pyttsx3
import datetime
import os
import webbrowser

engine = pyttsx3.init()
engine.setProperty('rate', 170)

def speak(text):
    print(f"🤖 Bot: {text}")
    engine.say(text)
    engine.runAndWait()

speak("System online! Main apps aur websites kholne ke liye ready hoon.")

while True:
    user_input = input("\nYou Command: ").lower().strip()

    if "hello" in user_input or "hi" in user_input:
        speak("Hello! Kese hain aap?")

    elif "time" in user_input:
        now = datetime.datetime.now().strftime("%I:%M %p")
        speak(f"Abhi time ho raha hai {now}")

    # App Open Commands
    elif "open chrome" in user_input:
        speak("Opening Google Chrome...")
        os.system("start chrome")

    elif "open notepad" in user_input:
        speak("Opening Notepad...")
        os.system("start notepad")

    elif "open youtube" in user_input:
        speak("Opening YouTube...")
        webbrowser.open("https://www.youtube.com")

    elif "open google" in user_input:
        speak("Opening Google...")
        webbrowser.open("https://www.google.com")

    elif "bye" in user_input or "exit" in user_input:
        speak("Goodbye!")
        break
    else:
        speak("Aap 'open chrome', 'open youtube' ya 'open notepad' bol kar try karein.")