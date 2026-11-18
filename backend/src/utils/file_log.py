# -*- coding: utf-8 -*-
"""把服务运行时的终端输出同步写进日志文件，方便事后查看。

项目的日志绝大部分是 print()，只有编排器用了 logging，而 uvicorn 的访问日志
走 logging.StreamHandler -> sys.stderr。单独加 FileHandler 会漏掉 print，
单独重定向 stdout 会漏掉 uvicorn，所以这里做两件事：

1. 用 _Tee 包住 sys.stdout / sys.stderr：终端照常显示，同时按行加时间戳落盘；
2. 把已经创建的 logging.StreamHandler 重新指向 _Tee，避免 uvicorn 的日志
   仍绑定到替换前的原始 stderr（用 `python -m uvicorn ...` 启动时会这样）。

进程内只安装一次；pytest 环境自动跳过，避免干扰它的输出捕获。
"""

from __future__ import annotations

import atexit
import logging
import os
import sys
import threading
from datetime import datetime

from src.paths import BACKEND_ROOT, LOG_DIR

LOG_FILE = LOG_DIR / "server.log"
MAX_BYTES = int(os.getenv("FILE_LOG_MAX_BYTES", str(5 * 1024 * 1024)))
BACKUP_COUNT = int(os.getenv("FILE_LOG_BACKUP_COUNT", "3"))

_installed = False
_sink: _LogSink | None = None


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class _LogSink:
    """带按大小轮转的日志文件写入器（线程安全）。"""

    def __init__(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._file = open(LOG_FILE, "a", encoding="utf-8", errors="replace")

    def write_line(self, line: str) -> None:
        text = f"[{_timestamp()}] {line}\n"
        with self._lock:
            try:
                if self._file.tell() + len(text.encode("utf-8", "replace")) > MAX_BYTES:
                    self._rotate()
                self._file.write(text)
                self._file.flush()
            except (OSError, ValueError):
                # 日志写失败不能反过来把服务搞挂
                pass

    def _rotate(self) -> None:
        self._file.close()
        oldest = LOG_FILE.parent / f"{LOG_FILE.name}.{BACKUP_COUNT}"
        if oldest.exists():
            oldest.unlink()
        for i in range(BACKUP_COUNT - 1, 0, -1):
            src = LOG_FILE.parent / f"{LOG_FILE.name}.{i}"
            if src.exists():
                src.replace(LOG_FILE.parent / f"{LOG_FILE.name}.{i + 1}")
        LOG_FILE.replace(LOG_FILE.parent / f"{LOG_FILE.name}.1")
        self._file = open(LOG_FILE, "a", encoding="utf-8", errors="replace")
        self._file.write(f"[{_timestamp()}] === 日志已轮转，上一段见 server.log.1 ===\n")
        self._file.flush()

    def close(self) -> None:
        with self._lock:
            try:
                self._file.close()
            except OSError:
                pass


class _Tee:
    """终端原样输出，文件按行加时间戳。"""

    def __init__(self, stream, sink: _LogSink) -> None:
        self._stream = stream
        self._sink = sink
        self._buf = ""
        # to_thread 之后会有多个线程同时 print；缓冲拼接不能交错，否则日志会串行/丢字
        self._buf_lock = threading.Lock()

    def write(self, s) -> int:
        if isinstance(s, bytes):
            s = s.decode("utf-8", "replace")
        with self._buf_lock:
            try:
                self._stream.write(s)
            except Exception:
                pass
            self._buf += s
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                self._sink.write_line(line.rstrip("\r"))
        return len(s)

    def writelines(self, lines) -> None:
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        try:
            self._stream.flush()
        except Exception:
            pass

    def isatty(self) -> bool:
        try:
            return bool(self._stream.isatty())
        except Exception:
            return False

    def fileno(self):
        return self._stream.fileno()

    def __getattr__(self, name):
        return getattr(self.__dict__["_stream"], name)


def _all_loggers():
    """root + 所有已创建的具名 logger。"""
    yield logging.getLogger()
    for obj in list(logging.root.manager.loggerDict.values()):
        if isinstance(obj, logging.Logger):
            yield obj


def enable_file_logging() -> None:
    """启用文件日志。幂等，可安全调用多次。"""
    global _installed, _sink

    if _installed:
        return
    if os.getenv("FILE_LOG_ENABLED", "1").lower() in ("0", "false", "off", "no"):
        return
    # pytest 会替换 sys.stdout 做输出捕获，这里必须让开
    if "pytest" in sys.modules:
        return

    _installed = True  # 先置位，避免后续异常导致反复重试
    try:
        sink = _LogSink()
        _sink = sink
        original_out, original_err = sys.stdout, sys.stderr
        tee_out = _Tee(original_out, sink)
        tee_err = _Tee(original_err, sink)
        sys.stdout, sys.stderr = tee_out, tee_err

        # `python -m uvicorn ...` 会先配置好 logging，此时把已有 handler 指过来
        for logger in _all_loggers():
            for handler in logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    continue
                if isinstance(handler, logging.StreamHandler):
                    stream = getattr(handler, "stream", None)
                    if stream is original_out:
                        handler.setStream(tee_out)
                    elif stream is original_err:
                        handler.setStream(tee_err)

        sink.write_line("=" * 60)
        sink.write_line(
            f"=== 服务启动 | pid={os.getpid()} | 端口={os.getenv('API_PORT', '8001')} "
            f"| 文件={LOG_FILE.relative_to(BACKEND_ROOT)} ==="
        )
        sink.write_line("=" * 60)

        def _on_exit() -> None:
            sink.write_line(f"=== 服务退出 | pid={os.getpid()} ===")
            sink.close()

        atexit.register(_on_exit)
    except OSError as exc:
        # 目录不可写时保持纯终端输出，不影响服务
        sys.__stderr__.write(f"[file_log] 日志文件不可用，已跳过: {exc}\n")
