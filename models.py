from urllib import request
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from enum import Enum
from utils import current_timestamp_s


class DriftMsgType(str, Enum):
    """消息类型枚举"""
    D2S_NOTIFY = "notify"    # 设备->系统
    D2S_DEVICE_CONTROL = "device_control"  # 设备->系统
    S2D_CONTROL = "control"  # 系统->设备
    S2D_DEVICE_NOTIFY = "device_notify"    # 系统->设备
    S2D_MESSAGE = "message"  # 系统->设备

class DriftEvent(str, Enum):
    """事件类型枚举"""
    # 设备事件
    JOIN = "join"
    DEVICE_JOIN = "device_join"
    DEVICE_INFO = "device_info"
    POWER_OFF = "power_off"
    GET_RTMP = "get_rtmp"
    GET_SCREEN = "get_screen"
    
    # 控制事件
    START_RTMP = "start_rtmp"
    STOP_RTMP = "stop_rtmp"
    START_RTSP = "start_rtsp"
    STOP_RTSP = "stop_rtsp"
    START_RECORD = "start_record"
    STOP_RECORD = "stop_record"
    DZOOM = "dzoom"
    STREAM_RES = "stream_res"
    STREAM_BITRATE = "stream_bitrate"
    STREAM_FRAMERATE = "stream_framerate"
    LED = "led"
    EXPOSURE = "exposure"
    FILTER = "filter"
    MIC_SENSITIVITY = "mic_sensitivity"
    FOV = "fov"
    SCREEN = "screen"

class Resolution(str, Enum):
    """分辨率枚举"""
    RES_4K = "4K"
    RES_4KUHD = "4KUHD"
    RES_2_7K = "2.7K"
    RES_1080P = "1080P"
    RES_720P = "720P"
    RES_WVGA = "WVGA"

# 基础消息格式（设备发送的消息、发送给设备的消息）
class DriftMessage(BaseModel):
    """基础消息模型"""
    type: DriftMsgType
    event: DriftEvent
    deviceId: str = ""
    playId: Optional[str] = ""
    data: Optional[Dict[str, Any]] = {}
    code: Optional[int] = 0

    @field_validator('deviceId')
    def validate_device_id(cls, v):
        if v and len(v) != 32:
            raise ValueError('设备ID必须为32位字符串')
        return v
    
class DeviceInfo(BaseModel):
    """设备信息模型"""
    no: str = Field("", description="device_sn")
    dzoom: int = Field(1, description="缩放状态（1-正常，其他值按设备定义）")
    rtmp: str = Field("stop", description="推流状态（start/stop）")
    rtmp_url: str = Field("", description="RTMP推流地址")
    rtsp: str = Field("stop", description="RTSP状态（start/stop）")
    rtsp_url: str = Field("", description="RTSP地址")
    record: str = Field("stop", description="录像状态（start/stop）")
    stream_res: str = Field("720P", description="分辨率")
    stream_bitrate: int = Field(2000000, description="比特率（字节/秒）")
    stream_framerate: int = Field(30, description="帧率（FPS）")
    led: int = Field(0, description="LED状态（0-关闭，1-开启）")
    exposure: int = Field(1, description="曝光值（0-4）")
    filter: int = Field(0, description="滤镜模式（0-正常，1-鲜艳，2-低光）")
    mic_sensitivity: int = Field(3, description="麦克风灵敏度（0-5）")
    fov: int = Field(140, description="镜头角度（140/110/90）")

class DeviceStatus(BaseModel):
    """设备状态模型"""
    device_id: str = Field("", description="设备ID")
    device_info: Optional[DeviceInfo] = None  # 设备信息
    connection_time: int = Field(current_timestamp_s(), description="连接时间")
    last_heartbeat: int = Field(current_timestamp_s(), description="最后心跳时间")

'''
class DeviceJoinMessage(DriftRequest):
    """设备连接消息"""
    type: MessageType = MessageType.D2S_NOTIFY
    event: EventType = EventType.DEVICE_JOIN

class HeartbeatMessage(DriftRequest):
    """心跳消息"""
    type: MessageType = MessageType.D2S_NOTIFY
    event: EventType = EventType.JOIN

class GetRtmpMessage(DriftRequest):
    """获取RTMP地址消息"""
    type: MessageType = MessageType.D2S_DEVICE_CONTROL
    event: EventType = EventType.GET_RTMP

class GetScreenMessage(DriftRequest):
    """获取截图地址消息"""
    type: MessageType = MessageType.D2S_DEVICE_CONTROL
    event: EventType = EventType.GET_SCREEN

class DeviceInfoMessage(DriftRequest):
    """设备信息消息"""
    type: MessageType = MessageType.D2S_NOTIFY
    event: EventType = EventType.DEVICE_INFO
    data: DeviceInfo

class ControlMessage(DriftRequest):
    """控制消息"""
    type: MessageType = MessageType.S2D_CONTROL
'''

# ================================== 云监视 ==================================

class MonitorMsgType(str, Enum):
    """云监视消息类型枚举"""
    GET_DEVICE_LIST = "get_device_list"  # 获取设备列表
    GET_DEVICE_STATUS = "get_device_status"  # 获取设备状态

class MonitorRequest(BaseModel):
    """云监视请求消息"""
    type: str = Field("", description="消息类型")
    data: Optional[Dict[str, Any]] = Field({}, description="数据")

class MonitorResponse(BaseModel):
    """云监视响应消息"""
    code: int = Field(0, description="状态码")
    info: str = Field("ok", description="状态信息")
    type: str = Field("", description="消息类型")
    data: Optional[Dict[str, Any]] = Field({}, description="数据")
    