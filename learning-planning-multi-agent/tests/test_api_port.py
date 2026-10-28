# 文件：tests/test_api_port.py
# 功能：验证后端监听端口解析，保证默认端口避开被占用的 8000，且异常输入能安全回落
# 输入：API_PORT 环境变量；输出：断言结果

from __future__ import annotations

import pytest

from api_server import DEFAULT_API_PORT, resolve_api_port


def test_default_port_is_8001(monkeypatch):
    """未设置 API_PORT 时默认 8001（本机 8000 常被 Docker 等服务占用）"""
    monkeypatch.delenv("API_PORT", raising=False)
    assert DEFAULT_API_PORT == 8001
    assert resolve_api_port() == 8001


def test_port_can_be_overridden(monkeypatch):
    """API_PORT 合法时按配置生效，便于多环境并存"""
    monkeypatch.setenv("API_PORT", "8020")
    assert resolve_api_port() == 8020


def test_blank_port_falls_back(monkeypatch):
    """空白值视为未设置"""
    monkeypatch.setenv("API_PORT", "   ")
    assert resolve_api_port() == DEFAULT_API_PORT


@pytest.mark.parametrize("raw", ["abc", "80.5", "0", "70000", "-1"])
def test_invalid_port_falls_back(monkeypatch, raw):
    """非整数或越界端口回落到默认值，而不是让服务起不来"""
    monkeypatch.setenv("API_PORT", raw)
    assert resolve_api_port() == DEFAULT_API_PORT
