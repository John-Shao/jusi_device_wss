from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from enum import Enum

class MessageType(str, Enum):
    """消息类型枚举"""
    NOTIFY = "notify"
    DEVICE_CONTROL = "device_control"
    CONTROL = "control"
    DEVICE_NOTIFY = "device_notify"
    MESSAGE = "message"

class EventType(str, Enum):
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

class BaseMessage(BaseModel):
    """基础消息模型"""
    type: MessageType
    event: EventType
    deviceId: str = None
    playId: str = None
    code: Optional[int] = 0
    data: Optional[Dict[str, Any]] = None
    
    @field_validator('deviceId')
    def validate_device_id(cls, v):
        if v and len(v) != 32:
            raise ValueError('设备ID必须为32位字符串')
        return v

class DeviceInfo(BaseModel):
    """设备信息模型"""
    no: str = Field(..., description="设备序列号SN")
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
    
    @field_validator('stream_res')
    def validate_resolution(cls, v):
        if v not in [r.value for r in Resolution]:
            raise ValueError(f'不支持的分辨率: {v}')
        return v
    
    @field_validator('stream_bitrate')
    def validate_bitrate(cls, v):
        if v > 4000000:  # 32Mbps
            raise ValueError('比特率不能超过4000000（32Mbps）')
        return v

class DeviceJoinMessage(BaseMessage):
    """设备连接消息"""
    type: MessageType = MessageType.NOTIFY
    event: EventType = EventType.DEVICE_JOIN

class HeartbeatMessage(BaseMessage):
    """心跳消息"""
    type: MessageType = MessageType.NOTIFY
    event: EventType = EventType.JOIN

class GetRtmpMessage(BaseMessage):
    """获取RTMP地址消息"""
    type: MessageType = MessageType.DEVICE_CONTROL
    event: EventType = EventType.GET_RTMP

class GetScreenMessage(BaseMessage):
    """获取截图地址消息"""
    type: MessageType = MessageType.DEVICE_CONTROL
    event: EventType = EventType.GET_SCREEN

class DeviceInfoMessage(BaseMessage):
    """设备信息消息"""
    type: MessageType = MessageType.NOTIFY
    event: EventType = EventType.DEVICE_INFO
    data: DeviceInfo

class ControlMessage(BaseMessage):
    """控制消息"""
    type: MessageType = MessageType.CONTROL