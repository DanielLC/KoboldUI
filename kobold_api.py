import requests
import json
import re
import collections
import winsound
import threading
import random
import time

GENERATE_URL = 'http://localhost:5001/api/v1/generate'
POLL_URL = 'http://localhost:5001/api/extra/generate/check'
STREAM_URL = 'http://localhost:5001/api/extra/generate/stream'
TOKEN_COUNT = 'http://localhost:5001/api/extra/tokencount'
DETOKENIZE = 'http://localhost:5001/api/extra/detokenize'
ABORT = 'http://localhost:5001/api/extra/abort'
POLLING_PERIOD = 0.5

baseSettings = {
  "n": 1,
  "max_context_length": 2048,
  "rep_pen": 1.1,
  "top_p": 0.92,
  "top_k": 0,
  "top_a": 0,
  "typical": 1,
  "tfs": 1,
  "rep_pen_range": 320,
  "rep_pen_slope": 0.7,
  "sampler_order": [
    6,
    0,
    1,
    3,
    4,
    2,
    5
  ],
  "prompt": "This is a test of Kobold AI. This is just a test. Had this been a real emergency, I wouldn't keep saying it's a test.",
  "quiet": True,
  "stop_sequence": [
    "."
  ],
  "use_default_badwordsids": False,
}

#This prompts teh LLM, and prints the result. Note that it's polling it to see progress, so simply returning the result won't work. I'll need something more sophisticated.
def prompt(outFunction, text = '', memory = '', grammar = '', stopSequence = []):
    global genkey
    settings = baseSettings.copy()
    settings['prompt'] = text
    settings['stop_sequence'] = stopSequence
    settings['grammar'] = grammar
    settings['memory'] = memory
    settings['genkey'] = genkey
    
    result = [None]
    thread = threading.Thread(target=request, args=(settings, result))
    thread.start()
    thread.join(POLLING_PERIOD)
    while thread.is_alive():
        #response = requests.get(POLL_URL)
        response = requests.post(POLL_URL, json = {'genkey': genkey})
        outFunction(json.loads(response.text)['results'][0]['text'], False)
        #thread.join(POLLING_PERIOD)
    outFunction(result[0], True)
    return

#I think the thread is just being stuck here endlessly.
#Note to self: If this is what's happening, the abort button shouldn't continue the text. Does abort ever work correctly?
def stream_prompt(outFunction, text='', memory='', max_length=100, temperature=1, grammar='', stopSequence = []):
    global genkey
    settings = baseSettings.copy()
    genkey = ''.join([random.choice('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in range(10)])
    settings.update({'prompt': text, 'memory': memory, 'max_length': max_length, 'temperature': temperature, 'grammar': grammar, 'stop_sequence': stopSequence, 'genkey': genkey})
    prevTime = -1
    with requests.post(STREAM_URL, json=settings, stream=True) as resp:
        for line in resp.iter_lines(decode_unicode=True, chunk_size=1):
            #print(f"stream_prompt: {line}")
            if line.startswith('data: '):
                data = json.loads(line[6:])
                token = data.get('token')
                done = data.get('finish_reason') != 'null'
                outFunction(token, done)
                if done:
                    return

#This is run in a thread, so it can't return a result normally.
def request(settings, result):
    response = requests.post(GENERATE_URL, json = settings)
    text = json.loads(response.text)['results'][0]['text']
    result[0] = text

def tokenCount(text):
    response = requests.post(TOKEN_COUNT, json = {"prompt": text})
    result = json.loads(response.text)
    return result['value'], result['ids']

def detokenize(ids):
    response = requests.post(DETOKENIZE, json = {"ids": ids})
    return json.loads(response.text)['result']

def abort():
    print("Sending Abort request")
    requests.post(ABORT, json = {"genkey": genkey})

def mainLoop():
    while True:
        post(input())
        prompt()

def main():
    initialize()
    mainLoop()

if __name__ == "__main__":
    main()
