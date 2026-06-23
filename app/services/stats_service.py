"""
统计服务模块
封装系统统计业务逻辑
"""

from datetime import datetime

from app.core.config import config
from app.core.stats import stats_manager
from app.core.devices import device_manager
from app.schemas.stats import StatsResponse, HealthResponse


class StatsService:
    """统计服务类"""
    
    def get_stats(self) -> StatsResponse:
        """获取系统统计数据"""
        stats = stats_manager.load_stats()
        devices = device_manager.get_all_devices()
        
        online_count = 0
        now = datetime.now()
        for info in devices.values():
            last_used = info.get("last_used")
            if last_used:
                try:
                    last_time = datetime.fromisoformat(last_used.replace("Z", "+00:00"))
                    if (now - last_time).total_seconds() < 300:
                        online_count += 1
                except ValueError:
                    continue
        
        uptime = now - config.SYSTEM_START_TIME
        uptime_str = f"{uptime.days}天 {uptime.seconds // 3600}时 {(uptime.seconds // 60) % 60}分"
        
        daily_records = stats.get("daily_records", [])
        today_count = stats.get("daily_requests", 0)
        yesterday_count = 0
        if len(daily_records) >= 2:
            yesterday_count = daily_records[-2].get("count", 0)
        
        growth_rate = 0
        if yesterday_count > 0:
            growth_rate = ((today_count - yesterday_count) / yesterday_count * 100)
        
        return StatsResponse(
            daily_requests=today_count,
            total_requests=stats.get("total_requests", 0),
            growth_rate=round(growth_rate, 1),
            online_devices=online_count,
            total_devices=len(devices),
            today_output_tokens=stats.get("today_output_tokens", 0),
            total_output_tokens=stats.get("total_output_tokens", 0),
            tool_calls=stats.get("tool_calls", {}),
            daily_records=daily_records,
            uptime=uptime_str,
            version="1.0.0",
            skill_version="2025-06-18",
        )
    
    async def check_health(self) -> HealthResponse:
        """检查系统健康状态"""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.head(config.DEFAULT_URL)
                latency = response.elapsed.total_seconds() * 1000
                
                if response.status_code == 200:
                    status_text, status_color = "online", "green"
                elif 400 <= response.status_code < 500:
                    status_text, status_color = "rate_limited", "orange"
                else:
                    status_text, status_color = "error", "red"
        except Exception:
            status_text, status_color, latency = "offline", "red", -1
        
        return HealthResponse(
            status=status_text,
            status_color=status_color,
            latency=round(latency, 1) if latency >= 0 else None,
            timestamp=datetime.now().isoformat(),
        )
