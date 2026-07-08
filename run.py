import os

from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('APP_PORT', '5000'))
    debug = os.environ.get('APP_DEBUG', 'true').lower() in ('1', 'true', 'yes')
    app.run(host='0.0.0.0', port=port, debug=debug)
