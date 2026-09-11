import os

from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('APP_PORT', '5000'))
    # Debug defaults OFF. The Werkzeug interactive debugger allows remote code
    # execution once its PIN is known; never enable it by default.
    debug = os.environ.get('APP_DEBUG', 'false').lower() in ('1', 'true', 'yes')
    app.run(host='0.0.0.0', port=port, debug=debug)
