"""Entry point: `flask --app app run` or `python app.py`."""
from webapp import create_app

app = create_app()

if __name__ == "__main__":
    app.run(port=5000)
