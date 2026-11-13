# Language Translation Studio

A polished Streamlit language-translation workspace powered by the **Google Gemini API**. It includes automatic source-language detection, 15 built-in languages, a responsive glass-style interface, dark/light appearance, text-to-speech, copy/download actions, and session-only history.

## Features

- Gemini-powered translation with source-language auto-detection
- 15 built-in source/target languages: English, Hindi, Bengali, Spanish, French, German, Japanese, Chinese (Simplified), Arabic, Portuguese, Russian, Italian, Korean, Tamil, and Telugu
- Premium glassmorphism interface with dark and light theme toggle
- Responsive input/output workspace and language swapping
- Character counter and configurable input limit
- Copy translation and download as a UTF-8 `.txt` file
- Optional text-to-speech through gTTS
- Session-only recent translation history
- Clearly labelled demo mode with a small set of sample phrases
- Friendly error handling and automated tests with mocked Gemini responses

## Project structure

```text
Language-Translation-Tool/
├── app.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── pytest.ini
├── .streamlit/
│   └── config.toml
├── src/
│   ├── __init__.py
│   ├── languages.py
│   ├── text_to_speech.py
│   ├── translator.py
│   └── utils.py
├── tests/
│   ├── test_languages.py
│   ├── test_text_to_speech.py
│   ├── test_translator.py
│   └── test_utils.py
└── assets/
```

## Requirements

- Python 3.11 or newer
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey) for live translation
- Internet access for Gemini requests and gTTS audio generation

## Installation on Windows PowerShell

Open a terminal in the project folder and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run this in the same terminal and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Configure Gemini

1. Copy `.env.example` to `.env` in the project root.
2. Open `.env` and replace the placeholder with your own API key.
3. Keep `.env` private. Do not upload it to GitHub, share it in screenshots, or send it in ZIP files.

PowerShell commands:

```powershell
Copy-Item .env.example .env
notepad .env
```

Example `.env` format (use your own key, never this placeholder):

```env
GEMINI_API_KEY=replace_with_your_private_api_key
GEMINI_MODEL=gemini-3.8-flash
TRANSLATION_TIMEOUT_SECONDS=30
MAX_INPUT_CHARS=5000
LOG_LEVEL=INFO
```

The app reads the API key from the environment or `.env`. The API key is not hard-coded in Python source. If no key is configured, the app opens in demo mode.

## Run the application

From the project root, with the virtual environment activated:

```powershell
python -m streamlit run app.py
```

Streamlit will print a local address, usually `http://localhost:8501`. Open it in your browser. Use the sidebar to switch between dark and light appearance or enable demo mode.

## Run tests

```powershell
python -m pytest -q
```

The automated tests mock the Gemini client and do not require a real API key or make paid/live API calls.

## Security notes

- Never commit `.env`, API keys, service-account files, or private credentials.
- `.gitignore` excludes local environment files, virtual environments, Python caches, and common credential files.
- If an API key is accidentally shared, revoke it in Google AI Studio and create a replacement.
- Translation history is stored only in Streamlit session state and is not persisted to disk.
- Do not use demo results as evidence of live translation quality.

## Limitations

- The language dropdown uses a maintained built-in list; availability may vary by the Gemini model and API.
- Demo mode supports only the bundled sample phrases.
- gTTS is a separate online text-to-speech service and may not support every language.
- API usage is subject to the current Gemini model quotas and pricing shown in Google AI Studio.
- This project has not been live-tested with your private API key. Complete the manual check below after configuration.

## Manual verification checklist

- [ ] App opens in a browser without a Python traceback
- [ ] Dark/light theme toggle changes the interface
- [ ] Demo mode translates the bundled examples and clearly labels the result
- [ ] Live mode translates a short sentence after a valid API key is configured
- [ ] Auto Detect identifies a source language when Gemini returns it
- [ ] Swap, clear, copy, download, and history actions work
- [ ] Listen generates audio for a supported target language
- [ ] Missing/invalid API key shows a friendly error without exposing credentials
