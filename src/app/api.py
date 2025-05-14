import os
import logging
from functools import wraps
from flask import (
    Flask, request, jsonify,
    send_from_directory, url_for
)
from werkzeug.utils import secure_filename
import tempfile
from datetime import datetime, timezone 

try:
    from app.config import (
        OUTPUT_DIR, SUPPORTED_LANGUAGES,
        DEFAULT_TTS_PARAMS, DEFAULT_AUDIO_POSTPROCESSING_PARAMS,
        VALID_API_KEYS, API_KEY_HEADER, MIN_CHAR_PER_SENTENCE_INPUT 
    )
    from app.application_services.tts_service import ApplicationTTSService
    from app.celery_app import celery_app
    from app.tasks import generate_tts_task
except ImportError as e:
    print(f"LỖI NGHIÊM TRỌNG KHI IMPORT TRONG api.py: {e}. "
          "Đảm bảo 'src' đã được thêm vào sys.path và các module con tồn tại.")
    raise

if not logging.getLogger().hasHandlers(): 
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=log_level,
                        format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
tts_app_service: ApplicationTTSService | None = None 

def initialize_global_services():
    """Khởi tạo các global services cần thiết cho ứng dụng Flask. Được gọi từ run.py."""
    global tts_app_service
    if tts_app_service is None:
        logger.info("Bắt đầu khởi tạo ApplicationTTSService từ api.py...")
        try:
            tts_app_service = ApplicationTTSService()
            logger.info("ApplicationTTSService đã được khởi tạo thành công.")
        except Exception as e_init:
            logger.critical(f"LỖI NGHIÊM TRỌNG khi khởi tạo ApplicationTTSService: {e_init}", exc_info=True)
    else:
        logger.info("ApplicationTTSService đã được khởi tạo trước đó, bỏ qua.")

if not os.path.exists(OUTPUT_DIR):
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        logger.info(f"API: Thư mục output '{OUTPUT_DIR}' đã được tạo hoặc đã tồn tại.")
    except OSError as e:
        logger.error(f"API: Không thể tạo thư mục output '{OUTPUT_DIR}': {e}")

def require_api_key(f):
    """Decorator để yêu cầu API key cho một endpoint."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key_received = request.headers.get(API_KEY_HEADER)
        if not api_key_received:
            logger.warning(f"Từ chối truy cập: Thiếu API Key. IP: {request.remote_addr}, Endpoint: {request.endpoint}")
            return jsonify({"error": f"Yêu cầu API Key. Vui lòng cung cấp trong header '{API_KEY_HEADER}'."}), 401

        if not VALID_API_KEYS:
            logger.error("Lỗi cấu hình server: VALID_API_KEYS không được định nghĩa hoặc rỗng.")
            return jsonify({"error": "Lỗi cấu hình phía server, không thể xác thực API Key."}), 500

        if api_key_received not in VALID_API_KEYS:
            logger.warning(f"Từ chối truy cập: API Key không hợp lệ. IP: {request.remote_addr}, Key (một phần): '{api_key_received[:8]}...', Endpoint: {request.endpoint}")
            return jsonify({"error": "API Key không hợp lệ hoặc không được phép."}), 403

        logger.debug(f"Truy cập được chấp nhận với API Key cho endpoint: {request.endpoint}. IP: {request.remote_addr}")
        return f(*args, **kwargs)
    return decorated_function

@app.route('/languages', methods=['GET'])
def get_supported_languages_endpoint():
    """Endpoint trả về danh sách các ngôn ngữ được hỗ trợ."""
    if tts_app_service is None:
        logger.error("/languages: ApplicationTTSService chưa được khởi tạo.")
        return jsonify({"error": "Dịch vụ hiện không khả dụng. Vui lòng thử lại sau."}), 503
    return jsonify(tts_app_service.get_supported_languages())

@app.route('/health', methods=['GET'])
def health_check_endpoint():
    """Endpoint kiểm tra "sức khỏe" của ứng dụng, chủ yếu dựa vào model TTS."""
    if tts_app_service is None:
        logger.error("/health: ApplicationTTSService chưa được khởi tạo.")
        return jsonify({
            "status": "ERROR",
            "message": "Application Service chưa được khởi tạo.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 503

    is_model_healthy, model_message = tts_app_service.check_model_health()
    status_code = 200 if is_model_healthy else 503
    
    response_message = model_message
    if not is_model_healthy:
        response_message = f"API gặp sự cố do model TTS không sẵn sàng: {model_message}"

    return jsonify({
        "status": "OK" if is_model_healthy else "ERROR",
        "message": response_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": {
            "model_ready": is_model_healthy,
            "model_status_message": model_message
        }
    }), status_code

@app.route('/tts', methods=['POST'])
@require_api_key
def api_tts_endpoint_route():
    """Endpoint chính để yêu cầu tổng hợp giọng nói (TTS) bất đồng bộ qua Celery."""
    if tts_app_service is None:
        logger.error("/tts: ApplicationTTSService chưa được khởi tạo.")
        return jsonify({"error": "Hệ thống tạm thời không xử lý được yêu cầu do service chưa sẵn sàng."}), 503

    if 'text' not in request.form or not request.form['text'].strip():
        logger.warning(f"/tts: Yêu cầu thiếu trường 'text'. IP: {request.remote_addr}")
        return jsonify({"error": "Trường 'text' là bắt buộc và không được để trống."}), 400

    input_text = request.form['text']
    if len(input_text) < MIN_CHAR_PER_SENTENCE_INPUT : 
         logger.warning(f"/tts: Văn bản đầu vào quá ngắn. IP: {request.remote_addr}, Length: {len(input_text)}")
         return jsonify({"error": f"Văn bản đầu vào quá ngắn. Yêu cầu tối thiểu {MIN_CHAR_PER_SENTENCE_INPUT} ký tự."}), 400


    input_lang_code = request.form.get('language', 'vi').lower()
    if input_lang_code not in SUPPORTED_LANGUAGES:
        logger.warning(f"/tts: Ngôn ngữ không được hỗ trợ '{input_lang_code}'. IP: {request.remote_addr}")
        return jsonify({"error": f"Ngôn ngữ '{input_lang_code}' không được hỗ trợ. Các ngôn ngữ được hỗ trợ: {', '.join(SUPPORTED_LANGUAGES.keys())}"}), 400

    form_params = request.form.to_dict()
    logger.info(f"Nhận yêu cầu TTS: lang='{input_lang_code}', text_len={len(input_text)}. IP: {request.remote_addr}")
    logger.debug(f"Form params nhận được cho TTS: {form_params}")

    parsed_model_params = {}
    for key, default_val in DEFAULT_TTS_PARAMS.items():
        parse_method_name = f'_parse_{type(default_val).__name__}_param'
        if hasattr(tts_app_service, parse_method_name):
            parsed_model_params[key] = getattr(tts_app_service, parse_method_name)(form_params, key, default_val)
        else:
            parsed_model_params[key] = form_params.get(key, default_val)

    parsed_postproc_params = {}
    for key, default_val in DEFAULT_AUDIO_POSTPROCESSING_PARAMS.items():
        parse_method_name = f'_parse_{type(default_val).__name__}_param'
        if key == "denoise_method":
             parsed_postproc_params[key] = form_params.get(key, default_val)
        elif hasattr(tts_app_service, parse_method_name):
             parsed_postproc_params[key] = getattr(tts_app_service, parse_method_name)(form_params, key, default_val)
        else:
             parsed_postproc_params[key] = form_params.get(key, default_val)
    
    default_normalize_text = DEFAULT_AUDIO_POSTPROCESSING_PARAMS.get('normalize_text', True)
    should_apply_text_normalization = tts_app_service._parse_bool_param(form_params, 'normalize_text', default_normalize_text)

    speaker_audio_path_for_task = "USE_DEFAULT_SPEAKER"
    temp_speaker_file_to_delete_on_dispatch_error = None

    speaker_file_storage = request.files.get('speaker_audio_file')
    if speaker_file_storage and speaker_file_storage.filename:
        try:
            s_filename = secure_filename(speaker_file_storage.filename)
            file_suffix = os.path.splitext(s_filename)[1].lower() or ".wav"
            if file_suffix not in ['.wav', '.mp3', '.ogg', '.flac']: 
                logger.warning(f"/tts: Loại file giọng mẫu không hợp lệ '{file_suffix}'. IP: {request.remote_addr}")
                return jsonify({"error": f"Loại file giọng mẫu không hợp lệ: '{s_filename}'. Chỉ hỗ trợ .wav, .mp3, .ogg, .flac."}), 400

            with tempfile.NamedTemporaryFile(suffix=file_suffix, dir=OUTPUT_DIR, prefix="api_speaker_upload_", delete=False) as tmp_file:
                speaker_file_storage.save(tmp_file)
                speaker_audio_path_for_task = tmp_file.name
            temp_speaker_file_to_delete_on_dispatch_error = speaker_audio_path_for_task
            logger.info(f"API: File giọng mẫu tải lên đã được lưu tạm tại: {speaker_audio_path_for_task}")
        except Exception as e_save:
            logger.error(f"API: Lỗi khi lưu file giọng mẫu tải lên: {e_save}", exc_info=True)
            if temp_speaker_file_to_delete_on_dispatch_error and os.path.exists(temp_speaker_file_to_delete_on_dispatch_error):
                try: os.remove(temp_speaker_file_to_delete_on_dispatch_error)
                except OSError: pass
            return jsonify({"error": f"Lỗi khi xử lý file giọng mẫu tải lên: {str(e_save)}"}), 500

    try:
        task_result_obj = generate_tts_task.delay(
            text_input=input_text,
            language_code=input_lang_code,
            speaker_audio_temp_path_or_flag=speaker_audio_path_for_task,
            apply_text_normalization=should_apply_text_normalization,
            synthesis_model_params=parsed_model_params,
            audio_postproc_params=parsed_postproc_params
        )
        logger.info(f"API: Đã gửi task TTS vào Celery với ID: {task_result_obj.id}. IP: {request.remote_addr}")
        status_check_url = url_for('get_tts_task_status_endpoint', task_id=task_result_obj.id, _external=True)
        return jsonify({
            "message": "Yêu cầu tổng hợp giọng nói đã được tiếp nhận và đang được xử lý.",
            "task_id": task_result_obj.id,
            "status_url": status_check_url
        }), 202
    except Exception as e_dispatch:
        logger.error(f"API: Lỗi khi gửi task tới Celery: {e_dispatch}", exc_info=True)
        if temp_speaker_file_to_delete_on_dispatch_error and os.path.exists(temp_speaker_file_to_delete_on_dispatch_error):
            try:
                os.remove(temp_speaker_file_to_delete_on_dispatch_error)
                logger.info(f"API: Đã dọn dẹp file giọng mẫu tạm (do lỗi dispatch Celery): {temp_speaker_file_to_delete_on_dispatch_error}")
            except OSError as e_remove_tmp:
                logger.error(f"API: Lỗi khi dọn dẹp file giọng mẫu tạm (do lỗi dispatch Celery): {e_remove_tmp}")
        return jsonify({"error": "Lỗi hệ thống khi gửi yêu cầu xử lý giọng nói."}), 500

@app.route('/tts/status/<string:task_id>', methods=['GET'])
@require_api_key
def get_tts_task_status_endpoint(task_id):
    """Endpoint để kiểm tra trạng thái của một tác vụ TTS."""
    logger.debug(f"API Status: Nhận yêu cầu kiểm tra status cho task_id: {task_id}. IP: {request.remote_addr}")
    try:
        task = generate_tts_task.AsyncResult(task_id, app=celery_app)
    except Exception as e_get_task:
        logger.error(f"API Status: Lỗi khi lấy AsyncResult cho task {task_id}: {e_get_task}", exc_info=True)
        return jsonify({"task_id": task_id, "status": "UNKNOWN", "error_message": "Không thể kết nối đến backend để lấy trạng thái task."}), 503

    response_data = {
        "task_id": task_id,
        "status": task.status.upper(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if task.successful():
        task_info = task.result 
        response_data["result"] = {
            "message": "Tổng hợp giọng nói thành công.",
            "filename": task_info.get("filename"),
            "download_url": url_for('download_tts_result_endpoint', task_id=task_id, _external=True)
        }
    elif task.failed():
        error_info_details = "Lỗi không xác định trong quá trình xử lý ở worker."
        try:
            if isinstance(task.result, Exception):
                error_info_details = f"{type(task.result).__name__}: {str(task.result)}"
            elif task.info and isinstance(task.info, Exception) : 
                 error_info_details = f"{type(task.info).__name__}: {str(task.info)}"
            elif task.info : 
                 error_info_details = str(task.info)

        except Exception as e_extract_error:
            logger.error(f"API Status: Lỗi khi trích xuất thông tin lỗi từ task {task_id} thất bại: {e_extract_error}")
        
        logger.warning(f"API Status: Task {task_id} FAILED. Info: {error_info_details}\nTraceback (nếu có từ Celery): {task.traceback}")
        response_data["error_details"] = error_info_details
    else: 
        response_data["message"] = "Yêu cầu đang được xử lý hoặc đang chờ trong hàng đợi..."
        if task.status == 'RETRY' and task.info and isinstance(task.info, dict):
            response_data['retry_info'] = {
                'reason': str(task.info.get('exc')),
                'eta': task.info.get('eta'),
                'retries_left': task.info.get('retries')
            }
            
    return jsonify(response_data)

@app.route('/tts/result/<string:task_id>', methods=['GET'])
@require_api_key
def download_tts_result_endpoint(task_id):
    """Endpoint để tải file âm thanh kết quả của một tác vụ TTS đã hoàn thành."""
    logger.debug(f"API Result: Nhận yêu cầu tải kết quả cho task_id: {task_id}. IP: {request.remote_addr}")
    try:
        task = generate_tts_task.AsyncResult(task_id, app=celery_app)
    except Exception as e_get_task:
        logger.error(f"API Result: Lỗi khi lấy AsyncResult cho task {task_id}: {e_get_task}", exc_info=True)
        return jsonify({"error": "Không thể kết nối đến backend để lấy kết quả task."}), 503

    if task.successful():
        result_data = task.result
        actual_filename_to_serve = result_data.get("filename")

        if actual_filename_to_serve and OUTPUT_DIR:
            file_to_serve_path = os.path.join(OUTPUT_DIR, actual_filename_to_serve)
            
            if os.path.exists(file_to_serve_path):
                logger.info(f"API Result: Chuẩn bị gửi file: '{actual_filename_to_serve}' từ thư mục '{OUTPUT_DIR}' cho task {task_id}.")
                try:
                    return send_from_directory(
                        directory=os.path.abspath(OUTPUT_DIR),
                        path=actual_filename_to_serve,
                        as_attachment=True, 
                        download_name=actual_filename_to_serve 
                    )
                except Exception as e_send_file:
                    logger.error(f"API Result: Lỗi khi gửi file '{file_to_serve_path}': {e_send_file}", exc_info=True)
                    return jsonify({"error": "Lỗi khi chuẩn bị file để tải xuống."}), 500
            else:
                logger.error(f"API Result: Task {task_id} thành công nhưng file kết quả '{file_to_serve_path}' không tồn tại trên server.")
                return jsonify({"error": "File kết quả không tìm thấy trên server. Có thể đã bị xóa hoặc lỗi lưu trữ."}), 404
        else:
            logger.error(f"API Result: Task {task_id} thành công nhưng thiếu thông tin file ('filename' hoặc 'OUTPUT_DIR') trong kết quả: {result_data}")
            return jsonify({"error": "Thông tin file kết quả không đầy đủ hoặc lỗi cấu hình server."}), 500
    elif task.failed():
        logger.warning(f"API Result: Yêu cầu tải kết quả cho task {task_id} nhưng task đã thất bại.")
        return jsonify({"error": "Xử lý tác vụ thất bại. Không có file kết quả để tải. Kiểm tra '/tts/status/<task_id>' để biết chi tiết."}), 400 
    else: 
        logger.info(f"API Result: Yêu cầu tải kết quả cho task {task_id} nhưng task chưa hoàn tất (Status: {task.status}).")
        return jsonify({"message": "Xử lý chưa hoàn tất hoặc task ID không hợp lệ. Kiểm tra lại trạng thái.", "status": task.status.upper()}), 202 



