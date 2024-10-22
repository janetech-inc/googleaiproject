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
import uuid
import json
import re
from google.cloud import datastore


nest_asyncio.apply()

CONTENT_PATH = os.environ.get("CONTENT_PATH", "./tmp/output")

# Constants
AUDIO_OUTPUT_FILE = f"{CONTENT_PATH}/AnswerAudioTest.mp3"
VIDEO_OUTPUT_FILE = f"{CONTENT_PATH}/AnswerVideo.mp4"
VIDEO_ORIGIN_FILE = "app/assets/ShellySpeak.mp4"
VIDEO_DEFAULT = "app/assets/WelcomeVideo.mp4"
FIRESORE_JSON_PATH = "app/assets/datastoreKey.json"



video_ready = False
language_codeG = "en"
questionG = ""

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

async def generate_audio(response_text, voice_name, audio_output_file):
    communicate = edge_tts.Communicate(response_text, voice_name)
    await communicate.save(audio_output_file)
    print(f"Audio saved to {audio_output_file}")

def create_video_with_audio_length(original_video_path, audio_path, output_video_path, temp_path):
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
    final_video_clip.write_videofile(output_video_path, 
                                     codec='libx264', 
                                     audio_codec='aac', 
                                     temp_audiofile=temp_path, 
                                #     threads=3, 
                                     remove_temp=True,
                                     verbose=False, 
                                     preset='ultrafast', 
                                     )

def get_audio_duration(audio_path):
    audio = AudioSegment.from_mp3(audio_path)
    return audio.duration_seconds

async def handle_response(question, selected_language_code, prompt):
    print(f"Selected language code: {selected_language_code}")
    global video_ready
    global language_codeG
    global geminiAnswerText
    global questionG

    genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
    
    full_voice_name = VOICE_OPTIONS.get(selected_language_code, 'en-US')  # Default to 'en-US' if not found
    locale_part = full_voice_name.split('(')[1].split(',')[0].strip()  # "en-US"
    language_code = locale_part.split('-')[0]  # "en"
    language_codeG = language_code
    questionG = question
    response = genai.GenerativeModel('gemini-pro').generate_content(prompt + language_code +"\n and this is the user question \n" + question)
    response_text = response.text
    geminiAnswerText = response_text
    
    temp_path = f"{CONTENT_PATH}/{uuid.uuid4()}/AnswerVideoTEMP_MPY_wvf_snd.mp4"
    audio_path = f"{CONTENT_PATH}/{uuid.uuid4()}/{AUDIO_OUTPUT_FILE}"
    video_path = f"{CONTENT_PATH}/{uuid.uuid4()}/{VIDEO_OUTPUT_FILE}"
    try:
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)
        os.makedirs(os.path.dirname(video_path), exist_ok=True)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        print(f"Generating audio for response: {response_text}")
        await generate_audio(response_text, full_voice_name, audio_path)
        print(f"Creating video with audio for response: {response_text}")
        create_video_with_audio_length(VIDEO_ORIGIN_FILE, audio_path, video_path, temp_path)
        print
        video_ready = True
        return video_path
    except Exception as e:
        print(f"Error creating video: {e}")
        return None
 
def handle_suggestions(suggestionsPrompt):
    if not video_ready:
        return "You can get suggestions when the video becomes ready."
    else:
        response_suggestions = genai.GenerativeModel('gemini-pro').generate_content(suggestionsPrompt + language_codeG +"\n and this is the user question \n" + questionG)
        print(response_suggestions.text)
        suggestions = extract_suggestions(response_suggestions.text)
        return format_suggestions_as_html(suggestions)
client = datastore.Client.from_service_account_json(FIRESORE_JSON_PATH)

def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

def subscribe_save_user_data(name, email):
    client = datastore.Client.from_service_account_json(FIRESORE_JSON_PATH)
    if not name or not email:
        return "Name and email are required."
    if not is_valid_email(email):
        return "Invalid email format."
    
    # Check if the email already exists
    query = client.query(kind='User')
    query.add_filter('email', '=', email)
    existing_user = list(query.fetch())
    
    if existing_user:
        return "Email is already subscribed."

    entity = datastore.Entity(key=client.key('User'))
    entity.update({'username': name, 'email': email})
    client.put(entity)
    
    return "You Subscribed Successfully!🎉"

def extract_suggestions(text):
    pattern = re.compile(r'([^\[]+?)(?:\[(?:[^\]]+?)\])?\((https?://[^\)]+)\)')
    matches = pattern.findall(text)
    suggestions = [{"text": match[0].strip(), "url": match[1]} for match in matches]
    return suggestions

def format_suggestions_as_html(suggestions):
    html_content = ""
    for suggestion in suggestions:
        html_content += f'<a href="{suggestion["url"]}" target="_blank">{suggestion["text"]}</a><br>'
    return html_content


theme = gr.themes.Default(primary_hue="green").set(
    button_primary_background_fill="#388e3c",
    button_primary_background_fill_hover="#66bb6a",
)
def read_css_file(filename):
    with open(filename, 'r') as file:
        return file.read()


def gradio_interface(prompt,suggestionsPrompt,app):
    css = read_css_file('app/assets/styles.css')
    with gr.Blocks(analytics_enabled=False,css=css,theme=theme , title="Shelly Bot" ) as demo:
        gr.HTML("""
            <div class="header">
                <div class="title">
                    <h1><i class='fas fa-question-circle'></i> ASK Shelly!! </h1>
                </div>
                <span class="turtle">🐢</span> <!-- Turtle emoji element -->
            </div>
        """)
        with gr.Row():
            with gr.Column(scale=2, min_width=200):
                with gr.Row():
                    with gr.Column():
                        video_output = gr.Video(
                            label="Shelly's Answer",
                            scale=1.0, elem_classes="fixed-size-video",
                            value=VIDEO_DEFAULT,
                            autoplay=True     
                            )  
                question_input = gr.Textbox(label="Question", placeholder="Write Your question here, or Record it", lines=2, max_lines=3, scale=0.5)
                language_codes = asyncio.run(list_language_codes())  # Fetch language codes asynchronously
                language_selector = gr.Dropdown(
                    label="Answer Language",
                    choices=language_codes,  # Populate dropdown with language codes
                    value="en",  # Default choice
                    scale=0.7
                )
                suggestions_output = gr.HTML(label="Shelly Suggestions")  # Changed to gr.HTML

                with gr.Row():
                     send_button = gr.Button("Send", scale=1, elem_classes="gradio-button")
                     suggestions_button = gr.Button("Shelly Suggestions", scale=1, elem_classes="gradio-button")  
                gr.HTML("""
                    <div style="text-align: center; margin-top: 10px;">
                        <span style="font-weight: bold; color: #4caf50; cursor: pointer;font-size: 16px;" onclick="window.location.reload();">
                            New Question
                        </span>
                    </div>
                """)
                    #new_question_button = gr.Button("New Question", scale=0.7, elem_classes="gradio-button")

            with gr.Column(scale=1, min_width=200):
                audio_input = gr.Audio(type="filepath", label="Record your question", scale=0.7)
                transcribe_button = gr.Button("Audio to Text", scale=0.7)
                gr.HTML("""
                    <p style="text-align: center; font-size: 14 px; font-weight: bold; color: #333;">
                        You can SUBSCRIBE to receive the latest educational news
                    </p>
                """)
                name_input = gr.Textbox(label="Name", placeholder="Enter your name", lines=1, scale=0.7)
                email_input = gr.Textbox(label="Email", placeholder="Enter your email", lines=1, scale=0.7)
                subscribe_button = gr.Button("Subscribe", scale=0.7)
                result_output = gr.HTML(elem_id="result-output")

               

        transcribe_button.click(handle_audio_upload, inputs=audio_input, outputs=question_input)

        # Asynchronous function wrapper for Gradio
        async def async_handle_send(question, language_code):
            return await handle_response(question, language_code, prompt)

        def handle_send(question, language_code):
            asyncio.run(initialize_voices())    
            return asyncio.run(async_handle_send(question, language_code))

        def handle_suggestions_click():
            return handle_suggestions(suggestionsPrompt)

        def handle_subscription(name, email):
            result_message = subscribe_save_user_data(name, email)
            return f"<div style='text-align: center; font-size: 14px; color: gray ;'>{result_message}</div>"


        send_button.click(
            handle_send,
            inputs=[question_input, language_selector],
            outputs=video_output
        )
      
        suggestions_button.click(
            handle_suggestions_click,
            outputs=suggestions_output
        )

        subscribe_button.click(
            handle_subscription,
            inputs=[name_input, email_input],
            outputs=result_output
        )
    return gr.mount_gradio_app(app, demo, path="/")


def run(app):

    file_path = "app/assets/Prompt.txt"
    file_path2 = "app/assets/SuggestionsPrompt.txt"  

    try:
     
        with open(file_path, 'r') as file:
            ourPrompt = file.read()
    except FileNotFoundError:
        print(f"The file at {file_path} was not found.")
    except IOError:
        print(f"An error occurred while reading the file at {file_path}.") 

    try:
         with open(file_path2, 'r') as file:
           suggestionsPrompt = file.read()
    except FileNotFoundError:
        print(f"The file at {file_path2} was not found.")
    except IOError:
        print(f"An error occurred while reading the file at {file_path2}.")


    return gradio_interface(ourPrompt,suggestionsPrompt, app)
    
