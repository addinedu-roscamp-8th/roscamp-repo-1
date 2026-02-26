#!/usr/bin/env python3
"""
Main Server 실행 스크립트
Usage: python3 run_main_server.py
"""
import sys
import os

# 현재 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main_server.main_server_node import main

if __name__ == '__main__':
    main()
