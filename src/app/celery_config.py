import os
from dotenv import load_dotenv

load_dotenv() 

worker_concurrency = 1  
worker_max_tasks_per_child = 5
worker_max_memory_per_child = 2000000  
task_time_limit = 600 
task_soft_time_limit = 540 
worker_prefetch_multiplier = 1
task_acks_late = True

_REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
_REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
_REDIS_USERNAME = os.environ.get('REDIS_USERNAME', None)
_REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
_CELERY_BROKER_DB = int(os.environ.get('REDIS_CELERY_DB', 0))
_CELERY_RESULTS_DB = int(os.environ.get('REDIS_CELERY_RESULTS_DB', 1))

_redis_auth_string = ""
if _REDIS_PASSWORD:
    if _REDIS_USERNAME: 
        _redis_auth_string = f"{_REDIS_USERNAME}:{_REDIS_PASSWORD}@"
    else: 
        _redis_auth_string = f":{_REDIS_PASSWORD}@"

BROKER_URL = f"redis://{_redis_auth_string}{_REDIS_HOST}:{_REDIS_PORT}/{_CELERY_BROKER_DB}"
RESULT_BACKEND = f"redis://{_redis_auth_string}{_REDIS_HOST}:{_REDIS_PORT}/{_CELERY_RESULTS_DB}"

TASK_SERIALIZER = 'json'
RESULT_SERIALIZER = 'json'
ACCEPT_CONTENT = ['json']
TIMEZONE = 'Asia/Ho_Chi_Minh'
ENABLE_UTC = True
RESULT_EXPIRES = int(os.environ.get('CELERY_RESULT_EXPIRES', 3600 * 24)) 
IMPORTS = ('app.tasks',)

