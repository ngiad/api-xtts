import torch
import torchaudio 
import numpy as np
import logging
import io

import librosa 
import noisereduce 
from pedalboard import ( 
    Pedalboard, Compressor, Gain, LowShelfFilter, HighShelfFilter, PeakFilter, Limiter
)
from app.config import XTTS_SAMPLE_RATE 

logger = logging.getLogger(__name__)

class AudioPostprocessorService:
    def __init__(self, sample_rate: int = XTTS_SAMPLE_RATE):
        self.sample_rate = sample_rate
        logger.info(f"AudioPostprocessorService initialized with sample rate: {self.sample_rate}")

    def _to_numpy(self, audio_tensor: torch.Tensor) -> np.ndarray:
        if not isinstance(audio_tensor, torch.Tensor):
            logger.error(f"Input to _to_numpy is not a Tensor, type: {type(audio_tensor)}")
            return np.array([], dtype=np.float32) 
        return audio_tensor.squeeze().cpu().to(torch.float32).numpy()

    def _to_tensor(self, audio_np: np.ndarray) -> torch.Tensor:
        if not isinstance(audio_np, np.ndarray):
            logger.error(f"Input to _to_tensor is not a Numpy array, type: {type(audio_np)}")
            return torch.empty(0, dtype=torch.float32)
        return torch.from_numpy(audio_np.astype(np.float32))

    def _trim_silence(self, audio_tensor: torch.Tensor, top_db: int) -> torch.Tensor:
        if audio_tensor.numel() == 0: 
            logger.warning("Trimming: Input audio tensor is empty, skipping.")
            return audio_tensor
        logger.info(f"Trimming silence with top_db={top_db}...")
        audio_np = self._to_numpy(audio_tensor)
        
        if audio_np.ndim == 0 or audio_np.size == 0 : 
            logger.warning("Trimming: Audio numpy array is scalar or empty after conversion, skipping trim.")
            return audio_tensor
        
        try:
            trimmed_audio_np, _ = librosa.effects.trim(audio_np, top_db=top_db)
            logger.info(f"Trimming: Original samples: {len(audio_np)}, Trimmed samples: {len(trimmed_audio_np)}")
            return self._to_tensor(trimmed_audio_np)
        except Exception as e:
            logger.error(f"Error during librosa trimming: {e}", exc_info=True)
            return audio_tensor


    def _reduce_noise_basic(self, audio_tensor: torch.Tensor) -> torch.Tensor:
        if audio_tensor.numel() == 0: 
            logger.warning("Noise Reduction: Input audio tensor is empty, skipping.")
            return audio_tensor
        logger.info("Reducing noise (basic using noisereduce)...")
        audio_np = self._to_numpy(audio_tensor)

        if audio_np.ndim == 0 or audio_np.size == 0:
            logger.warning("Noise Reduction: Audio numpy array is scalar or empty, skipping.")
            return audio_tensor

        try:
            reduced_noise_audio_np = noisereduce.reduce_noise(y=audio_np, sr=self.sample_rate, stationary=True)
            logger.info("Noise reduction applied.")
            return self._to_tensor(reduced_noise_audio_np)
        except Exception as e:
            logger.error(f"Error during noisereduce processing: {e}", exc_info=True)
            return audio_tensor

    def _apply_pedalboard_effects(self, audio_tensor: torch.Tensor, params: dict) -> torch.Tensor:
        if audio_tensor.numel() == 0:
            logger.warning("Pedalboard: Input audio tensor is empty, skipping.")
            return audio_tensor
        logger.info(f"Applying Pedalboard effects with params: {params}...")
        audio_np = self._to_numpy(audio_tensor)

        if audio_np.ndim == 0 or audio_np.size == 0:
            logger.warning("Pedalboard: Audio numpy array is scalar or empty, skipping.")
            return audio_tensor

        audio_np_for_pb = audio_np.reshape(1, -1) if audio_np.ndim == 1 else audio_np

        if audio_np_for_pb.shape[1] == 0:
            logger.warning("Pedalboard: No samples to process after reshape, skipping effects.")
            return audio_tensor

        board_effects = []
        if params.get("apply_compressor", False):
            board_effects.append(Compressor(
                threshold_db=float(params.get("comp_threshold_db", -16.0)),
                ratio=float(params.get("comp_ratio", 4.0)),
                attack_ms=float(params.get("comp_attack_ms", 5.0)),
                release_ms=float(params.get("comp_release_ms", 100.0))
            ))

        if params.get("apply_eq", False):
            peak_gain = float(params.get("eq_peak_voice_gain_db", 0.0))
            if peak_gain != 0.0:
                board_effects.append(PeakFilter(
                    cutoff_frequency_hz=float(params.get("eq_peak_voice_hz", 1500.0)),
                    q=float(params.get("eq_peak_voice_q", 1.0)),
                    gain_db=peak_gain
                ))

        if params.get("normalize_volume", False):
            board_effects.append(Limiter(
                threshold_db=float(params.get("norm_target_limiter_db", -1.0)),
                release_ms=50.0
            ))

        if not board_effects:
            logger.info("Pedalboard: No effects enabled.")
            return audio_tensor

        try:
            board = Pedalboard(board_effects)  # Sửa ở đây
            processed_audio_pb = board.process(audio_np_for_pb, sample_rate=self.sample_rate)  # Và sửa ở đây

            final_processed_np = processed_audio_pb.reshape(-1) if audio_np_for_pb.shape[0] == 1 else processed_audio_pb
            logger.info("Pedalboard effects applied.")
            return self._to_tensor(final_processed_np)
        except Exception as e:
            logger.error(f"Error during pedalboard effects processing: {e}", exc_info=True)
            return audio_tensor



    def process_audio(self, audio_tensor: torch.Tensor, processing_params: dict) -> torch.Tensor:
        if not isinstance(audio_tensor, torch.Tensor) or audio_tensor.numel() == 0:
            logger.warning("Audio Postprocess: Input audio_tensor không hợp lệ hoặc rỗng, không xử lý.")
            return audio_tensor if isinstance(audio_tensor, torch.Tensor) else torch.empty(0)

        current_audio = audio_tensor
        logger.info(f"Starting audio post-processing with params: {processing_params}")

        if processing_params.get("trim_silence", False):
            current_audio = self._trim_silence(current_audio, top_db=int(processing_params.get("trim_top_db", 20)))
            if current_audio.numel() == 0: logger.warning("Audio became empty after trimming."); return current_audio
        
        if processing_params.get("reduce_noise", False):
            current_audio = self._reduce_noise_basic(current_audio)
            if current_audio.numel() == 0: logger.warning("Audio became empty after noise reduction."); return current_audio
            
        is_pedalboard_needed = any(
            processing_params.get(key, False) for key in ["apply_compressor", "apply_eq", "normalize_volume"]
        )
        if is_pedalboard_needed:
            current_audio = self._apply_pedalboard_effects(current_audio, processing_params)
            if current_audio.numel() == 0: logger.warning("Audio became empty after pedalboard effects."); return current_audio
        
        logger.info("Hoàn tất xử lý hậu kỳ âm thanh.")
        return current_audio