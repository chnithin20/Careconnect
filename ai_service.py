"""
CareConnect AI Service
Supports: Images (JPG/PNG/WEBP/BMP/GIF/TIFF), PDF, and text files.
Images are sent to an Ollama vision model (llava, bakllava, etc.).
Text/PDF uses a text model with model-fallback logic.
"""

import base64
import io
import logging
import os

import PyPDF2
import requests

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL    = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
DEFAULT_TEXT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")
OLLAMA_REQUEST_TIMEOUT_SEC = int(os.environ.get("OLLAMA_REQUEST_TIMEOUT_SEC", "45"))
OLLAMA_NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "1024"))
OLLAMA_NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "220"))

# Preferred vision models in order
_VISION_MODELS_PRIORITY = ["llava-med", "llava:13b", "llava:7b", "llava", "bakllava", "moondream"]

# Accepted MIME / extension groups
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif"}
TEXT_EXTENSIONS  = {".txt", ".csv", ".md", ".log", ".json", ".xml", ".html"}
PDF_EXTENSIONS   = {".pdf"}

ALL_ACCEPTED_EXTENSIONS = IMAGE_EXTENSIONS | TEXT_EXTENSIONS | PDF_EXTENSIONS


def is_image(filename: str) -> bool:
    return os.path.splitext(filename.lower())[1] in IMAGE_EXTENSIONS


def is_pdf(filename: str) -> bool:
    return os.path.splitext(filename.lower())[1] in PDF_EXTENSIONS


def is_supported(filename: str) -> bool:
    return os.path.splitext(filename.lower())[1] in ALL_ACCEPTED_EXTENSIONS


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_content: bytes) -> str:
    """Pull text out of a PDF binary blob."""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        pages  = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages.append(t)
        return "\n".join(pages).strip()
    except Exception as e:
        logger.error(f"PDF parse error: {e}")
        raise ValueError(f"Could not extract text from PDF: {e}")


def extract_text_from_text_file(file_content: bytes) -> str:
    """Decode a plain-text file."""
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return file_content.decode(enc).strip()
        except Exception:
            continue
    return file_content.decode("utf-8", errors="replace").strip()


def file_to_base64(file_content: bytes) -> str:
    """Encode binary content as a base64 string (for Ollama vision API)."""
    return base64.b64encode(file_content).decode("utf-8")


# ---------------------------------------------------------------------------
# Ollama helpers
# ---------------------------------------------------------------------------

def _get_installed_models() -> list[str]:
    """Return locally installed Ollama model names (smallest first by size)."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=4)
        if resp.status_code == 200:
            raw = resp.json().get("models", [])
            raw_sorted = sorted(raw, key=lambda m: m.get("size", float("inf")))
            return [m["name"] for m in raw_sorted if m.get("name")]
    except Exception as e:
        logger.warning(f"Cannot reach Ollama at {OLLAMA_BASE_URL}: {e}")
    return []


def _get_vision_model() -> str | None:
    """Find the best available vision-capable model."""
    installed = _get_installed_models()
    installed_lower = {m.lower(): m for m in installed}

    # Check priority list first
    for pref in _VISION_MODELS_PRIORITY:
        if pref.lower() in installed_lower:
            return installed_lower[pref.lower()]
        # Partial match: e.g. "llava" matches "llava:latest"
        for inst_lower, inst_orig in installed_lower.items():
            if inst_lower.startswith(pref.lower()):
                return inst_orig

    # Fallback: any installed model with "llava" or "vision" in name
    for inst_lower, inst_orig in installed_lower.items():
        if "llava" in inst_lower or "vision" in inst_lower or "bakllava" in inst_lower:
            return inst_orig

    return None


def _get_text_models() -> list[str]:
    """Return candidate text models in preference order."""
    preferred   = os.environ.get("OLLAMA_MODEL")
    installed   = _get_installed_models()
    ordered     = []
    if preferred and preferred not in ordered:
        ordered.append(preferred)
    if DEFAULT_TEXT_MODEL not in ordered:
        ordered.append(DEFAULT_TEXT_MODEL)
    for m in installed:
        if m not in ordered:
            ordered.append(m)
    return ordered


def _is_memory_error(msg: str) -> bool:
    flags = ["requires more system memory", "not enough memory",
             "insufficient memory", "out of memory", "cuda out of memory"]
    return any(f in (msg or "").lower() for f in flags)


def _parse_ollama_error(resp) -> tuple[str, str]:
    """Return (http_code_str, detail_str) from a non-200 Ollama response."""
    try:
        body = resp.json()
        detail = body.get("error", "") if isinstance(body, dict) else ""
    except Exception:
        detail = resp.text or ""
    return str(resp.status_code), detail.strip()


# ---------------------------------------------------------------------------
# Core generation calls
# ---------------------------------------------------------------------------

MEDICAL_IMAGE_PROMPT = (
    "You are a medical AI assistant. This is a medical image (X-ray, MRI, CT scan, "
    "lab report photo, or similar). Please:\n"
    "1. Describe what you see in plain English.\n"
    "2. Highlight any abnormalities or areas of concern.\n"
    "3. Explain what this might mean for the patient in simple terms.\n"
    "4. Recommend next steps (e.g., consult a specialist).\n"
    "Keep your response clear and under 4 short paragraphs. "
    "Do NOT provide a definitive diagnosis."
)

MEDICAL_TEXT_PROMPT_TEMPLATE = (
    "Please read the following medical/diagnostic report and explain it to a patient.\n"
    "Summarize findings in simple English and avoid jargon.\n"
    "Highlight major concerns clearly.\n"
    "Limit your response to 3 short paragraphs.\n\n"
    "Report text:\n\n{text}"
)


def _call_vision_model(model: str, file_content: bytes) -> str:
    """Send an image to an Ollama vision model using the /api/generate endpoint."""
    b64 = file_to_base64(file_content)
    payload = {
        "model":  model,
        "prompt": MEDICAL_IMAGE_PROMPT,
        "images": [b64],
        "stream": False,
    }
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json=payload,
        timeout=OLLAMA_REQUEST_TIMEOUT_SEC,
    )
    if resp.status_code == 200:
        result = resp.json().get("response", "")
        if result:
            return result
        raise ValueError("Vision model returned an empty response.")
    code, detail = _parse_ollama_error(resp)
    raise RuntimeError(f"{code}::{detail}")


def _call_text_model(model: str, prompt: str) -> str:
    """Send a text prompt to a standard Ollama text model."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        # Important for thinking models like qwen3.5: force final answer in `response`.
        "think": False,
        # Conservative settings reduce memory pressure and improve reliability.
        "options": {
            "num_ctx": OLLAMA_NUM_CTX,
            "num_predict": OLLAMA_NUM_PREDICT,
            "num_batch": 1,
            "temperature": 0.2,
        },
    }
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json=payload,
        timeout=OLLAMA_REQUEST_TIMEOUT_SEC,
    )
    if resp.status_code == 200:
        body = resp.json()
        result = (body.get("response") or "").strip()
        if result:
            return result
        if body.get("thinking"):
            raise ValueError(
                "Model returned only internal thinking without a final answer. "
                "Retrying with next model."
            )
        raise ValueError("Model returned an empty response.")
    code, detail = _parse_ollama_error(resp)
    raise RuntimeError(f"{code}::{detail}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_medical_report(file_content: bytes, filename: str) -> str:
    """
    Analyse a medical file with Ollama.
    - Images → vision model (llava etc.)
    - PDF / text → text model with model-fallback
    Returns a plain-English summary string.
    """
    ext = os.path.splitext(filename.lower())[1]

    # ------------------------------------------------------------------
    # IMAGE path
    # ------------------------------------------------------------------
    if ext in IMAGE_EXTENSIONS:
        vision_model = _get_vision_model()
        if not vision_model:
            # Fall back: extract any embedded text if PIL is available,
            # otherwise raise a helpful error.
            try:
                from PIL import Image
                import pytesseract
                img = Image.open(io.BytesIO(file_content))
                text = pytesseract.image_to_string(img).strip()
                if text:
                    logger.info("No vision model found; falling back to OCR text extraction.")
                    return _analyze_text(text)
            except Exception:
                pass
            raise ValueError(
                "No vision-capable Ollama model is installed. "
                "Please run: ollama pull llava  then restart the server."
            )

        try:
            logger.info(f"Analyzing image '{filename}' with vision model '{vision_model}'.")
            return _call_vision_model(vision_model, file_content)
        except RuntimeError as e:
            raw = str(e)
            parts = raw.split("::", 1)
            detail = parts[1] if len(parts) == 2 else raw
            if _is_memory_error(detail):
                raise ValueError(
                    f"Vision model '{vision_model}' failed due to low memory. "
                    "Close other apps and retry, or use a smaller vision model."
                )
            raise ValueError(f"Vision model analysis failed: {detail}")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(
                f"Failed to communicate with Ollama at {OLLAMA_BASE_URL}. "
                "Please ensure Ollama is running locally."
            )

    # ------------------------------------------------------------------
    # PDF / TEXT path
    # ------------------------------------------------------------------
    if ext in PDF_EXTENSIONS:
        raw_text = extract_text_from_pdf(file_content)
    else:
        raw_text = extract_text_from_text_file(file_content)

    if not raw_text:
        raise ValueError("The file appears to be empty or unreadable. Please check it and retry.")

    return _analyze_text(raw_text)


def _analyze_text(text: str) -> str:
    """Run a text medical report through available Ollama text models with fallback."""
    prompt = MEDICAL_TEXT_PROMPT_TEMPLATE.format(text=text[:8000])  # cap at ~8k chars

    candidates = _get_text_models()
    if not candidates:
        raise ValueError(
            "No Ollama models found. Pull a small model first, e.g.: ollama pull phi3:mini"
        )

    memory_errors = []
    other_errors  = []
    connectivity_errors = []

    for model in candidates:
        try:
            logger.info(f"Attempting text analysis with model '{model}'.")
            return _call_text_model(model, prompt)
        except ValueError as e:
            msg = f"Model '{model}' returned no usable answer: {e}"
            other_errors.append(msg)
            logger.warning(msg)
            continue
        except RuntimeError as e:
            raw    = str(e)
            parts  = raw.split("::", 1)
            code   = parts[0] if len(parts) == 2 else "500"
            detail = parts[1] if len(parts) == 2 else raw

            if _is_memory_error(detail):
                memory_errors.append((model, detail))
                logger.warning(f"Model '{model}' ran out of memory, trying next.")
                continue
            if code == "404":
                other_errors.append(f"Model '{model}' not found locally")
                continue
            other_errors.append(f"Model '{model}' failed: {detail}")
            logger.warning(f"Model '{model}' failed: {detail}")
            continue
        except requests.exceptions.Timeout:
            msg = (
                f"Model '{model}' timed out after {OLLAMA_REQUEST_TIMEOUT_SEC}s "
                "while generating."
            )
            connectivity_errors.append(msg)
            logger.warning(msg)
            continue
        except requests.exceptions.RequestException as e:
            msg = f"Model '{model}' request error: {e}"
            connectivity_errors.append(msg)
            logger.warning(msg)
            continue

    if memory_errors:
        attempted = ", ".join(m for m, _ in memory_errors)
        raise ValueError(
            f"All models ({attempted}) failed due to low system memory. "
            "Close other applications or switch to a smaller model such as `phi3:mini`."
        )
    if connectivity_errors and not other_errors:
        raise ConnectionError(
            f"Could not get a response from Ollama at {OLLAMA_BASE_URL}. "
            "Tried multiple models but requests timed out/failed."
        )
    if other_errors:
        details = "; ".join(other_errors[:3])
        if connectivity_errors:
            details = f"{details}; {'; '.join(connectivity_errors[:2])}"
        raise ValueError(details)
    if connectivity_errors:
        raise ConnectionError(
            f"Could not get a response from Ollama at {OLLAMA_BASE_URL}. "
            "Requests timed out or failed."
        )
    raise ValueError("Analysis failed for an unknown reason.")
