import torch
import torchaudio
import io
import logging
import os
from app.domain.tts_model import TTSModel
from app.domain.services.text_processor import TextProcessor
from app.domain.services.audio_postprocessor import AudioPostprocessorService
from app.domain.value_objects import AudioOutput
from app.config import MIN_CHAR_PER_SENTENCE_INPUT, XTTS_SAMPLE_RATE 

logger = logging.getLogger(__name__)

class SpeechSynthesisService:
    def __init__(self, 
                 tts_model: TTSModel, 
                 text_processor: TextProcessor, 
                 audio_postprocessor: AudioPostprocessorService):
        self.tts_model = tts_model
        self.text_processor = text_processor
        self.audio_postprocessor = audio_postprocessor

    def synthesize(self,
                   full_text_input: str,
                   language_code: str,
                   speaker_audio_path: str,
                   apply_text_normalization: bool,
                   synthesis_model_params: dict, 
                   audio_postproc_params: dict  
                   ) -> tuple[AudioOutput | None, str | None]:

        if not self.tts_model.is_loaded():
            logger.error("SpeechSynthesisService: Model chưa được tải!")
            return None, "Lỗi hệ thống: Model giọng nói chưa sẵn sàng."
        
        if not os.path.exists(speaker_audio_path):
            logger.error(f"SpeechSynthesisService: File âm thanh mẫu không tồn tại: {speaker_audio_path}")
            return None, f"Lỗi: File âm thanh mẫu '{os.path.basename(speaker_audio_path)}' không tồn tại."

        logger.info(f"SpeechSynthesisService: Bắt đầu TTS. Lang='{language_code}', Speaker='{os.path.basename(speaker_audio_path)}'")
        logger.debug(f"Model Params: {synthesis_model_params}")
        logger.debug(f"Postproc Params: {audio_postproc_params}")
        
        processed_text = full_text_input
        if apply_text_normalization and language_code == "vi":
            logger.info("Áp dụng chuẩn hóa văn bản tiếng Việt...")
            processed_text = self.text_processor.normalize_vietnamese_text(full_text_input)
            logger.debug(f"Văn bản sau chuẩn hóa (100 chars): '{processed_text[:100]}...'")
        else:
            logger.debug(f"Văn bản gốc (100 chars): '{processed_text[:100]}...'")

        try:
            gpt_cond_latent, speaker_embedding = self.tts_model.get_conditioning_latents(speaker_audio_path)
            
            sentences = self.text_processor.tokenize_sentences(processed_text, language_code)
            logger.info(f"Văn bản được tách thành {len(sentences)} câu.")

            if not sentences:
                logger.warning("Không có câu nào được tách từ văn bản đầu vào.")
                return None, "Văn bản đầu vào không chứa nội dung có thể xử lý."

            wav_generated_chunks = []
            for i, single_sentence_text in enumerate(sentences):
                current_sentence_for_tts = single_sentence_text.strip()
                
                if not current_sentence_for_tts:
                    logger.debug(f"Câu {i+1} rỗng, bỏ qua.")
                    continue
                
                if len(current_sentence_for_tts) < MIN_CHAR_PER_SENTENCE_INPUT:
                    logger.warning(f"Câu {i+1} ('{current_sentence_for_tts[:50]}...') quá ngắn ({len(current_sentence_for_tts)} ký tự so với min {MIN_CHAR_PER_SENTENCE_INPUT}). Bỏ qua.")
                    continue
                
                logger.info(f"Đang tổng hợp giọng nói cho câu {i+1}/{len(sentences)}: '{current_sentence_for_tts[:50]}...'")
                
                try:
                    wav_output_dict = self.tts_model.inference(
                        text=current_sentence_for_tts,
                        language=language_code,
                        gpt_cond_latent=gpt_cond_latent,
                        speaker_embedding=speaker_embedding,
                        model_params=synthesis_model_params 
                    )
                    
                    audio_data_from_model = wav_output_dict["wav"] 
                    
                    if isinstance(audio_data_from_model, torch.Tensor):
                        audio_tensor_for_sentence = audio_data_from_model
                    else: 
                        audio_tensor_for_sentence = torch.tensor(audio_data_from_model, dtype=torch.float32)
                    
                    keep_length = self.text_processor.calculate_keep_length(current_sentence_for_tts, language_code)
                    if keep_length > 0 and audio_tensor_for_sentence.numel() > keep_length :
                        logger.debug(f"Áp dụng cắt ngắn cho audio của câu '{current_sentence_for_tts[:30]}...': giữ lại {keep_length} samples.")
                        audio_tensor_for_sentence = audio_tensor_for_sentence[:keep_length]

                    if audio_tensor_for_sentence.numel() > 0 :
                        wav_generated_chunks.append(audio_tensor_for_sentence)
                    else:
                        logger.warning(f"Câu {i+1} không tạo ra dữ liệu âm thanh hoặc audio rỗng sau khi cắt ngắn.")

                except Exception as e_inference_loop:
                    logger.error(f"Lỗi khi inference câu '{current_sentence_for_tts[:50]}...': {e_inference_loop}", exc_info=False)
                finally:
                    self.tts_model.clear_gpu_cache()


            if not wav_generated_chunks:
                logger.warning("Không có chunk âm thanh nào được tạo thành công từ các câu.")
                return None, "Không tạo được âm thanh từ văn bản (có thể tất cả các câu đều bị lỗi, quá ngắn, hoặc văn bản không hợp lệ)."

            final_output_wave = torch.cat([chunk.view(-1) for chunk in wav_generated_chunks if chunk.numel() > 0], dim=0)
            logger.info(f"Ghép {len(wav_generated_chunks)} chunk âm thanh thành công. Tổng độ dài: {final_output_wave.shape[0]} samples.")
            
            if final_output_wave.numel() == 0:
                logger.error("Âm thanh cuối cùng rỗng sau khi ghép các chunks.")
                return None, "Không tạo được nội dung âm thanh cuối cùng."

            logger.info("Bắt đầu xử lý hậu kỳ âm thanh...")
            processed_wave = self.audio_postprocessor.process_audio(final_output_wave, audio_postproc_params)
            
            if processed_wave is None or processed_wave.numel() == 0:
                logger.error("Âm thanh bị rỗng sau quá trình xử lý hậu kỳ.")
                return None, "Lỗi trong quá trình xử lý hậu kỳ âm thanh, không có dữ liệu đầu ra."

            audio_bytes_io = io.BytesIO()
            wave_to_save = processed_wave.unsqueeze(0) if processed_wave.ndim == 1 else processed_wave
            
            torchaudio.save(audio_bytes_io, wave_to_save.cpu(), self.audio_postprocessor.sample_rate, format="wav")
            audio_bytes_io.seek(0)
            logger.info(f"Đã tạo dữ liệu WAV (sau hậu kỳ) trong bộ nhớ, kích thước: {audio_bytes_io.getbuffer().nbytes} bytes.")
            
            output_filename = self.text_processor.generate_safe_filename(full_text_input)
            return AudioOutput(audio_data=audio_bytes_io, filename=output_filename), None

        except FileNotFoundError as e_fnf: 
            logger.error(f"Lỗi FileNotFoundError trong SpeechSynthesisService: {e_fnf}")
            return None, str(e_fnf)
        except RuntimeError as e_rt:
            logger.error(f"Lỗi RuntimeError trong SpeechSynthesisService: {e_rt}")
            return None, str(e_rt)
        except Exception as e_main_tts:
            logger.error(f"Lỗi chung không xác định trong SpeechSynthesisService: {e_main_tts}", exc_info=True)
            self.tts_model.clear_gpu_cache()
            return None, f"Lỗi hệ thống không mong muốn trong quá trình tổng hợp giọng nói."