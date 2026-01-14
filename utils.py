import time


def current_timestamp_s() -> int:
    """获取当前时间戳"""
    return int(time.time())

def current_timestamp_ms() -> int:
    """获取当前时间戳"""
    return int(time.time() * 1000)
