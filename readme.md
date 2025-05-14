# API Tổng Hợp Giọng Nói (Text-to-Speech) Nâng Cao

Dự án này cung cấp một API mạnh mẽ để chuyển đổi văn bản thành giọng nói, sử dụng mô hình XTTS với khả năng sao chép giọng nói (voice cloning) và hỗ trợ nhiều ngôn ngữ. API được thiết kế với kiến trúc bất đồng bộ sử dụng Celery và Redis để xử lý các tác vụ TTS tốn thời gian, đảm bảo tính phản hồi cao cho client. Dự án được đóng gói hoàn chỉnh bằng Docker để dễ dàng triển khai và có cơ chế xác thực bằng API Key.

## Tính năng chính

* **Tổng hợp giọng nói chất lượng cao:** Sử dụng mô hình XTTS tiên tiến.
* **Voice Cloning:** Tạo giọng nói dựa trên một file âm thanh mẫu (.wav, .mp3) được người dùng tải lên.
* **Xác thực API Key:** Bảo vệ các endpoint quan trọng bằng API Key qua header.
* **Xử lý bất đồng bộ:** Các yêu cầu TTS được đưa vào hàng đợi (Celery + Redis) và xử lý bởi các worker riêng biệt.
* **Tùy chỉnh tham số giọng nói:** Điều chỉnh tốc độ đọc (`speed`), nhiệt độ (temperature), và các tham số khác của mô hình XTTS.
* **Xử lý hậu kỳ âm thanh (tùy chọn):**
    * Cắt bỏ khoảng lặng (Trimming).
    * Giảm nhiễu cơ bản (Noise Reduction).
    * Nén âm (Compressor).
    * Cân bằng tần số (EQ).
    * Chuẩn hóa/Giới hạn âm lượng (Normalize/Limiter).
* **Endpoints theo dõi tác vụ:** Client có thể kiểm tra trạng thái và lấy kết quả sau khi xử lý hoàn tất.
* **Đóng gói với Docker:** Cung cấp `Dockerfile` và `docker-compose.yml` để dễ dàng build, triển khai và scale.
* **Hỗ trợ GPU (NVIDIA):** Có thể cấu hình để tận dụng GPU NVIDIA.

## Yêu cầu hệ thống

* [Docker](https://docs.docker.com/get-docker/)
* [Docker Compose](https://docs.docker.com/compose/install/)
* **(Bắt buộc nếu dùng GPU)**: Driver NVIDIA phù hợp trên máy host và [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
* Git (để clone repository này).

## Cài đặt và Thiết lập

1.  **Clone repository này về máy của bạn:**
    ```bash
    git clone https://github.com/ngiad/api-xtts.git
    cd api-xtts
    ```

2.  **Tải về Model Files:**
    API này yêu cầu các file model của XTTS. Chúng **không** được bao gồm trong repository này.
    Bạn cần tải chúng về thủ công và đặt vào thư mục `model/` trong thư mục gốc của dự án.

    **Cấu trúc thư mục `model/` cần có:**
    ```
    model/
    ├── model.pth
    ├── config.json
    ├── vocab.json
    ├── speakers_xtts.pth
    └── vi_sample.wav # File âm thanh mẫu tiếng Việt mặc định
    ```
    * File `speakers_xtts.pth` có thể lấy từ [Coqui XTTS v2 checkpoint gốc](https://huggingface.co/coqui/XTTS-v2/tree/main) nếu cần.

3.  **Cấu hình Biến Môi Trường (API Keys và Cấu hình khác):**
    * Tạo một file `.env` trong thư mục gốc của dự án từ file `.env.example`.
        ```bash
        cp .env.example .env
        ```
    * Mở file `.env` và chỉnh sửa các giá trị, đặc biệt là `VALID_API_KEYS`:
        ```env
        # Trong file .env
        VALID_API_KEYS="YOUR_KEY_1,YOUR_KEY_2" # Thay bằng các API key thực tế của bạn
        API_KEY_HEADER_NAME="X-API-Key" # Hoặc tên header bạn muốn
        # Các biến khác như PORT, REDIS_HOST (nếu không dùng docker-compose default), ...
        ```
    * File `docker-compose.yml` sẽ tự động sử dụng các biến từ file `.env` này.

4.  **(Tùy chọn) Xem lại cấu hình chi tiết:**
    Các cấu hình mặc định khác (tham số TTS, hậu kỳ, Celery) nằm trong `app/config.py` và `app/celery_config.py`.

## Chạy ứng dụng với Docker (Khuyến nghị)

1.  **Build Docker images:**
    Từ thư mục gốc của dự án, chạy lệnh:
    ```bash
    docker-compose build
    ```

2.  **Chạy các services (API, Redis, Celery Worker, Flower):**
    ```bash
    docker-compose up -d
    ```
    Lệnh này sẽ khởi tạo và chạy các container ở chế độ nền. File `docker-compose.yml` đã được cấu hình để có thể sử dụng GPU cho `celery_worker` và `tts_api` (nếu cần) thông qua phần `deploy.resources`.

3.  **Kiểm tra logs:**
    ```bash
    docker-compose logs -f tts_api
    docker-compose logs -f celery_worker
    ```

4.  **Truy cập Flower UI (Giao diện giám sát Celery):**
    Mở trình duyệt và truy cập: `http://localhost:5555` (hoặc port bạn đã cấu hình cho Flower).

### Mở rộng Worker (Scaling Workers) để tăng hiệu năng

Bạn có thể tăng số lượng worker xử lý tác vụ TTS để cải thiện thông lượng của hệ thống, đặc biệt nếu có nhiều yêu cầu đồng thời hoặc có nhiều tài nguyên phần cứng (CPU/GPU).

* **1. Tăng Số Lượng Worker Instances (Containers):**
    Đây là cách phổ biến để mở rộng theo chiều ngang. Bạn có thể tăng số lượng container `celery_worker` bằng lệnh:
    ```bash
    docker-compose up -d --scale celery_worker=N
    ```
    Trong đó `N` là tổng số container worker bạn muốn chạy (ví dụ: `N=3`).
    * **Với GPU:** Nếu bạn có `M` GPU trên máy host và mỗi worker container được cấu hình để sử dụng 1 GPU (thông qua `deploy.resources` trong `docker-compose.yml`), bạn có thể đặt `N` lên đến `M` để tận dụng tối đa các GPU. Docker và NVIDIA Container Toolkit sẽ cố gắng phân bổ GPU cho các container này.
    * Mỗi worker instance (container) sẽ tải model riêng, tiêu tốn RAM/VRAM nhưng đảm bảo độc lập.

* **2. Tăng Concurrency Bên Trong Một Worker Instance:**
    Điều này được điều khiển bởi tùy chọn `-c <số_luồng>` trong lệnh khởi động Celery worker (được định nghĩa trong `command:` của service `celery_worker` trong `docker-compose.yml`).
    ```yaml
    # ví dụ trong docker-compose.yml cho celery_worker:
    command: celery -A app.celery_app worker -l INFO -c 1 # -c 1 là concurrency
    ```
    * **Đối với tác vụ TTS nặng về GPU:**
        * Một tác vụ tổng hợp giọng nói XTTS thường sử dụng đáng kể tài nguyên của một GPU.
        * **Khuyến nghị:** Bắt đầu với `-c 1` cho mỗi worker instance (container) được cấp quyền truy cập một GPU.
        * Tăng `-c` cao hơn cho một worker chỉ có một GPU có thể không tăng hiệu suất mà còn gây lỗi Out of Memory cho GPU hoặc tranh chấp tài nguyên.
        * Nếu tác vụ TTS của bạn có phần xử lý CPU đáng kể (trước hoặc sau khi dùng GPU) và phần GPU diễn ra nhanh, bạn có thể thử nghiệm cẩn thận với `-c` lớn hơn 1 (ví dụ: `2`) và theo dõi sát sao VRAM, GPU utilization.
    * **Đối với tác vụ nặng về CPU:** Nếu bạn có các worker chuyên xử lý tác vụ CPU, bạn có thể đặt `-c` bằng số lượng CPU core khả dụng.

* **3. Theo dõi và Điều chỉnh:**
    * Sử dụng **Flower UI** (`http://localhost:5555`) để theo dõi số lượng task, thời gian xử lý, worker hoạt động.
    * Sử dụng các công cụ hệ thống (`top`, `htop`, `docker stats`) và `nvidia-smi` (trên host hoặc trong container nếu image có) để theo dõi tải CPU, RAM, GPU, VRAM.
    * Dựa trên kết quả theo dõi, hãy điều chỉnh số lượng worker instances (`--scale`) và/hoặc concurrency (`-c`) cho phù hợp với cấu hình của bạn.

* **4. (Nâng cao) Phân tuyến Tác Vụ (Task Routing):**
    Nếu bạn có nhiều loại tác vụ với yêu cầu tài nguyên khác nhau, bạn có thể định nghĩa nhiều hàng đợi (queues) và cấu hình các nhóm worker riêng biệt với concurrency khác nhau để tiêu thụ từ các hàng đợi đó.

5.  **Dừng ứng dụng:**
    ```bash
    docker-compose down
    ```
    Để xóa cả volumes (ví dụ: dữ liệu Redis đã lưu): `docker-compose down -v`

## Chạy ứng dụng cục bộ (Không dùng Docker - Cho phát triển/debug)

1.  Cài đặt Python (3.10+), Redis.
2.  Tạo và kích hoạt môi trường ảo.
3.  Cài đặt PyTorch (phiên bản CPU/GPU phù hợp).
4.  Cài đặt các thư viện khác: `pip install -r requirements.txt`.
5.  Chạy Redis server.
6.  Chạy Celery worker:
    ```bash
    # Từ thư mục gốc dự án, đã kích hoạt môi trường ảo
    celery -A app.celery_app worker -l info -c 1
    ```
7.  Chạy Flask API server:
    ```bash
    # Từ thư mục gốc dự án, đã kích hoạt môi trường ảo
    python run.py
    ```

## Sử dụng API

### Xác thực
Hầu hết các endpoint quan trọng (`/tts`, `/tts/status/*`, `/tts/result/*`) yêu cầu xác thực bằng API Key. Client cần gửi API Key trong HTTP header.
* **Tên Header:** `X-API-Key` (hoặc giá trị bạn đặt cho `API_KEY_HEADER_NAME` trong file `.env`).
* **Giá trị Header:** Một trong các key bạn đã định nghĩa trong biến môi trường `VALID_API_KEYS`.

### Các Endpoint

1.  **`/health` (GET)**
    * Kiểm tra trạng thái API. (Có thể không cần API Key).

2.  **`/languages` (GET)**
    * Lấy danh sách ngôn ngữ hỗ trợ. (Có thể không cần API Key).

3.  **`/tts` (POST)**
    * Gửi yêu cầu tổng hợp giọng nói (bất đồng bộ).
    * **Header yêu cầu:** `X-API-Key: YOUR_API_KEY`
    * **Form-Data:**
        * `text` (bắt buộc): Chuỗi văn bản.
        * `language` (bắt buộc): Mã ngôn ngữ (ví dụ: `vi`).
        * `speaker_audio_file` (tùy chọn): File âm thanh giọng mẫu.
        * `normalize_text` (tùy chọn): `true`/`false` (mặc định `true`).
        * `speed` (tùy chọn): Tốc độ đọc (float, mặc định `1.0`).
        * Các tham số hậu kỳ (xem `app/config.py` cho danh sách đầy đủ và giá trị mặc định của chúng nếu không được gửi hoặc nếu cờ kích hoạt tương ứng được đặt là `false` trong config): `trim_silence`, `reduce_noise`, `apply_compressor`, `apply_eq`, `normalize_volume`, và các giá trị chi tiết của chúng.
    * **Response (202 Accepted):** JSON chứa `task_id` và `status_url`.
        ```json
        {
            "message": "Yêu cầu tổng hợp giọng nói đã được tiếp nhận...",
            "task_id": "task-id",
            "status_url": "http://localhost:5000/tts/status/<task-id>"
        }
        ```

4.  **`/tts/status/<task_id>` (GET)**
    * Kiểm tra trạng thái của tác vụ.
    * **Header yêu cầu:** `X-API-Key: API_KEY`
    * **Response:** JSON chứa trạng thái (PENDING, STARTED, SUCCESS, FAILURE) và link tải nếu thành công.

5.  **`/tts/result/<task_id>` (GET)**
    * Tải file âm thanh kết quả nếu tác vụ thành công.
    * **Header yêu cầu:** `X-API-Key: API_KEY`
    * **Response:** File âm thanh `.wav`.

* **Ví dụ `curl` với API Key:**
    ```bash
    curl -X POST http://localhost:5000/tts \
         -H "X-API-Key: ACTUAL_API_KEY" \
         -F "text=Xin chào các bạn đang theo dõi hướng dẫn này." \
         -F "language=vi" \
         -F "speed=0.9" \
         -F "apply_compressor=true" \
         --output temp_response.json && cat temp_response.json
    ```
    (Lấy `task_id` từ `temp_response.json` để kiểm tra status và tải kết quả).

## Cấu trúc thư mục dự án
* `app/api.py`: Endpoints Flask.
* `app/application_services/`: Services điều phối.
* `app/domain/`: Logic nghiệp vụ cốt lõi.
* `app/config.py`, `app/celery_config.py`: Cấu hình.
* `app/tasks.py`: Định nghĩa Celery tasks.
* `app/celery_app.py`: Khởi tạo Celery app.
* ...



