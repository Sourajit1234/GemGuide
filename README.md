GemGuide
---

AI Powered Computer Usage Interface for the Physically Disabled
An AI-powered accessibility interface that enables physically disabled users to control and use a computer efficiently using eye tracking, voice commands, and AI automation.
The project combines Gemma 4 as an intelligent AI agent, Parakeet for speech-to-text, and EyeTrax for eye gaze tracking — creating a seamless hands-free computing experience.

Features
EyeTrax is used for eye tracking, allowing users to control the mouse cursor using eye movement. Blinking is used for clicking.
Gemma 4 E4B model acts as an AI assistant agent capable of opening apps, folders, and files, typing text, copying content to the clipboard, and analyzing the screen using vision.
Uses Parakeet 0.6B v3 STT-TDT for real-time streaming speech-to-text.
Uses llama.cpp for efficient local inference on consumer devices.
One of the only free and open solutions that combines eye tracking, voice interaction, and AI computer control into a single software.
Powered by state-of-the-art (SOTA) AI models.

Minimum System Requirements
For acceptable performance and smooth local AI inference, the recommended minimum system requirements are:
16 GB RAM
8 GB VRAM (NVIDIA GPU recommended)

Development Setup
Download:
`gui_main.py`
`ai_full.py`
`server.py`
`voice_engine.py`
`tools.py`
Download the `libespeak-ng.dll` file from GitHub.
Create the following folders:
```text
llamacpp/bin
```
Download llama.cpp release binaries and place them inside:
```text
llamacpp/bin
```
Download the required files/models:
https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf
https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/blob/main/mmproj-F16.gguf
https://huggingface.co/google/gemma-4-E4B-it/blob/main/chat_template.jinja
Rename:
`gemma-4-E4B-it-Q4_K_M.gguf` → `google_gemma-4-E4B-it-Q4_K_M.gguf`
`mmproj-F16.gguf` → `mmproj-google_gemma-4-E4B-it-f16.gguf`
Place all downloaded models/files inside:
```text
models/
```
Install the required Python packages:
```bash
pip install -r requirements.txt
```
---
Project Structure
```text
ComputerUsage
│
├── llamacpp
│   └── bin
│
├── models
│   ├── chat_template.jinja
│   ├── google_gemma-4-E4B-it-Q4_K_M.gguf
│   ├── kokoro-v1.0.onnx
│   ├── mmproj-google_gemma-4-E4B-it-f16.gguf
│   └── voices-v1.0.bin
│
├── libespeak-ng.dll
│
├── ai_full.py
├── gui_main.py
├── server.py
├── tools.py
└── voice_engine.py
```
---
Running the Project
Run:
```bash
python gui_main.py
```
---
Tech Stack
Gemma 4 E4B — AI Assistant Agent
Parakeet 0.6B v3 STT-TDT — Streaming Speech Recognition
EyeTrax — Eye Gaze Tracking
llama.cpp — Efficient Local Inference Engine
---
Goal
The goal of this project is to make computers more accessible and usable for physically disabled users by combining modern AI systems with intuitive control mechanisms.
---
Note
Please note that the current project will run significantly faster once MTP support is officially added to llama.cpp. In that case, the codebase should be updated accordingly.
