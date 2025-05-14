from dataclasses import dataclass
import io

# Không cần dùng SynthesisParameters nữa vì truyền dict trực tiếp tiện hơn cho nhiều tham số
# @dataclass(frozen=True)
# class SynthesisParameters:
#     temperature: float
#     length_penalty: float
#     repetition_penalty: float
#     top_k: int
#     top_p: float
#     speed: float

@dataclass(frozen=True)
class AudioPostprocessingParameters:
    trim_silence: bool
    trim_top_db: int
    reduce_noise: bool
    apply_compressor: bool
    comp_threshold_db: float
    comp_ratio: float
    comp_attack_ms: float
    comp_release_ms: float
    apply_eq: bool
    eq_peak_voice_hz: float
    eq_peak_voice_q: float
    eq_peak_voice_gain_db: float
    normalize_volume: bool
    norm_target_limiter_db: float

@dataclass(frozen=True)
class AudioOutput:
    audio_data: io.BytesIO
    filename: str
    mimetype: str = "audio/wav"