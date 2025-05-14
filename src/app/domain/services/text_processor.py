import os
import string
import re
import unicodedata
from unidecode import unidecode 
from underthesea import sent_tokenize 
from datetime import datetime
import logging
from app.config import MAX_FILENAME_PREFIX_CHAR 

DIR = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger(__name__)

class TextProcessor:
    def normalize_vietnamese_text(self, text: str) -> str:
        try:
            processed_text = (
                self.TTSnorm(text , punc=True, unknown=False, lower=False, rule=True)
                .replace("..", ".").replace("!.", "!").replace("?.", "?")
                .replace(" .", ".").replace(" ,", ",")
                .replace('"', "").replace("'", "")
                .replace("AI", "Ây Ai").replace("A.I", "Ây Ai")
            )
            return processed_text
        except Exception as e:
            logger.warning(f"Lỗi khi chuẩn hóa văn bản tiếng Việt: {e}. Sử dụng văn bản gốc.", exc_info=True)
            return text

    def TTSnorm(self, text: str, punc=False, unknown=True, lower=True, rule=False) -> str:
        try:
            if lower:
                text = text.lower()
            if unknown:
                text = ''.join(c for c in text if unicodedata.category(c)[0] != 'C')
            if punc:
                text = re.sub(r'[^\w\s]', '', text)
            if rule:
                replacements = {
                    'ko': 'không',
                    'k': 'không',
                    'j': 'gì',
                    'dc': 'được',
                    'vs': 'với',
                    'đc': 'được',
                    'mk': 'mình',
                }
                for key, val in replacements.items():
                    text = re.sub(rf'\b{re.escape(key)}\b', val, text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        except Exception as e:
            logger.warning(f"Lỗi khi TTSnorm nội bộ: {e}", exc_info=True)
            return text

    def tokenize_sentences(self, text: str, lang_code: str) -> list[str]:
        if lang_code in ["ja", "zh-cn"]:
            logger.debug(f"Sử dụng split('。') cho ngôn ngữ {lang_code}")
            return text.split("。") 
        elif lang_code == "vi":
            return sent_tokenize(text)
        else: 
            logger.debug(f"Sử dụng split cơ bản cho ngôn ngữ {lang_code}")
            text_with_delimiters = text.replace("!", "!<SPLIT>").replace("?", "?<SPLIT>").replace(".", ".<SPLIT>")
            sentences = [s.strip() for s in text_with_delimiters.split("<SPLIT>") if s.strip()]
            return sentences

    def calculate_keep_length(self, text_segment: str, lang_code: str) -> int:
        if lang_code in ["ja", "zh-cn"]: return -1 
        word_count = len(text_segment.split())
        num_punct = sum(text_segment.count(p) for p in [".", "!", "?", ","])
        if word_count == 0: return -1 
        if word_count < 3: return 18000 * word_count + 1500 * num_punct 
        elif word_count < 5: return 15000 * word_count + 2000 * num_punct
        elif word_count < 10: return 13000 * word_count + 2000 * num_punct
        return -1

    def generate_safe_filename(self, text_input: str) -> str:
        safe_text_part = text_input.replace("\n", " ").replace("\r", " ").strip()[:MAX_FILENAME_PREFIX_CHAR]
        filename_prefix = safe_text_part.lower().replace(" ", "_")
        allowed_chars_for_filename = string.ascii_lowercase + string.digits + "_"
        filename_prefix = "".join(c for c in filename_prefix if c in allowed_chars_for_filename)
        filename_prefix = unidecode(filename_prefix)
        filename_prefix = filename_prefix[:MAX_FILENAME_PREFIX_CHAR].strip('_')
        if not filename_prefix: 
            filename_prefix = "synthesized_audio"
        current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return f"{current_datetime}_{filename_prefix}.wav"
