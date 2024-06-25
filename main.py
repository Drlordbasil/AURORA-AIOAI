import os
import threading
import time
import webbrowser
from flask import Flask, render_template, request, jsonify, g, send_file, Response
from Brain_modules.brain import Brain
from listen_lobe import AuroraRecorder
from speaker import text_to_speech
from queue import Queue
import json

app = Flask(__name__)

# Initialize components
brain = Brain()
aurora_recorder = AuroraRecorder()
progress_queue = Queue()

def update_progress(message):
    progress_queue.put(message)

def process_input(input_text):
    if not input_text:
        update_progress("Error: No input provided.")
        return {'response': 'No input provided.', 'status': 'Error'}, None
    
    update_progress(f"Received input: {input_text}")

    try:
        response = brain.process_input(input_text, update_progress)
        update_progress("Response generated")
        audio_file = None
        if brain.tts_enabled:
            update_progress("Generating audio response...")
            audio_file = text_to_speech(response)
            update_progress("Audio response generated")
        return {'response': response, 'status': 'Completed'}, audio_file
    except Exception as e:
        error_message = f"Error processing input: {str(e)}"
        update_progress(error_message)
        return {'response': error_message, 'status': 'Error'}, None

@app.before_request
def before_request():
    g.start_time = time.time()

@app.after_request
def after_request(response):
    diff = time.time() - g.start_time
    print(f"Request processed in {diff:.2f} seconds")
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.json
    message = data.get('message')
    
    if not message:
        return jsonify({'response': 'No message provided.', 'status': 'Error'})
    
    # Clear the progress queue before processing
    while not progress_queue.empty():
        progress_queue.get()
    
    response, audio_file = process_input(message)
    return jsonify({**response, 'audio_file': audio_file})

@app.route('/toggle_tts', methods=['POST'])
def toggle_tts():
    status = brain.toggle_tts()
    return jsonify({'status': f'Text-to-Speech {status}'})

@app.route('/start_recording', methods=['POST'])
def start_recording():
    try:
        aurora_recorder.start_recording()
        return jsonify({'status': 'Recording started'})
    except Exception as e:
        return jsonify({'status': f"Error starting recording: {str(e)}"})

@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    try:
        update_progress("Stopping recording...")
        aurora_recorder.stop_recording()
        update_progress("Recording stopped, starting transcription...")
        transcription = aurora_recorder.transcription
        update_progress(f"Transcription completed: {transcription}")
        
        response, audio_file = process_input(transcription)
        
        return jsonify({**response, 'transcription': transcription, 'audio_file': audio_file})
    except Exception as e:
        error_message = f"Error stopping recording: {str(e)}"
        update_progress(error_message)
        return jsonify({'status': error_message, 'response': error_message})

@app.route('/get_audio/<filename>', methods=['GET'])
def get_audio(filename):
    return send_file(filename, mimetype="audio/mp3")

@app.route('/get_detailed_info', methods=['GET'])
def get_detailed_info():
    return brain.get_detailed_info()

@app.route('/progress_updates')
def progress_updates():
    def generate():
        while True:
            message = progress_queue.get()
            yield f"data: {json.dumps({'message': message})}\n\n"
    return Response(generate(), mimetype='text/event-stream')

@app.route('/chat_history.json')
def chat_history():
    return jsonify(brain.chat_history)

def open_browser():
    webbrowser.open_new('http://127.0.0.1:5000/')

if __name__ == '__main__':
    threading.Timer(1.25, open_browser).start()
    app.run(host='0.0.0.0', port=5000, threaded=True)
