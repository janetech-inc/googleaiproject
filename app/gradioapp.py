#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os

from faster_whisper import WhisperModel
import google.generativeai as genai
import time
import asyncio
import edge_tts
import nest_asyncio
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip
from pydub import AudioSegment
import gradio as gr

nest_asyncio.apply()

CONTENT_PATH = os.environ.get("CONTENT_PATH", "./assets")

# Constants
AUDIO_OUTPUT_FILE = f"{CONTENT_PATH}/AnswerAudioTest.mp3"
VIDEO_OUTPUT_FILE = f"{CONTENT_PATH}/AnswerVideo.mp4"
VIDEO_ORIGIN_FILE = "assets/Shelly.mp4"

async def initialize_voices():
    global VOICE_OPTIONS
    voices = await edge_tts.list_voices()
    VOICE_OPTIONS = {voice['Locale'].split('-')[0]: voice['Name'] for voice in voices if voice['Gender'] == 'Male'}

async def list_language_codes():
    voices = await edge_tts.list_voices()
    language_codes = set()
    for voice in voices:
        if voice['Gender'] == 'Male':
            locale = voice['Locale']
            language_codes.add(locale.split('-')[0])
    return sorted(language_codes)  # Return sorted list of unique language codes


def handle_audio_upload(audio):
    whisper_model = WhisperModel("base", device="cpu")

    global audio_uploaded
    if audio:
        audio_uploaded = True
        start_time = time.time()
        segments, info = whisper_model.transcribe(audio)
        transcribed_text = " ".join([segment.text for segment in segments])
        end_time = time.time()
        print(f"Processing time: {end_time - start_time} seconds")
        return transcribed_text
    else:
        audio_uploaded = False
        return "No audio uploaded, click Audio to Text Button again"

async def generate_audio(response_text, voice_name):
    communicate = edge_tts.Communicate(response_text, voice_name)
    await communicate.save(AUDIO_OUTPUT_FILE)
    print(f"Audio saved to {AUDIO_OUTPUT_FILE}")

def create_video_with_audio_length(original_video_path, audio_path, output_video_path):
    video_clip = VideoFileClip(original_video_path)
    audio_duration = get_audio_duration(audio_path)
    video_duration = video_clip.duration
    num_repeats = int(audio_duration // video_duration) + 1
    clips = [video_clip] * num_repeats
    final_video_clip = concatenate_videoclips(clips)
    if final_video_clip.duration > audio_duration:
        final_video_clip = final_video_clip.subclip(0, audio_duration)
    audio_clip = AudioFileClip(audio_path)
    final_video_clip = final_video_clip.set_audio(audio_clip)
    final_video_clip.write_videofile(output_video_path, codec='libx264', audio_codec='aac', temp_audiofile=f"{CONTENT_PATH}/AnswerVideoTEMP_MPY_wvf_snd.mp4", remove_temp=True)

def get_audio_duration(audio_path):
    audio = AudioSegment.from_mp3(audio_path)
    return audio.duration_seconds

async def handle_response(question, selected_language_code, prompt):
    print(f"Selected language code: {selected_language_code}")
    #await initialize_voices()
    
    genai.configure(api_key="AIzaSyB9In1M-PS_TxrWBtHoivcGBTVqgPWCcIg")
    
    full_voice_name = VOICE_OPTIONS.get(selected_language_code, 'en-US')  # Default to 'en-US' if not found
    locale_part = full_voice_name.split('(')[1].split(',')[0].strip()  # "en-US"
    language_code = locale_part.split('-')[0]  # "en"
    response = genai.GenerativeModel('gemini-pro').generate_content(prompt + language_code +"\n and this is the user question \n" + question)
    response_text = response.text
    global geminiAnswerText
    geminiAnswerText = response_text
    try:
        os.makedirs(os.path.dirname(AUDIO_OUTPUT_FILE), exist_ok=True)
        print(f"Generating audio for response: {response_text}")
        await generate_audio(response_text, full_voice_name)
        print(f"Creating video with audio for response: {response_text}")
        create_video_with_audio_length(VIDEO_ORIGIN_FILE, AUDIO_OUTPUT_FILE, VIDEO_OUTPUT_FILE)
        return VIDEO_OUTPUT_FILE
    except Exception as e:
        print(f"Error creating video: {e}")
        return None

def reset_ui():
    return None, "en"

def gradio_interface(prompt, app):
    with gr.Blocks(analytics_enabled=False) as demo:
        gr.Markdown("# Ask Shelly")

        with gr.Row():
            with gr.Column(scale=1, min_width=200):
                text_input = gr.Textbox(label="Your question here", lines=3, max_lines=3, scale=0.7)
                language_codes = asyncio.run(list_language_codes())  # Fetch language codes asynchronously
                language_selector = gr.Dropdown(
                    label="Select Voice Locale",
                    choices=language_codes,  # Populate dropdown with language codes
                    value="en",  # Default choice
                    scale=0.7
                )

                with gr.Row():
                    send_button = gr.Button("Send", scale=0.7)
                    new_question_button = gr.Button("New Question", scale=0.7)

                video_output = gr.Video(label="Generated Answer Video", scale=0.7)

            with gr.Column(scale=1, min_width=200):
                audio_input = gr.Audio(type="filepath", label="Record your question", scale=0.7)
                transcribe_button = gr.Button("Audio to Text", scale=0.7)

        transcribe_button.click(handle_audio_upload, inputs=audio_input, outputs=text_input)

        # Asynchronous function wrapper for Gradio
        async def async_handle_send(question, language_code):
            return await handle_response(question, language_code, prompt)

        def handle_send(question, language_code):
            asyncio.run(initialize_voices())    
            return asyncio.run(async_handle_send(question, language_code))

        send_button.click(
            handle_send,
            inputs=[text_input, language_selector],
            outputs=video_output
        )
        new_question_button.click(reset_ui, outputs=[audio_input, text_input, video_output, language_selector])

    return gr.mount_gradio_app(app, demo, path="/")


def run(app):

    file_path = "assets/Prompt.txt"
    try:
     
        with open(file_path, 'r') as file:
            ourPrompt = file.read()
    except FileNotFoundError:
        print(f"The file at {file_path} was not found.")
    except IOError:
        print(f"An error occurred while reading the file at {file_path}.") 


    return gradio_interface(ourPrompt, app)
    