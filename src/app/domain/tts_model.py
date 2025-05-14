import os
import torch
import logging
from TTS.tts.configs.xtts_config import XttsConfig 
from TTS.tts.models.xtts import Xtts 
from app.config import MODEL_PATH, CONFIG_PATH, VOCAB_PATH, DEFAULT_SPEAKER_WAV_PATH

logger = logging.getLogger(__name__)

class TTSModel:
    _instance = None
    _initialized_flag = False 

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TTSModel, cls).__new__(cls)
        return cls._instance

    def __init__(self, model_path=MODEL_PATH, config_path=CONFIG_PATH, vocab_path=VOCAB_PATH):
        if TTSModel._initialized_flag:
            return
        
        self.model: Xtts = None
        self.model_path = model_path
        self.config_path = config_path
        self.vocab_path = vocab_path
        
        if not os.path.exists(DEFAULT_SPEAKER_WAV_PATH):
             logger.warning(f"File âm thanh mẫu mặc định không tồn tại: {DEFAULT_SPEAKER_WAV_PATH}")

        self._load_model()
        TTSModel._initialized_flag = True


    def _check_files_exist(self) -> tuple[bool, list[str]]:
        missing_files = []
        if not os.path.exists(self.model_path): missing_files.append(os.path.basename(self.model_path))
        if not os.path.exists(self.config_path): missing_files.append(os.path.basename(self.config_path))
        if not os.path.exists(self.vocab_path): missing_files.append(os.path.basename(self.vocab_path))
        
        if missing_files:
            logger.error(f"Thiếu các file model cần thiết: {', '.join(missing_files)} tại {os.path.dirname(self.model_path)}")
            return False, missing_files
        return True, []

    def _load_model(self):
        files_ok, _ = self._check_files_exist()
        if not files_ok:
            self.model = None
            logger.error("Không thể tải model XTTS do thiếu file cấu hình hoặc checkpoint.")
            return

        try:
            current_config = XttsConfig()
            current_config.load_json(self.config_path)
            self.model = Xtts.init_from_config(current_config)
            logger.info(f"Đang tải checkpoint XTTS từ: {self.model_path}")
            self.model.load_checkpoint(
                current_config,
                checkpoint_path=self.model_path,
                vocab_path=self.vocab_path,
                use_deepspeed=False 
            )
            if torch.cuda.is_available():
                logger.info("Phát hiện GPU, model sẽ được chuyển sang CUDA.")
                self.model.cuda()
            else:
                logger.info("Không phát hiện GPU, model sẽ sử dụng CPU.")
            logger.info("Model XTTS đã được tải thành công!")
        except Exception as e:
            logger.error(f"Lỗi nghiêm trọng khi tải model XTTS: {e}", exc_info=True)
            self.model = None
            
    def is_loaded(self) -> bool:
        return self.model is not None

    def get_conditioning_latents(self, audio_path: str):
        if not self.is_loaded():
            logger.error("Cố gắng lấy conditioning latents nhưng model chưa được tải.")
            raise RuntimeError("Model chưa được tải.")
        if not os.path.exists(audio_path):
            logger.error(f"File âm thanh mẫu không tồn tại để lấy conditioning latents: {audio_path}")
            raise FileNotFoundError(f"File âm thanh mẫu không tồn tại: {audio_path}")

        try:
            return self.model.get_conditioning_latents(
                audio_path=audio_path,
                gpt_cond_len=self.model.config.gpt_cond_len,
                max_ref_length=self.model.config.max_ref_len,
                sound_norm_refs=self.model.config.sound_norm_refs
            )
        except Exception as e:
            logger.error(f"Lỗi khi lấy conditioning latents từ '{audio_path}': {e}", exc_info=True)
            raise

    def inference(self, text: str, language: str, gpt_cond_latent, speaker_embedding, model_params: dict):
        if not self.is_loaded():
            logger.error("Cố gắng thực hiện inference nhưng model chưa được tải.")
            raise RuntimeError("Model chưa được tải.")
        
        try:
            return self.model.inference(
                text=text,
                language=language,
                gpt_cond_latent=gpt_cond_latent,
                speaker_embedding=speaker_embedding,
                **model_params 
            )
        except Exception as e:
            logger.error(f"Lỗi trong quá trình inference của model XTTS: {e}", exc_info=True)
            raise

    def clear_gpu_cache(self):
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.debug("Đã xóa GPU cache.")