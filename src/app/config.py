import os
from dotenv import load_dotenv 
import logging

load_dotenv() 

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

MODEL_DIR_NAME = "../model" 
OUTPUT_DIR_NAME = "../../output"

MODEL_DIR = os.environ.get("MODEL_DIR", os.path.join(BASE_DIR, MODEL_DIR_NAME))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(BASE_DIR, OUTPUT_DIR_NAME))

DEFAULT_SPEAKER_WAV_NAME = "vi_sample.wav"
DEFAULT_SPEAKER_WAV_PATH = os.path.join(MODEL_DIR, DEFAULT_SPEAKER_WAV_NAME)

MODEL_FILENAME = "model.pth"
CONFIG_FILENAME = "config.json"
VOCAB_FILENAME = "vocab.json"
SPEAKERS_XTTS_FILENAME = "speakers_xtts.pth" 

MODEL_PATH = os.path.join(MODEL_DIR, MODEL_FILENAME)
CONFIG_PATH = os.path.join(MODEL_DIR, CONFIG_FILENAME)
VOCAB_PATH = os.path.join(MODEL_DIR, VOCAB_FILENAME)
SPEAKERS_XTTS_PATH = os.path.join(MODEL_DIR, SPEAKERS_XTTS_FILENAME)


DEFAULT_TTS_PARAMS = {
    "temperature": 0.3,
    "length_penalty": 1.0,
    "repetition_penalty": 10.0,
    "top_k": 30,
    "top_p": 0.85,
    "speed": 1.0,
    "enable_text_splitting": True
}

MIN_CHAR_PER_SENTENCE_INPUT = 3
MAX_FILENAME_PREFIX_CHAR = 50

DEFAULT_AUDIO_POSTPROCESSING_PARAMS = {
    "trim_silence": False,
    "trim_top_db": 20,
    "reduce_noise": False,
    "denoise_method": "noisereduce",
    "apply_compressor": False,
    "comp_threshold_db": -16.0,
    "comp_ratio": 4.0,
    "comp_attack_ms": 5.0,
    "comp_release_ms": 100.0,
    "apply_eq": False,
    "eq_peak_voice_hz": 1500.0,
    "eq_peak_voice_q": 1.0,
    "eq_peak_voice_gain_db": 1.5,
    "normalize_volume": False,
    "norm_target_limiter_db": -1.0
}

SUPPORTED_LANGUAGES = {
    "vi": "Tiếng Việt", "en": "Tiếng Anh", "es": "Tiếng Tây Ban Nha", "fr": "Tiếng Pháp",
    "de": "Tiếng Đức", "it": "Tiếng Ý", "pt": "Tiếng Bồ Đào Nha", "pl": "Tiếng Ba Lan",
    "tr": "Tiếng Thổ Nhĩ Kỳ", "ru": "Tiếng Nga", "nl": "Tiếng Hà Lan", "cs": "Tiếng Séc",
    "ar": "Tiếng Ả Rập", "zh-cn": "Tiếng Trung (giản thể)", "ja": "Tiếng Nhật",
    "hu": "Tiếng Hungary", "ko": "Tiếng Hàn", "hi": "Tiếng Hindi"
}

XTTS_SAMPLE_RATE = 24000

DEFAULT_DEV_API_KEY = "secret_development" 
API_KEYS_STR = os.environ.get("VALID_API_KEYS", DEFAULT_DEV_API_KEY)

VALID_API_KEYS = [key.strip() for key in API_KEYS_STR.split(',') if key.strip()]

API_KEY_HEADER = os.environ.get("API_KEY_HEADER_NAME", "X-API-Key")


config_logger = logging.getLogger(__name__) 

if not VALID_API_KEYS:
    config_logger("CẢNH BÁO NGHIÊM TRỌNG: VALID_API_KEYS rỗng sau khi xử lý! Sẽ không có API Key nào hợp lệ. "
          "Vui lòng kiểm tra biến môi trường VALID_API_KEYS hoặc DEFAULT_DEV_API_KEY trong config.py.")
elif API_KEYS_STR == DEFAULT_DEV_API_KEY and DEFAULT_DEV_API_KEY == "secret_development":
    config_logger("CẢNH BÁO: Đang sử dụng API Key mặc định ('secret_development') cho development. "
          "Hãy đặt biến môi trường VALID_API_KEYS với các key thực tế cho production!")