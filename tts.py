from gtts import gTTS
import os
import tempfile

def speak_text(text):
    if not text:
        return None
    try:
        # Create a temp file
        tts = gTTS(text=text, lang='en')
        
        # Create a named temp file that we can return the path of
        # Gradio needs a file path to play audio
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        
        tts.save(path)
        return path
    except Exception as e:
        print(f"TTS Error: {e}")
        return None
