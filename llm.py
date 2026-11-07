"""Compatibility entry point. Models and indexes are loaded only on demand."""
from campus_assistant.web import create_app

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5555)
