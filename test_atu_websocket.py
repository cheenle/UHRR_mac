#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATU WebSocket连接测试
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Deprecated: atu_client removed; tests replaced by WS proxy integration
# Legacy direct-device test disabled.

if __name__ == '__main__':
    print('This test is deprecated. Use backend WS proxy (/WSCTRX) for ATU data.')