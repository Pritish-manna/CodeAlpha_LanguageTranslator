"""AI-Powered Language Translator - Streamlit front end.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import html

import streamlit as st

from src.languages import (
    AUTO_DETECT_LABEL,
    DEFAULT_SOURCE,
    DEFAULT_TARGET,
    LanguageOptions,
    SameLanguageError,
    build_language_options,
    get_language_name,
    resolve_language_pair,
    swap_languages,
)
from src.text_to_speech import is_tts_supported, synthesize_speech
from src.translator import (
    TranslatorBackend,
    create_backend,
    demo_translate,
    get_demo_examples,
    translate_text_detailed,
)
from src.utils import (
    HISTORY_LIMIT,
    AppError,
    Settings,
    add_history_entry,
    build_copy_button_html,
    count_characters,
    get_logger,
    load_settings,
    make_history_entry,
    validate_text,
)

logger = get_logger("translation_tool.app")

st.set_page_config(page_title="AI-Powered Language Translator", page_icon="🌐", layout="wide")


def build_custom_css(dark_mode: bool) -> str:
    """Return theme-aware glassmorphism styling for the Streamlit interface."""
    if dark_mode:
        palette = {
            "bg": "#08111f",
            "surface": "rgba(18, 31, 52, 0.72)",
            "surface_strong": "rgba(22, 38, 62, 0.88)",
            "text": "#edf4ff",
            "muted": "#a9b9d0",
            "border": "rgba(170, 198, 235, 0.17)",
            "accent": "#83aaff",
            "accent2": "#9a8cff",
            "input": "rgba(7, 17, 32, 0.72)",
            "shadow": "rgba(0, 0, 0, 0.28)",
        }
    else:
        palette = {
            "bg": "#edf3fb",
            "surface": "rgba(255, 255, 255, 0.70)",
            "surface_strong": "rgba(255, 255, 255, 0.92)",
            "text": "#15243b",
            "muted": "#63748d",
            "border": "rgba(91, 119, 158, 0.18)",
            "accent": "#315fe8",
            "accent2": "#7359df",
            "input": "rgba(255, 255, 255, 0.78)",
            "shadow": "rgba(42, 66, 105, 0.10)",
        }

    dark_sidebar_css = ""
    if dark_mode:
        dark_sidebar_css = """
/* Sidebar history cards */
[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: #192b43 !important;
    border: 1px solid rgba(170, 198, 235, 0.40) !important;
    border-radius: 12px !important;
    margin-bottom: 10px !important;
    overflow: hidden !important;
}

/* History heading */
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    background: #263c59 !important;
    color: #ffffff !important;
}

[data-testid="stSidebar"] [data-testid="stExpander"] summary * {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    font-weight: 650 !important;
}

/* History content */
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    background: #192b43 !important;
    color: #edf4ff !important;
}

[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stText"],
[data-testid="stSidebar"] [data-testid="stExpander"] p,
[data-testid="stSidebar"] [data-testid="stExpander"] pre,
[data-testid="stSidebar"] [data-testid="stExpander"] span {
    color: #edf4ff !important;
    -webkit-text-fill-color: #edf4ff !important;
}

/* History labels and timestamps */
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {
    color: #c5d4e8 !important;
    -webkit-text-fill-color: #c5d4e8 !important;
}

/* Connection status messages */
[data-testid="stSidebar"] [data-testid="stAlert"],
[data-testid="stSidebar"] [data-testid="stAlert"] > div,
[data-testid="stSidebar"] [role="alert"] {
    background: #19364d !important;
    border: 1px solid rgba(130, 190, 235, 0.50) !important;
    border-radius: 10px !important;
    color: #f1f6ff !important;
}

[data-testid="stSidebar"] [data-testid="stAlert"] *,
[data-testid="stSidebar"] [role="alert"] * {
    color: #f1f6ff !important;
    -webkit-text-fill-color: #f1f6ff !important;
}

/* Demo mode and theme toggles */
[data-testid="stSidebar"] [data-testid="stToggle"] {
    background: rgba(35, 53, 78, 0.85) !important;
    border: 1px solid rgba(170, 198, 235, 0.35) !important;
    border-radius: 10px !important;
    padding: 10px 12px !important;
    margin-bottom: 8px !important;
}

[data-testid="stSidebar"] [data-testid="stToggle"] label,
[data-testid="stSidebar"] [data-testid="stToggle"] label *,
[data-testid="stSidebar"] [data-testid="stToggle"] p {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    font-weight: 600 !important;
}

/* Sidebar headings and general text */
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label {
    color: #edf4ff;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
    color: #edf4ff;
}
"""

    return f"""
<style>
{dark_sidebar_css}

:root {{
  --app-bg: {palette['bg']};
  --glass: {palette['surface']};
  --glass-strong: {palette['surface_strong']};
  --ink: {palette['text']};
  --muted: {palette['muted']};
  --glass-border: {palette['border']};
  --accent: {palette['accent']};
  --accent-two: {palette['accent2']};
  --field: {palette['input']};
  --glass-shadow: {palette['shadow']};
}}

.stApp {{
  background:
    radial-gradient(ellipse at 8% 3%, rgba(87, 126, 255, .16), transparent 34%),
    radial-gradient(ellipse at 92% 10%, rgba(153, 112, 255, .14), transparent 32%),
    linear-gradient(145deg, var(--app-bg), var(--app-bg));
  color: var(--ink);
}}

[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stAppViewContainer"] {{ background: transparent; }}
.block-container {{ max-width: 1440px; padding-top: 2rem; padding-bottom: 3rem; }}

h1, h2, h3, p, label, [data-testid="stMarkdownContainer"] {{
  color: var(--ink);
}}

.hero {{
  padding: 1.55rem 1.7rem;
  border: 1px solid var(--glass-border);
  border-radius: 25px;
  background: linear-gradient(125deg, var(--glass-strong), var(--glass));
  box-shadow: 0 18px 50px var(--glass-shadow);
  backdrop-filter: blur(22px);
  -webkit-backdrop-filter: blur(22px);
  margin: .25rem 0 1.3rem 0;
}}

.hero-kicker {{
  color: var(--accent);
  font-size: .76rem;
  font-weight: 800;
  letter-spacing: .15em;
  text-transform: uppercase;
}}

.hero-title {{
  color: var(--ink);
  font-size: clamp(1.8rem, 4vw, 2.8rem);
  font-weight: 800;
  letter-spacing: -.045em;
  line-height: 1.1;
  margin: .35rem 0;
}}

.hero-subtitle {{
  color: var(--muted);
  font-size: 1rem;
  margin: .4rem 0 0 0;
}}

.glass-panel [data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stVerticalBlockBorderWrapper"] {{
  border: 1px solid var(--glass-border) !important;
  border-radius: 22px !important;
  background: linear-gradient(145deg, var(--glass-strong), var(--glass)) !important;
  box-shadow: 0 14px 36px var(--glass-shadow) !important;
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}}

[data-testid="stTextArea"] textarea,
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] [data-baseweb="select"] > div {{
  color: var(--ink) !important;
  background: var(--field) !important;
  border: 1px solid var(--glass-border) !important;
  border-radius: 14px !important;
}}

textarea {{
  min-height: 245px;
  line-height: 1.65 !important;
}}

[data-testid="stTextArea"] textarea::placeholder {{
  color: var(--muted) !important;
}}

[data-testid="stButton"] button,
[data-testid="stDownloadButton"] button {{
  border: 1px solid var(--glass-border) !important;
  border-radius: 13px !important;
  background: var(--glass-strong) !important;
  color: var(--ink) !important;
  font-weight: 650 !important;
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
  box-shadow: 0 5px 16px var(--glass-shadow);
}}

[data-testid="stButton"] button:hover,
[data-testid="stDownloadButton"] button:hover {{
  transform: translateY(-2px);
  border-color: var(--accent) !important;
  box-shadow: 0 9px 22px var(--glass-shadow);
}}

[data-testid="stButton"] button[kind="primary"] {{
  color: #fff !important;
  border: 0 !important;
  background: linear-gradient(110deg, var(--accent), var(--accent-two)) !important;
  box-shadow: 0 10px 25px rgba(67, 100, 220, .25) !important;
  min-height: 3rem;
  font-size: 1rem;
}}

[data-testid="stSelectbox"] label,
[data-testid="stTextArea"] label {{
  color: var(--muted) !important;
  font-weight: 700 !important;
}}

[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, var(--glass-strong), var(--glass));
  border-right: 1px solid var(--glass-border);
}}

[data-testid="stSidebar"] > div {{ background: transparent; }}

.tt-output {{
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  padding: 1.05rem 1.1rem;
  min-height: 245px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--ink);
  background: var(--field);
  font-size: 1.05rem;
  line-height: 1.7;
}}

.tt-placeholder {{
  color: var(--muted);
  display: flex;
  align-items: center;
}}

.tt-meta {{
  color: var(--muted);
  font-size: .82rem;
  margin: .65rem 0 .8rem;
}}

.tt-swap-spacer {{ height: 2.05rem; }}

.metric-chip {{
  display: inline-block;
  padding: .38rem .75rem;
  margin: .3rem .35rem 0 0;
  border: 1px solid var(--glass-border);
  border-radius: 999px;
  color: var(--muted);
  background: var(--glass);
  font-size: .78rem;
  font-weight: 650;
}}

.section-label {{
  color: var(--muted);
  font-size: .76rem;
  font-weight: 800;
  letter-spacing: .12em;
  text-transform: uppercase;
}}

hr {{ border-color: var(--glass-border) !important; }}

.stCaption,
[data-testid="stCaptionContainer"] {{
  color: var(--muted) !important;
}}

@media (max-width: 760px) {{
  .block-container {{ padding: 1rem .8rem 2rem; }}
  .hero {{ padding: 1.2rem; border-radius: 19px; }}
  textarea {{ min-height: 190px; }}
  .tt-output {{ min-height: 190px; }}
}}
</style>
"""



# ----------------------------------------------------------------------------
# Gemini backend and language loading
# ----------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_cached_backend(
    api_key: str,
    model: str,
    timeout: float,
) -> TranslatorBackend:
    return create_backend(
        api_key=api_key,
        model=model,
        timeout=timeout,
    )


def load_backend(settings: Settings) -> tuple[TranslatorBackend | None, str | None]:
    if not settings.gemini_api_key:
        return None, "Gemini API key not found. Add GEMINI_API_KEY to your .env file."

    try:
        backend = get_cached_backend(
            settings.gemini_api_key,
            settings.gemini_model,
            settings.timeout_seconds,
        )
        return backend, None

    except AppError as exc:
        return None, exc.user_message

    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error while creating the Gemini client")
        return None, "Could not create the Gemini client."


def load_language_options(
    backend: TranslatorBackend | None,
    demo: bool,
    timeout: float,
) -> tuple[LanguageOptions, str | None]:
    return build_language_options(None), None

# ----------------------------------------------------------------------------
# Session state and callbacks (callbacks run before widgets are created, so they
# may safely change widget-bound keys such as source_lang / input_text)
# ----------------------------------------------------------------------------


def init_state(options: LanguageOptions, default_demo: bool) -> None:
    state = st.session_state
    state.setdefault("source_lang", DEFAULT_SOURCE)
    state.setdefault("target_lang", DEFAULT_TARGET)
    state.setdefault("input_text", "")
    state.setdefault("history", [])
    state.setdefault("result", None)
    state.setdefault("result_counter", 0)
    state.setdefault("audio", None)
    state.setdefault("flash", None)
    state.setdefault("demo_mode", default_demo)

    if state["source_lang"] not in options.source:
        state["source_lang"] = DEFAULT_SOURCE
    if state["target_lang"] not in options.target:
        state["target_lang"] = DEFAULT_TARGET if DEFAULT_TARGET in options.target else next(iter(options.target))


def on_clear() -> None:
    st.session_state["input_text"] = ""
    st.session_state["result"] = None
    st.session_state["audio"] = None


def on_swap(options: LanguageOptions) -> None:
    state = st.session_state
    result = state.get("result")
    detected_name = result.get("detected_name") if result else None
    outcome = swap_languages(state["source_lang"], state["target_lang"], detected_name, options)
    if not outcome.swapped:
        state["flash"] = ("info", outcome.message)
        return
    state["source_lang"] = outcome.source
    state["target_lang"] = outcome.target
    if result:  # move the translation into the input so the swap round-trips
        state["input_text"] = result["translated_text"]
        state["result"] = None
        state["audio"] = None


def on_example(text: str) -> None:
    state = st.session_state
    state["input_text"] = text
    state["source_lang"] = AUTO_DETECT_LABEL
    state["result"] = None
    state["audio"] = None


def on_clear_history() -> None:
    st.session_state["history"] = []


# ----------------------------------------------------------------------------
# Actions
# ----------------------------------------------------------------------------


def handle_translate(
    options: LanguageOptions,
    backend: TranslatorBackend | None,
    backend_error: str | None,
    settings: Settings,
    demo: bool,
) -> None:
    """Validate, translate (only when the button was clicked) and store the result."""
    state = st.session_state
    try:
        text = validate_text(state["input_text"], settings.max_input_chars)
        source_code, target_code = resolve_language_pair(state["source_lang"], state["target_lang"], options)

        if not demo and backend is None:
            st.error(backend_error or "Gemini API key is not configured.")
            st.caption("Switch on Demo mode in the sidebar to try sample phrases without credentials.")
            return

        with st.spinner("Translating..."):
            if demo:
                result = demo_translate(text, source_code, target_code, max_chars=settings.max_input_chars)
            else:
                result = translate_text_detailed(
                    text,
                    source_code,
                    target_code,
                    backend=backend,
                    timeout=settings.timeout_seconds,
                    max_chars=settings.max_input_chars,
                    supported_source=[c for c in options.source.values() if c] if options.verified_with_api else None,
                    supported_target=list(options.target.values()) if options.verified_with_api else None,
                )
    except SameLanguageError as exc:
        st.info(exc.user_message)
        return
    except AppError as exc:
        st.error(exc.user_message)
        return
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error during translation")
        st.error("An unexpected error occurred. No translation was produced. Please try again.")
        return

    state["result_counter"] += 1
    result_id = state["result_counter"]
    detected_name = get_language_name(result.detected_language, options) if result.detected_language else None
    source_label = state["source_lang"]
    if detected_name and source_label == AUTO_DETECT_LABEL:
        source_label = f"{AUTO_DETECT_LABEL} ({detected_name})"
    state["result"] = {
        "id": result_id,
        "translated_text": result.translated_text,
        "source_label": source_label,
        "target_name": state["target_lang"],
        "target_code": result.target_language,
        "detected_name": detected_name,
        "is_demo": result.is_demo,
    }
    state["audio"] = None
    add_history_entry(
        state["history"],
        make_history_entry(
            text,
            result.translated_text,
            source_label,
            state["target_lang"],
            is_demo=result.is_demo,
            entry_id=result_id,
        ),
        HISTORY_LIMIT,
    )
    st.success("Translation complete." if not result.is_demo else "Demo result shown (not a real API translation).")
    if detected_name and detected_name == state["target_lang"]:
        st.info(f"The detected language ({detected_name}) is the same as the target, so the text is unchanged.")


def render_copy_button(text: str) -> None:
    """Render the clipboard button (sandboxed iframe with a small script)."""
    document = build_copy_button_html(text)
    if hasattr(st, "iframe"):  # Streamlit >= 1.56
        st.iframe(document, height=56)
    else:  # pragma: no cover - older Streamlit
        import streamlit.components.v1 as components

        components.html(document, height=56)


# ----------------------------------------------------------------------------
# Page
# ----------------------------------------------------------------------------

settings = load_settings()
backend, backend_error = load_backend(settings)

# Theme preference is session-local and can be changed at any time.
st.session_state.setdefault("dark_mode", True)
dark_mode = bool(st.session_state["dark_mode"])

# Demo mode defaults to ON only when no real client could be created.
st.session_state.setdefault("demo_mode", backend is None)
demo_mode: bool = bool(st.session_state["demo_mode"])

options, language_warning = load_language_options(backend, demo_mode, settings.timeout_seconds)
init_state(options, default_demo=backend is None)

st.markdown(build_custom_css(dark_mode), unsafe_allow_html=True)

# ---- sidebar ---------------------------------------------------------------
with st.sidebar:
    st.markdown("## ✦ Translate Studio")
    st.caption("AI-powered language workspace")
    st.toggle("Dark glass theme", key="dark_mode", help="Switch between dark and light appearance.")
    st.divider()

    st.markdown("### Connection")
    if backend is not None:
        st.success(f"Gemini client ready · {settings.gemini_model}")
        st.caption("The API key is configured. Gemini validates it on the first live translation.")
    else:
        st.warning(backend_error or "Gemini API key was not found.")
    st.toggle(
        "Demo mode",
        key="demo_mode",
        help="Uses built-in sample phrases only. Demo results are never presented as live translations.",
    )
    if demo_mode:
        st.info("Demo mode is active. Choose a built-in example to try it.")
    else:
        st.caption("Live translations are processed by Gemini and subject to your API quota.")

    if language_warning:
        st.warning(language_warning)

    st.divider()
    st.markdown("### Quick guide")
    st.markdown(
        "1. Enter or paste your text.\n"
        "2. Choose the source and target languages.\n"
        "3. Select **Translate**.\n"
        "4. Copy, download, or listen to the result."
    )
    with st.expander("Supported languages"):
        st.write(", ".join(options.target.keys()))

    st.markdown("### Try a sample")
    st.button("नमस्ते · Hindi greeting", key="ex_hi", on_click=on_example,
              args=("नमस्ते, आप कैसे हैं?",), width="stretch")
    english_examples = get_demo_examples()
    st.button("Good morning · English", key="ex_en", on_click=on_example,
              args=(english_examples[2],), width="stretch")

    st.divider()
    st.markdown("### Recent translations")
    st.caption("Stored only in this browser session.")
    history = st.session_state["history"]
    if not history:
        st.caption("Your recent translations will appear here.")
    else:
        for entry in reversed(history[-8:]):
            demo_tag = " · DEMO" if entry.get("is_demo") else ""
            with st.expander(f"{entry['source']} → {entry['target']}{demo_tag}"):
                st.caption(entry["timestamp"])
                st.caption("Original")
                st.text(entry["original"][:240])
                st.caption("Translation")
                st.text(entry["translated"][:240])
        st.button("Clear history", key="clear_history_btn", on_click=on_clear_history, width="stretch")

    st.divider()
    st.caption("Built with Python · Streamlit · Gemini · gTTS")


# ---- hero ------------------------------------------------------------------
st.markdown(
    """
    <div class="hero">
      <div class="hero-kicker">✦ Language intelligence workspace</div>
      <div class="hero-title">Say it in every language.</div>
      <div class="hero-subtitle">Thoughtful translations, clear language controls, and a calm workspace for every conversation.</div>
      <div>
        <span class="metric-chip">15 built-in languages</span>
        <span class="metric-chip">Auto language detection</span>
        <span class="metric-chip">Text-to-speech</span>
        <span class="metric-chip">Private session history</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- translation workspace -------------------------------------------------
left, middle, right = st.columns([10, 1.5, 10], gap="medium")

with left:
    with st.container(border=True):
        st.markdown('<div class="section-label">01 · Your text</div>', unsafe_allow_html=True)
        st.selectbox("Translate from", list(options.source), key="source_lang")
        st.text_area(
            "Text to translate",
            key="input_text",
            height=250,
            placeholder="Write or paste something to translate...",
            label_visibility="collapsed",
        )
        count_col, clear_col = st.columns([3, 2])
        current_count = count_characters(st.session_state["input_text"])
        count_col.caption(f"{current_count:,} / {settings.max_input_chars:,} characters")
        clear_col.button("Clear text", key="clear_btn", on_click=on_clear,
                         width="stretch", help="Clear input and output")

with middle:
    st.markdown('<div class="tt-swap-spacer"></div>', unsafe_allow_html=True)
    st.button("⇄", key="swap_btn", on_click=on_swap, args=(options,),
              width="stretch", help="Swap source and target languages")

with right:
    with st.container(border=True):
        st.markdown('<div class="section-label">02 · Translation</div>', unsafe_allow_html=True)
        st.selectbox("Translate to", list(options.target), key="target_lang")
        result = st.session_state.get("result")
        if result is None:
            st.html('<div class="tt-output tt-placeholder" dir="auto">Your translated text will appear here.\n\nChoose your languages and start translating.</div>')
        else:
            translated = result["translated_text"]
            if result["is_demo"]:
                st.warning("DEMO RESULT · This is a built-in sample, not a live AI translation.")
            st.html(f'<div class="tt-output" dir="auto">{html.escape(translated)}</div>')
            meta = f"From: {result['source_label']} · To: {result['target_name']} · {count_characters(translated):,} characters"
            if result["detected_name"]:
                meta += f" · Detected: {result['detected_name']}"
            st.html(f'<div class="tt-meta">{html.escape(meta)}</div>')

            copy_col, listen_col, download_col = st.columns(3)
            with copy_col:
                render_copy_button(translated)
            tts_ok = is_tts_supported(result["target_code"])
            listen_clicked = listen_col.button(
                "Listen", key="listen_btn", disabled=not tts_ok,
                width="stretch", help="Generate speech using gTTS (internet required)",
            )
            download_col.download_button(
                "Download", data=translated.encode("utf-8"),
                file_name="translation.txt", mime="text/plain",
                key="download_btn", width="stretch",
            )
            if not tts_ok:
                st.caption(f"Text-to-speech is not available for {result['target_name']}.")
            if listen_clicked:
                try:
                    with st.spinner("Generating speech..."):
                        audio_bytes = synthesize_speech(translated, result["target_code"])
                    st.session_state["audio"] = {"result_id": result["id"], "data": audio_bytes}
                except AppError as exc:
                    st.error(exc.user_message)
            audio = st.session_state.get("audio")
            if audio and audio["result_id"] == result["id"]:
                st.audio(audio["data"], format="audio/mpeg")
                st.caption("Speech is generated by gTTS, separately from Gemini translation.")

st.markdown("")
translate_clicked = st.button("✦  Translate now", key="translate_btn",
                              type="primary", width="stretch")
if translate_clicked:
    handle_translate(options, backend, backend_error, settings, demo_mode)

# Display callback messages after the action area.
flash = st.session_state.get("flash")
st.session_state["flash"] = None
if flash:
    level, message = flash
    getattr(st, level, st.info)(message)

st.markdown(
    '<div style="text-align:center; padding:1.5rem 0 .4rem; color:var(--muted); font-size:.78rem;">'
    'AI translation workspace · Gemini-powered · Your history stays in this session</div>',
    unsafe_allow_html=True,
)
