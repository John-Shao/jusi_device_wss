import json
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from utils import current_timestamp_ms


logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""
    
    async def dispatch(self, request: Request, call_next):
        # 记录请求开始时间
        start_time = current_timestamp_ms()
        
        # 获取请求体（对于可能验证失败的情况特别重要）
        request_body = await self._get_request_body(request)
        
        # 记录请求信息
        logger.info(f"请求开始: {request.method} {request.url}")
        logger.info(f"请求头: {dict(request.headers)}")
        logger.info(f"查询参数: {dict(request.query_params)}")
        logger.info(f"路径参数: {request.path_params}")
        
        if request_body:
            # 格式化请求体为易读JSON
            formatted_request_body = self._format_body(request_body)
            logger.info(f"请求体: {formatted_request_body}")
        
        # 存储请求体到 state 以便后续使用
        request.state.request_body = request_body
        
        try:
            # 继续处理请求
            response = await call_next(request)
        except Exception as e:
            # 处理异常
            logger.error(f"请求处理异常: {str(e)}")
            logger.error(f"请求URL: {request.url}")
            if hasattr(request.state, 'request_body'):
                formatted_request_body = self._format_body(request.state.request_body)
                logger.error(f"请求体: {formatted_request_body}")
            raise

        # 尝试读取并记录响应体（安全且有限制）
        response_body = None
        try:
            max_bytes = 10 * 1024  # 日志中记录的最大字节数，超过会被截断
            content_type = response.headers.get("content-type", "")
            # 对于可能的文件/大流式响应，避免读取大量数据
            content_length = response.headers.get("content-length")
            should_try_read = False
            if content_length is not None:
                try:
                    should_try_read = int(content_length) <= max_bytes
                except Exception:
                    should_try_read = False
            else:
                # 若没有 content-length，且类型可读时尝试读取
                if content_type.startswith("application/json") or content_type.startswith("text/"):
                    should_try_read = True

            if should_try_read:
                # 首先尝试从 body_iterator 读取（针对 StreamingResponse）
                if hasattr(response, "body_iterator"):
                    body = b""
                    truncated = False
                    async for chunk in response.body_iterator:
                        body += chunk
                        if len(body) > max_bytes:
                            body = body[:max_bytes]
                            truncated = True
                            break

                    # body_iterator 已耗尽，需要创建新的 Response 供客户端使用
                    from starlette.responses import Response
                    new_response = Response(content=body, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)
                    response = new_response

                    if body:
                        try:
                            if "application/json" in content_type:
                                response_body = json.loads(body.decode("utf-8"))
                            else:
                                response_body = body.decode("utf-8", errors="ignore")
                            if truncated:
                                response_body = str(response_body) + " ... <truncated>"
                        except Exception:
                            response_body = "<可读响应体解析失败>"

                # 如果没有 body_iterator，尝试从 response.body 读取
                elif hasattr(response, "body"):
                    body = response.body
                    if isinstance(body, (bytes, bytearray)):
                        truncated = len(body) > max_bytes
                        if truncated:
                            body = body[:max_bytes]
                        try:
                            if "application/json" in content_type:
                                response_body = json.loads(body.decode("utf-8"))
                            else:
                                response_body = body.decode("utf-8", errors="ignore")
                            if truncated:
                                response_body = str(response_body) + " ... <truncated>"
                        except Exception:
                            response_body = "<可读响应体解析失败>"

        except Exception as e:
            logger.warning(f"获取响应体失败: {e}")

        # 计算处理时间
        process_time = current_timestamp_ms() - start_time
        
        # 记录响应信息
        logger.info(f"请求结束: {request.method} {request.url} - 状态码: {response.status_code} - 耗时: {process_time:.4f}ms")
        logger.info(f"响应头: {dict(response.headers)}")
        if response_body is not None:
            # 格式化响应体为易读JSON
            formatted_response_body = self._format_body(response_body)
            logger.info(f"响应体: {formatted_response_body}")
        
        return response
    
    async def _get_request_body(self, request: Request):
        """安全地获取请求体"""
        try:
            # 对于JSON请求
            if request.headers.get("content-type", "").startswith("application/json"):
                body = await request.body()
                if body:
                    try:
                        return json.loads(body.decode("utf-8"))
                    except json.JSONDecodeError:
                        return body.decode("utf-8")
            
            # 对于表单数据
            elif request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
                form_data = await request.form()
                return dict(form_data)
            
            # 对于 multipart/form-data
            elif request.headers.get("content-type", "").startswith("multipart/form-data"):
                # 注意：对于文件上传，不要读取整个文件到内存
                form_data = await request.form()
                result = {}
                for key, value in form_data.items():
                    if hasattr(value, 'filename'):  # 文件字段
                        result[key] = f"<文件: {value.filename}, 大小: {value.size}字节>"
                    else:
                        result[key] = value
                return result
            
            # 其他类型的请求体
            else:
                body = await request.body()
                if body:
                    return body.decode("utf-8", errors="ignore")
                
        except Exception as e:
            logger.warning(f"获取请求体失败: {e}")
        
        return None
    
    def _format_body(self, body):
        """格式化请求体或响应体为易读JSON"""
        try:
            if isinstance(body, (dict, list)):
                # 如果已经是JSON对象，直接格式化
                return json.dumps(body, indent=2, ensure_ascii=False)
            elif isinstance(body, str):
                # 如果是字符串，尝试解析为JSON后再格式化
                try:
                    parsed_json = json.loads(body)
                    return json.dumps(parsed_json, indent=2, ensure_ascii=False)
                except (json.JSONDecodeError, TypeError):
                    # 如果不是JSON字符串，直接返回
                    return body
            else:
                # 其他类型直接返回
                return body
        except Exception as e:
            logger.warning(f"格式化请求体/响应体失败: {e}")
