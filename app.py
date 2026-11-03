import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    # Debug on for local development, off in production (APP_ENV=production).
    # FLASK_DEBUG is honored when explicitly set; otherwise APP_ENV decides.
    flask_debug = os.environ.get("FLASK_DEBUG")
    if flask_debug is None:
        debug = os.environ.get("APP_ENV", "development").lower() != "production"
    else:
        debug = flask_debug.lower() == "true"
    app.run(debug=debug, host=host, port=port)
