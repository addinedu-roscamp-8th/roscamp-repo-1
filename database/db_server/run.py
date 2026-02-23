#!/usr/bin/env python
"""Flask 애플리케이션 실행 스크립트"""
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

