import os
import tempfile
import logging
import torch
from app.celery_app import celery_app 
from app.config import (
    OUTPUT_DIR, DEFAULT_SPEAKER_WAV_PATH, XTTS_SAMPLE_RATE,
)

from app.domain.services.speech_synthesis_service import SpeechSynthesisService

logger = logging.getLogger(__name__)

class WorkerServices:
    _instance = None
    _initialized_flag = False 

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WorkerServices, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if WorkerServices._initialized_flag:
            return

        logger.info("Celery Task Worker: Initializing services for this worker process...")
        from app.domain.tts_model import TTSModel
        from app.domain.services.text_processor import TextProcessor
        from app.domain.services.audio_postprocessor import AudioPostprocessorService

        self.tts_model: TTSModel = TTSModel() 
        if not self.tts_model.is_loaded():
            logger.critical("Celery Task Worker: MODEL KHÔNG THỂ TẢI! Worker này có thể không xử lý được task.")

        self.text_processor: TextProcessor = TextProcessor()
        self.audio_postprocessor: AudioPostprocessorService = AudioPostprocessorService(sample_rate=XTTS_SAMPLE_RATE)
        
        self.synthesis_service: SpeechSynthesisService = SpeechSynthesisService(
            self.tts_model, self.text_processor, self.audio_postprocessor
        )
        
        WorkerServices._initialized_flag = True
        logger.info("Celery Task Worker: Services initialized successfully for this worker process.")

    def get_synthesis_service(self) -> SpeechSynthesisService:
        if not hasattr(self, 'synthesis_service') or not self.tts_model.is_loaded():
            logger.error("Celery Task Worker: Cố gắng lấy synthesis_service nhưng nó chưa được khởi tạo đúng hoặc model lỗi.")
            if not WorkerServices._initialized_flag :
                 self.__init__() 
                 if not hasattr(self, 'synthesis_service') or not self.tts_model.is_loaded():
                      raise RuntimeError("Không thể khởi tạo SpeechSynthesisService hoặc model trong worker.")
            elif not self.tts_model.is_loaded():
                 raise RuntimeError("Model giọng nói không khả dụng trong worker (lỗi khi tải lại hoặc kiểm tra).")

        return self.synthesis_service

worker_services_instance = WorkerServices()


@celery_app.task(bind=True, name='app.tasks.generate_tts_task', acks_late=True, reject_on_worker_lost=True)
def generate_tts_task(self, 
                      text_input: str,
                      language_code: str,
                      speaker_audio_temp_path_or_flag: str,
                      apply_text_normalization: bool,
                      synthesis_model_params: dict,
                      audio_postproc_params: dict) -> dict: 
    task_id = self.request.id or "unknown_task_id"
    logger.info(f"CeleryTask [{task_id}]: Bắt đầu xử lý. Lang='{language_code}', Text='{text_input[:50]}...'")

    temp_speaker_file_to_delete_by_worker = None

    try:
        synthesis_service = worker_services_instance.get_synthesis_service()

        actual_speaker_audio_path = ""
        if speaker_audio_temp_path_or_flag == "USE_DEFAULT_SPEAKER":
            actual_speaker_audio_path = DEFAULT_SPEAKER_WAV_PATH
            logger.info(f"CeleryTask [{task_id}]: Sử dụng giọng mẫu mặc định: {actual_speaker_audio_path}")
        else:
            actual_speaker_audio_path = speaker_audio_temp_path_or_flag
            temp_speaker_file_to_delete_by_worker = actual_speaker_audio_path
            logger.info(f"CeleryTask [{task_id}]: Sử dụng giọng mẫu tải lên (đã lưu tạm): {actual_speaker_audio_path}")

        if not os.path.exists(actual_speaker_audio_path):
            logger.error(f"CeleryTask [{task_id}]: File giọng mẫu '{actual_speaker_audio_path}' không tồn tại.")
            raise FileNotFoundError(f"File giọng mẫu không tồn tại trong worker: {actual_speaker_audio_path}")

        audio_output_obj, error_msg = synthesis_service.synthesize(
            full_text_input=text_input,
            language_code=language_code,
            speaker_audio_path=actual_speaker_audio_path,
            apply_text_normalization=apply_text_normalization,
            synthesis_model_params=synthesis_model_params,
            audio_postproc_params=audio_postproc_params
        )

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.debug(f"CeleryTask [{task_id}]: GPU cache cleared.")

        if error_msg:
            logger.error(f"CeleryTask [{task_id}]: Lỗi từ SpeechSynthesisService: {error_msg}")
            raise Exception(error_msg) 

        if audio_output_obj and audio_output_obj.audio_data:
            if not os.path.exists(OUTPUT_DIR):
                os.makedirs(OUTPUT_DIR, exist_ok=True)
            
            saved_audio_path = os.path.join(OUTPUT_DIR, audio_output_obj.filename)
            
            with open(saved_audio_path, "wb") as f_out:
                f_out.write(audio_output_obj.audio_data.getbuffer())
            
            logger.info(f"CeleryTask [{task_id}]: Thành công! Âm thanh đã được lưu tại: {saved_audio_path}")
            return {"status": "SUCCESS", "file_path": saved_audio_path, "filename": audio_output_obj.filename}
        else:
            logger.error(f"CeleryTask [{task_id}]: SpeechSynthesisService không trả về dữ liệu âm thanh.")
            raise Exception("Không tạo được dữ liệu âm thanh.")

    except Exception as e: 
        logger.critical(f"CeleryTask [{task_id}]: Lỗi nghiêm trọng không xử lý được: {e}", exc_info=True)
        raise 
    finally:
        if temp_speaker_file_to_delete_by_worker and os.path.exists(temp_speaker_file_to_delete_by_worker):
            try:
                os.remove(temp_speaker_file_to_delete_by_worker)
                logger.info(f"CeleryTask [{task_id}]: Đã dọn dẹp file giọng mẫu tạm: {temp_speaker_file_to_delete_by_worker}")
            except OSError as e_remove:
                logger.error(f"CeleryTask [{task_id}]: Lỗi khi dọn dẹp file giọng mẫu tạm '{temp_speaker_file_to_delete_by_worker}': {e_remove}")