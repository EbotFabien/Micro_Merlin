import os
import json
import base64
import time
import random
import asyncio, logging
from aiologger import Logger
from dataclasses import dataclass
from quart_schema import validate_querystring
from quart import Quart, request, jsonify, Response, websocket
from twilio.twiml.voice_response import VoiceResponse, Connect, Say, Stream
from quart_schema import QuartSchema, validate_request, validate_response, Info
from dotenv import load_dotenv
import websockets

load_dotenv()
logger = Logger.with_default_handlers(level=logging.INFO)

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')  # Requires OpenAI Realtime API Access
PORT = int(os.getenv('PORT', 5002))
SYSTEM_MESSAGE = (
    "You are a helpful and bubbly AI assistant called Daniel,"
    "You work as a call center agent for the company called Acme Corporation."
    "When a client calls greet them and speak in fluent English, but you can adapt to their native language."
    "Be engaging, and try to make the customer feel comfortable. You can make some jokes and be funny."
    "Please speak quickly and be concise like 20 words or less."
)
VOICE = 'echo'
LOG_EVENT_TYPES = [
    'response.content.done', 'rate_limits.updated', 'response.done',
    'input_audio_buffer.committed', 'input_audio_buffer.speech_stopped',
    'input_audio_buffer.speech_started', 'session.created'
]

app = Quart(__name__)
QuartSchema(app, info=Info(title="My Great API", version="0.1.0"))

if not OPENAI_API_KEY:
    raise ValueError('Missing the OpenAI API key. Please set it in the .env file.')


@dataclass
class Event:
    message: str | None

@dataclass
class Query:
    count_le: int | str 
    count_gt: int | str
    message: Event

@app.get("/")
@validate_response(Event, 201)
@validate_querystring(Query)
async def index_page(query_args: Query):
    """
    Home of Twilio Media Stream Server.
    <p>Just the test page.</p>
    
    """
    return {"message": "Twilio Media Stream Server is running!"}, 201

@app.route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call():
    """
    Handle Incoming Call.
    <p>Handle incoming call and return TwiML response to connect to Media Stream.</p>
    
    """
    response = VoiceResponse()
    response.say("Please wait a while.")
    host = request.host  # This includes the hostname and port
    connect = Connect()
    connect.stream(url=f'wss://{host}/media-stream')
    response.append(connect)
    return Response(str(response), mimetype='application/xml')

@app.websocket('/media-stream')
async def handle_media_stream():
    """Handle WebSocket connections between Twilio and OpenAI."""
    print("Client connected")
    async with websockets.connect(
        'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
        extra_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }
    ) as openai_ws:
        await send_session_update(openai_ws)
        stream_sid = None

        async def receive_from_twilio():
            """Receive audio data from Twilio and send it to the OpenAI Realtime API."""
            nonlocal stream_sid
            try:
                while True:
                    message = await websocket.receive()
                    data = json.loads(message)
                    if data['event'] == 'media' and openai_ws.open:
                        audio_append = {
                            "type": "input_audio_buffer.append",
                            "audio": data['media']['payload']
                        }
                        await openai_ws.send(json.dumps(audio_append))
                    elif data['event'] == 'start':
                        stream_sid = data['start']['streamSid']
            except Exception as e:
                print(f"Client disconnected: {e}")
                if openai_ws.open:
                    await openai_ws.close()

        async def send_to_twilio():
            """Receive events from the OpenAI Realtime API, send audio back to Twilio."""
            nonlocal stream_sid
            try:
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)
                    if response['type'] in LOG_EVENT_TYPES:
                        pass
                    if response['type'] == 'input_audio_buffer.speech_stopped':
                        time.sleep(random.uniform(0, 1))
                        await websocket.send(json.dumps({"event": "clear", "streamSid": stream_sid}))
                    if response['type'] == 'response.audio.delta' and response.get('delta'):
                        try:
                            audio_payload = base64.b64encode(
                                base64.b64decode(response['delta'])
                            ).decode('utf-8')
                            audio_delta = {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": audio_payload
                                }
                            }
                            await websocket.send(json.dumps(audio_delta))
                        except Exception as e:
                            print(f"Error processing audio data: {e}")
                    if response['type'] == 'response.text.done':
                        await logger.info(f"AI: {response['text']}")
                    if response['type'] == 'conversation.item.input_audio_transcription.completed':
                        await logger.info(f"User: {response['transcript']}")
            except Exception as e:
                print(f"Error in send_to_twilio: {e}")

        await asyncio.gather(receive_from_twilio(), send_to_twilio())

async def send_session_update(openai_ws):
    """Send session update to OpenAI WebSocket."""
    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 200
            },
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": SYSTEM_MESSAGE,
            "modalities": ["text", "audio"],
            "temperature": 0.8,
        }
    }
    await openai_ws.send(json.dumps(session_update))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)