if not exist venv (
    python -m venv venv
    call venv\Scripts\activate
    pip install PySide6 requests
)

call venv\Scripts\activate
python app_controller.py