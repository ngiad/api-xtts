import os
import sys
import logging
from dotenv import load_dotenv


project_root_dir = os.path.dirname(os.path.abspath(__file__))


src_dir = os.path.join(project_root_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)


from app.api import app, initialize_global_services  
from app.config import OUTPUT_DIR                 


dotenv_path = os.path.join(project_root_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

if __name__ == '__main__':
    log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level_str,
        format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s'
    )
    logger = logging.getLogger("MainAppRunner")

    try:
        logger.info("RUN.PY: Bắt đầu khởi tạo global services...")
        initialize_global_services() 
        logger.info("RUN.PY: Global services đã được yêu cầu khởi tạo.")
    except Exception as e_init_main:
        logger.critical(f"RUN.PY: LỖI NGHIÊM TRỌNG KHI KHỞI TẠO GLOBAL SERVICES: {e_init_main}", exc_info=True)
        sys.exit(1)

    if not os.path.exists(OUTPUT_DIR):
        try:
            os.makedirs(OUTPUT_DIR)
            logger.info(f"RUN.PY: Đã tạo thư mục output: {OUTPUT_DIR}")
        except OSError as e:
            logger.error(f"RUN.PY: Không thể tạo thư mục output {OUTPUT_DIR}: {e}")

    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() in ["true", "1", "t"]

    use_reloader_env = os.environ.get("FLASK_USE_RELOADER")
    if use_reloader_env is not None:
        use_reloader_explicit = use_reloader_env.lower() in ["true", "1", "t"]
    else:
        use_reloader_explicit = debug_mode

    logger.info(f"RUN.PY: Khởi chạy server API trên host 0.0.0.0, port {port}, debug mode: {debug_mode}, use_reloader: {use_reloader_explicit}")

    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)