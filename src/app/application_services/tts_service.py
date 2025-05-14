import os
import tempfile 
import logging
from app.domain.services.speech_synthesis_service import SpeechSynthesisService
from app.domain.tts_model import TTSModel
from app.domain.services.text_processor import TextProcessor
from app.domain.services.audio_postprocessor import AudioPostprocessorService
from app.config import (
    DEFAULT_SPEAKER_WAV_PATH, OUTPUT_DIR,
    DEFAULT_TTS_PARAMS, SUPPORTED_LANGUAGES,
    DEFAULT_AUDIO_POSTPROCESSING_PARAMS, XTTS_SAMPLE_RATE
)
from app.domain.value_objects import AudioOutput

logger = logging.getLogger(__name__)

class ApplicationTTSService:
    def __init__(self):
        logger.info("Khởi tạo ApplicationTTSService...")
        self.tts_model_instance = TTSModel()
        self.text_processor_instance = TextProcessor()
        self.audio_postprocessor_instance = AudioPostprocessorService(sample_rate=XTTS_SAMPLE_RATE)

        self.synthesis_service_instance = SpeechSynthesisService(
            self.tts_model_instance,
            self.text_processor_instance,
            self.audio_postprocessor_instance
        )
        logger.info("ApplicationTTSService và các thành phần phụ thuộc đã được khởi tạo.")
        self.check_model_health(log_on_success=True)

    def get_supported_languages(self) -> dict:
        """Trả về danh sách các ngôn ngữ được hỗ trợ."""
        return SUPPORTED_LANGUAGES

    def check_model_health(self, log_on_success=False) -> tuple[bool, str]:
        """
        Kiểm tra xem model TTS đã được tải và sẵn sàng hay chưa.
        Cố gắng cung cấp thông tin chi tiết hơn nếu model chưa sẵn sàng.
        """
        if self.tts_model_instance and self.tts_model_instance.is_loaded():
            if log_on_success:
                logger.info("Model health check: OK, model TTS đã được tải và sẵn sàng.")
            return True, "Model TTS đã được tải và sẵn sàng."
        else:
            logger.warning("Model health check: Model TTS CHƯA được tải hoặc có vấn đề.")
            detailed_error_msg = "Model giọng nói chưa được tải."
            if self.tts_model_instance:
                files_ok, missing_files_list = self.tts_model_instance._check_files_exist()
                if not files_ok:
                    detailed_error_msg += f" Các file model cần thiết bị thiếu: {', '.join(missing_files_list)}."
                else:
                    detailed_error_msg += " Tất cả các file model dường như tồn tại, nhưng model vẫn chưa được nạp thành công (có thể do lỗi nội bộ khi nạp model)."
            else:
                detailed_error_msg += " Instance của TTSModel không tồn tại."

            logger.error(f"Model health check: FAILED. {detailed_error_msg}")
            return False, detailed_error_msg


    def _parse_bool_param(self, form_params: dict, key: str, default_value: bool) -> bool:
        """Helper để parse tham số boolean từ form data (chuỗi)."""
        if key in form_params:
            value_str = str(form_params[key]).lower()
            return value_str in ['true', '1', 'yes', 'on']
        return default_value

    def _parse_float_param(self, form_params: dict, key: str, default_value: float) -> float:
        """Helper để parse tham số float từ form data (chuỗi)."""
        if key in form_params:
            try:
                return float(form_params[key])
            except (ValueError, TypeError):
                logger.warning(f"Giá trị không hợp lệ cho tham số float '{key}': '{form_params[key]}'. Sử dụng giá trị mặc định: {default_value}")
                return default_value
        return default_value

    def _parse_int_param(self, form_params: dict, key: str, default_value: int) -> int:
        """Helper để parse tham số integer từ form data (chuỗi)."""
        if key in form_params:
            try:
                return int(form_params[key])
            except (ValueError, TypeError):
                logger.warning(f"Giá trị không hợp lệ cho tham số int '{key}': '{form_params[key]}'. Sử dụng giá trị mặc định: {default_value}")
                return default_value
        return default_value

    def process_tts_request(self,
                            text: str,
                            language: str,
                            speaker_file_storage, 
                            form_params: dict
                            ) -> tuple[AudioOutput | None, str | None, str | None]:
        """
        Xử lý yêu cầu TTS đồng bộ (thường không được gọi trực tiếp từ API nếu dùng Celery).
        Hàm này chủ yếu để tham khảo hoặc nếu có kịch bản dùng đồng bộ.
        Trả về: (audio_output, error_message, temp_speaker_file_path_to_delete)
        """
        logger.info(f"Bắt đầu xử lý TTS request (đồng bộ) cho ngôn ngữ '{language}'...")

        model_ready, model_error_msg = self.check_model_health()
        if not model_ready:
            return None, f"Model không sẵn sàng: {model_error_msg}", None

        if language.lower() not in SUPPORTED_LANGUAGES:
            supported_lang_keys = ', '.join(SUPPORTED_LANGUAGES.keys())
            return None, f"Ngôn ngữ '{language}' không được hỗ trợ. Các ngôn ngữ hỗ trợ: {supported_lang_keys}", None

        should_normalize_text = self._parse_bool_param(form_params, 'normalize_text', True)

        current_tts_model_params = DEFAULT_TTS_PARAMS.copy()
        for key, default_val in DEFAULT_TTS_PARAMS.items():
            if isinstance(default_val, float):
                current_tts_model_params[key] = self._parse_float_param(form_params, key, default_val)
            elif isinstance(default_val, int):
                current_tts_model_params[key] = self._parse_int_param(form_params, key, default_val)
            elif isinstance(default_val, bool): 
                 current_tts_model_params[key] = self._parse_bool_param(form_params, key, default_val)

        current_audio_postproc_params = DEFAULT_AUDIO_POSTPROCESSING_PARAMS.copy()
        for key, default_val in DEFAULT_AUDIO_POSTPROCESSING_PARAMS.items():
            if isinstance(default_val, float):
                current_audio_postproc_params[key] = self._parse_float_param(form_params, key, default_val)
            elif isinstance(default_val, int):
                current_audio_postproc_params[key] = self._parse_int_param(form_params, key, default_val)
            elif isinstance(default_val, bool):
                current_audio_postproc_params[key] = self._parse_bool_param(form_params, key, default_val)
            elif isinstance(default_val, str): 
                 current_audio_postproc_params[key] = form_params.get(key, default_val)


        current_speaker_audio_path = DEFAULT_SPEAKER_WAV_PATH
        temp_speaker_file_to_delete = None

        if speaker_file_storage and speaker_file_storage.filename:
            try:
                if not os.path.exists(OUTPUT_DIR):
                    os.makedirs(OUTPUT_DIR, exist_ok=True)

                file_suffix = os.path.splitext(speaker_file_storage.filename)[1] or ".wav"
                with tempfile.NamedTemporaryFile(suffix=file_suffix, dir=OUTPUT_DIR, prefix="sync_api_speaker_", delete=False) as tmp_file:
                    speaker_file_storage.save(tmp_file)
                    current_speaker_audio_path = tmp_file.name
                temp_speaker_file_to_delete = current_speaker_audio_path
                logger.info(f"Đã lưu file âm thanh tải lên (đồng bộ) vào file tạm: {current_speaker_audio_path}")
            except Exception as e_save_temp:
                logger.error(f"Lỗi khi lưu file âm thanh tạm (đồng bộ): {e_save_temp}", exc_info=True)
                return None, f"Lỗi khi xử lý file âm thanh tải lên: {e_save_temp}", None

        audio_output, error_msg = self.synthesis_service_instance.synthesize(
            full_text_input=text,
            language_code=language.lower(),
            speaker_audio_path=current_speaker_audio_path,
            apply_text_normalization=should_normalize_text,
            synthesis_model_params=current_tts_model_params,
            audio_postproc_params=current_audio_postproc_params
        )

        if error_msg:
            logger.error(f"Lỗi khi tổng hợp (đồng bộ): {error_msg}")
        if audio_output:
            logger.info(f"Tổng hợp (đồng bộ) thành công, filename: {audio_output.filename}")

        return audio_output, error_msg, temp_speaker_file_to_delete