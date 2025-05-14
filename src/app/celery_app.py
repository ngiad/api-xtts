import os
import sys
import logging
from celery import Celery
from dotenv import load_dotenv


_current_file_path = os.path.abspath(__file__)
_app_dir = os.path.dirname(_current_file_path)
_src_dir = os.path.dirname(_app_dir)

if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
    print(f"[celery_app.py DEBUG] Đã thêm '{_src_dir}' vào sys.path") 


_project_root = os.path.dirname(_src_dir) 
_dotenv_path = os.path.join(_project_root, '.env')

if os.path.exists(_dotenv_path):
    load_dotenv(dotenv_path=_dotenv_path)
else:
    load_dotenv() 

logger = logging.getLogger(__name__)


celery_app = Celery('app')

try:
    celery_app.config_from_object('app.celery_config')
    logger.info("Nạp cấu hình Celery thành công từ 'app.celery_config'.")

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"  Broker từ config      : {celery_app.conf.get('BROKER_URL', 'Chưa đặt')}")
        logger.debug(f"  Backend từ config     : {celery_app.conf.get('RESULT_BACKEND', 'Chưa đặt')}")
        logger.debug(f"  Task imports từ config: {celery_app.conf.get('IMPORTS', 'Chưa đặt')}")

except ImportError as e_import_config:
    logger.error(f"LỖI IMPORT: Không thể nạp module cấu hình 'app.celery_config': {e_import_config}", exc_info=True)
    logger.warning("Celery sẽ sử dụng cấu hình Redis mặc định (hoặc từ biến môi trường) do lỗi nạp 'app.celery_config'.")
    default_redis_host = os.environ.get('REDIS_HOST', 'localhost')
    default_redis_port = int(os.environ.get('REDIS_PORT', 6379))
    celery_app.conf.broker_url = os.environ.get('CELERY_BROKER_URL', f"redis://{default_redis_host}:{default_redis_port}/{int(os.environ.get('REDIS_CELERY_DB',0))}")
    celery_app.conf.result_backend = os.environ.get('CELERY_RESULT_BACKEND_URL', f"redis://{default_redis_host}:{default_redis_port}/{int(os.environ.get('REDIS_CELERY_RESULTS_DB',1))}")
    celery_app.conf.imports = ('app.tasks',) 
    logger.info(f"Đã áp dụng cấu hình Redis dự phòng. Broker: {celery_app.conf.broker_url}")

except Exception as e_config:
    logger.error(f"LỖI KHÔNG XÁC ĐỊNH khi nạp cấu hình Celery từ 'app.celery_config': {e_config}", exc_info=True)
    logger.warning("Celery sẽ sử dụng cấu hình Redis mặc định (hoặc từ biến môi trường) do lỗi không xác định.")
    default_redis_host = os.environ.get('REDIS_HOST', 'localhost')
    default_redis_port = int(os.environ.get('REDIS_PORT', 6379))
    celery_app.conf.broker_url = os.environ.get('CELERY_BROKER_URL', f"redis://{default_redis_host}:{default_redis_port}/{int(os.environ.get('REDIS_CELERY_DB',0))}")
    celery_app.conf.result_backend = os.environ.get('CELERY_RESULT_BACKEND_URL', f"redis://{default_redis_host}:{default_redis_port}/{int(os.environ.get('REDIS_CELERY_RESULTS_DB',1))}")
    celery_app.conf.imports = ('app.tasks',)
    logger.info(f"Đã áp dụng cấu hình Redis dự phòng. Broker: {celery_app.conf.broker_url}")


try:
    import app.tasks
    logger.info("Import thử module 'app.tasks' thành công. Các tasks nên được đăng ký thông qua cấu hình IMPORTS.")
except ImportError as e_tasks:
    logger.critical(
        f"LỖI NGHIÊM TRỌNG: Không thể import trực tiếp module 'app.tasks': {e_tasks}. "
        f"Hãy đảm bảo 'app.tasks.py' tồn tại và thư mục 'src' đã được thêm vào sys.path đúng cách. "
        f"Việc tự động tìm tasks có thể thất bại.",
        exc_info=True
    )
if __name__ == '__main__':
    logger.info("Chạy Celery application trực tiếp từ celery_app.py (thường dùng cho mục đích gỡ lỗi module này)...")
    celery_app.start()

