"""
智能家居控制技能（Home Assistant）v2
让 AI 助手能直接查询和控制用户 Home Assistant 中的智能设备。
通过后端代理 API（/api/ha/*）与 HA 实例通信。

v2 改进：
- 搜索按域优先级排序（light > climate > switch），过滤噪声实体
- 未连接 HA 时给出友好引导提示
- 状态展示优化，不暴露 entity_id 原始 ID
- list_devices 按实际电器聚类
"""

import httpx
import logging
from typing import Dict, Any, List, Optional

from app.skills.base_skill import BaseSkill

logger = logging.getLogger(__name__)

# ── 状态中文映射 ──
_STATE_MAP = {
    "on": "开启", "off": "关闭",
    "open": "打开", "closed": "关闭",
    "locked": "上锁", "unlocked": "解锁",
    "heat": "加热中", "cool": "制冷中",
    "dry": "除湿", "fan_only": "送风",
    "auto": "自动", "idle": "待机",
    "playing": "播放中", "paused": "暂停",
    "standby": "待机", "unavailable": "离线",
    "unknown": "未知",
    "discharging": "放电中", "charging": "充电中",
    "full": "已充满",
}

# ── 设备域图标映射 ──
_DOMAIN_ICONS = {
    "light": "\U0001f4a1",       # 💡
    "switch": "\U0001f30b",      # 🔌
    "climate": "\U0001f321\ufe0f", # 🌡️
    "fan": "\U0001f300",         # 🌀
    "cover": "\U0001fa9f",       # 🪟
    "media_player": "\U0001f4fa", # 📺
    "lock": "\U0001f512",        # 🔒
}

# ── 域优先级（数值越低越优先）──
_DOMAIN_PRIORITY = {
    "light": 10,
    "climate": 20,
    "cover": 25,
    "media_player": 30,
    "fan": 35,
    "switch": 40,
    "lock": 50,
    # 以下域搜索时默认排除（除非显式指定）
    "button": 99,
    "sensor": 99,
    "binary_sensor": 99,
    "event": 99,
    "notify": 99,
    "number": 99,
    "select": 99,
    "alarm_control_panel": 60,
}


class HomeAssistantSkill(BaseSkill):
    """Home Assistant 智能家居控制技能 v2"""

    name = "homeassistant"
    description = (
        "【智能家居控制】查询和控制 Home Assistant 智能设备。"
        "当用户询问灯的状态、开关灯光、调节亮度、查看温度、控制空调/窗帘/电视等智能家居时调用。"
        "支持：1)列出所有设备及状态 2)查询单个设备详情 3)开关设备 4)调节灯光亮度 "
        "5)设置空调模式(制冷/制热/自动) 6)控制窗帘(打开/关闭) 7)控制媒体播放器(播放/暂停)"
        "触发关键词：智能家居、HA、灯、开灯、关灯、亮度、空调、温度、窗帘、电视、音箱、风扇、"
        "马桶、洗衣机、干衣机、晾衣机、次卧、客厅、卧室、厨房、卫生间、设备、传感器"
    )
    icon = "\U0001f3e0"  # 🏠
    category = "智能家居"
    enabled = True
    auto_trigger = True
    is_direct_tool = False
    trigger_keywords = [
        "智能家居", "homeassistant", "ha", "灯", "开灯", "关灯", "亮灯", "灭灯",
        "亮度", "调光", "空调", "温度", "制冷", "制热", "暖气", "窗帘", "拉窗帘",
        "电视", "音箱", "音响", "播放", "暂停", "风扇", "开关", "马桶",
        "洗衣机", "干衣机", "晾衣机", "次卧", "主卧", "客厅", "卧室", "厨房",
        "卫生间", "设备状态", "传感器", "几盏灯", "哪些灯开着", "家里有什么设备",
        "所有设备", "打开灯", "关掉灯", "把灯打开", "把空调打开", "窗帘拉开",
        "电视开了吗", "音箱在放歌吗", "现在多少度", "室内温度"
    ]

    parameters = {
        "type": "object",
        "required": ["action"],
        "properties": {
            "action": {
                "type": "string",
                "description": (
                    "操作类型："
                    "list_devices — 列出所有可控设备及当前状态摘要；"
                    "get_device — 查询指定设备的详细状态（需配合 entity_id 或 device_name）；"
                    "turn_on — 开启指定设备；"
                    "turn_off — 关闭指定设备；"
                    "toggle — 切换设备开关状态；"
                    "set_brightness — 设置灯光亮度（需配合 brightness 参数 0-255）；"
                    "set_hvac_mode — 设置空调模式（需配合 mode 参数：cool/heat/auto/off/dry/fan_only）；"
                    "open_cover — 打开窗帘；"
                    "close_cover — 关闭窗帘；"
                    "stop_cover — 停止窗帘；"
                    "media_play — 媒体播放；"
                    "media_pause — 媒体暂停；"
                    "search_device — 根据名称模糊搜索设备"
                )
            },
            "entity_id": {
                "type": "string",
                "description": "设备实体 ID（如 light.bedroom_lamp），可通过 search_device 获取"
            },
            "device_name": {
                "type": "string",
                "description": "设备友好名称或关键词（如'次卧灯'、'客厅空调'），用于搜索设备"
            },
            "brightness": {
                "type": "integer",
                "description": "灯光亮度值 0-255（对应 0%-100%）"
            },
            "mode": {
                "type": "string",
                "description": "空调模式：cool(制冷)、heat(制热)、auto(自动)、off(关闭)、dry(除湿)、fan_only(送风)"
            }
        }
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def _ha_get(self, path: str) -> Any:
        """通过代理 API 发 GET 请求（端口从配置读取）"""
        from app.core.config import settings
        base_url = getattr(settings, "internal_api_url", "") or ""
        if not base_url:
            # 自动生成：使用当前配置的端口
            port = getattr(settings, "app_port", 8000)
            base_url = f"http://localhost:{port}"
        url = f"{base_url.rstrip('/')}/api/ha{path}"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    return r.json()
                elif r.status_code == 401:
                    # Token 无效/过期 → 引导用户配置
                    return {"__error__": "__UNCONFIGURED__"}
                elif r.status_code == 400:
                    # 400 = 未配置连接（后端 homeassistant.py 的判断）
                    detail = ""
                    try:
                        jd = r.json()
                        detail = jd.get("detail", "") if isinstance(jd, dict) else ""
                    except Exception:
                        pass
                    if "未配置" in detail or "未连接" in detail or not detail:
                        return {"__error__": "__UNCONFIGURED__"}
                    return {"__error__": detail or f"HA 请求参数错误 (HTTP {r.status_code})"}
                elif r.status_code in (502, 504):
                    return {"__error__": "__UNCONFIGURED__"}
                else:
                    return {"__error__": f"HA API 错误 (HTTP {r.status_code})"}
        except httpx.ConnectError:
            return {"__error__": "__UNCONFIGURED__"}
        except httpx.TimeoutException:
            return {"__error__": "__UNCONFIGURED__"}
        except Exception as e:
            err_msg = str(e)
            if any(x in err_msg for x in ["ConnectError", "ConnectionRefused"]):
                return {"__error__": "__UNCONFIGURED__"}
            return {"__error__": f"请求失败: {err_msg}"}

    async def _ha_post(self, path: str, body: Dict[str, Any]) -> Any:
        """通过代理 API 发 POST 请求"""
        from app.core.config import settings
        base_url = getattr(settings, "internal_api_url", "") or ""
        if not base_url:
            port = getattr(settings, "app_port", 8000)
            base_url = f"http://localhost:{port}"
        url = f"{base_url.rstrip('/')}/api/ha{path}"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(url, json=body)
                if r.status_code in (200, 201):
                    return r.json()
                # 解析错误详情
                detail = ""
                try:
                    jd = r.json()
                    detail = jd.get("detail", "") if isinstance(jd, dict) else ""
                except Exception:
                    pass
                if r.status_code == 400 and ("未配置" in detail or "未连接" in detail):
                    return {"__error__": "__UNCONFIGURED__"}
                if r.status_code == 401:
                    return {"__error__": "HA Token 已失效，请在智能家居页面重新配置"}
                if r.status_code in (502, 504):
                    return {"__error__": "__UNCONFIGURED__"}
                return {"__error__": detail or f"操作失败 (HTTP {r.status_code})"}
        except httpx.ConnectError:
            return {"__error__": "__UNCONFIGURED__"}
        except httpx.TimeoutException:
            return {"__error__": "__UNCONFIGURED__"}
        except Exception as e:
            err_msg = str(e)
            if any(x in err_msg for x in ["ConnectError", "ConnectionRefused"]):
                return {"__error__": "__UNCONFIGURED__"}
            return {"__error__": f"请求失败: {err_msg}"}

    async def run(self, args: Dict[str, Any]) -> str:
        """执行智能家居技能（异步，可直接 await）"""
        action = args.get("action", "").strip().lower()
        return await self._execute(action, args)

    async def _execute(self, action: str, args: Dict[str, Any]) -> str:
        """执行具体操作"""

        if action == "list_devices":
            return await self._list_devices()
        elif action == "get_device":
            return await self._get_device(args)
        elif action in ("turn_on", "turn_off", "toggle"):
            return await self._control_device(args, action)
        elif action == "set_brightness":
            return await self._set_brightness(args)
        elif action == "set_hvac_mode":
            return await self._set_hvac_mode(args)
        elif action in ("open_cover", "close_cover", "stop_cover"):
            return await self._control_cover(args, action)
        elif action in ("media_play", "media_pause"):
            return await self._control_media(args, action)
        elif action == "search_device":
            return await self._search_device(args)
        else:
            return f"\u274c 未知的操作类型: {action}"

    # ════════════════════════════════
    #   工具方法
    # ════════════════════════════════

    @staticmethod
    def _check_error(data: Any) -> Optional[str]:
        """检查返回数据是否包含错误，返回错误消息或 None"""
        if isinstance(data, dict):
            err = data.get("__error__", "")
            if err == "__UNCONFIGURED__":
                return (
                    "\U0001f3e0 **Home Assistant 尚未连接**\n\n"
                    "我目前还无法访问你的智能家居设备。请按以下步骤连接：\n\n"
                    "1. 打开 **智能家居** 页面\n"
                    "2. 输入 Home Assistant 地址（如 `http://192.168.x.x:8123`）\n"
                    "3. 输入长期访问令牌（Long-Lived Access Token）\n"
                    "4. 点击 **保存连接**\n\n"
                    "连接成功后就可以问我「次卧灯开着吗」这类问题了！"
                )
            elif err:
                return f"\u274c {err}"
        return None

    # 搜索时完全排除的域（纯系统内部实体）
    _EXCLUDED_DOMAINS = {
        "button", "sensor", "binary_sensor", "event", "notify",
        "number", "select", "input_boolean", "input_number", "input_text",
        "input_select", "automation", "scene", "timer", "calendar",
        "weather", "sun", "zone", "image", "camera", "remote",
        "update", "device_tracker", "person", "geo_location",
        "text", "time", "date", "counter", "input_datetime",
    }

    # 允许显示的控制域
    _CONTROL_DOMAINS = {"light", "switch", "climate", "fan", "cover", "media_player", "lock", "alarm_control_panel"}

    @staticmethod
    def _is_noise_entity(entity: Dict) -> bool:
        """判断是否为噪声实体"""
        eid = entity.get("entity_id", "")
        domain = eid.split(".")[0] if "." in eid else ""

        # 排除整个域
        if domain in HomeAssistantSkill._EXCLUDED_DOMAINS:
            return True

        name = ((entity.get("attributes") or {}).get("friendly_name") or "")

        # 排除特定模式
        noise_patterns = [
            "_update",
            "* 自定义属性 *",
            "_click_", "_double_click_", "_long_press_",
            "_key_param", "_local_control", "_clear_local", "_clear_wireless",
            "_enter_study", "_get_d_key", "_get_l_key", "_get_s_key",
            "_set_key", "_set_led_", "_brightnesso_", "_brightnessw_",
            "_key_mode", "_key_relay_set",
        ]
        for p in noise_patterns:
            if p in eid or p in name:
                return True
        return False

    @staticmethod
    def _get_device_display_name(entity: Dict) -> str:
        """获取设备的友好显示名称（去掉冗余前缀）"""
        raw_name = ((entity.get("attributes") or {}).get("friendly_name") or entity["entity_id"])
        # 去掉 " * 自定义属性 *" 后缀
        if " * " in raw_name:
            raw_name = raw_name.split(" * ")[0].strip()
        return raw_name.strip()

    @staticmethod
    def _format_state(entity: Dict) -> str:
        """格式化设备状态为中文显示"""
        state = entity.get("state", "unknown")
        domain = entity["entity_id"].split(".")[0]
        attrs = entity.get("attributes") or {}

        mapped = _STATE_MAP.get(state, state)

        # 域特有状态增强
        if domain == "light":
            bri = attrs.get("brightness")
            if state == "on" and bri is not None:
                pct = round(bri / 255 * 100)
                mapped = f"开启 ({pct}%亮度)"
        elif domain == "climate":
            temp = attrs.get("current_temperature")
            if temp is not None:
                mapped += f" \U0001f321\ufe0f {temp}\u00b0C"
            target = attrs.get("temperature")
            if target is not None:
                mapped += f" / 目标{target}\u00b0C"
        elif domain == "cover":
            pos = attrs.get("current_position")
            if pos is not None:
                mapped = f"{'打开' if int(pos) > 90 else ('关闭' if int(pos) < 10 else f'{pos}%')}"

        return mapped

    @staticmethod
    def _filter_and_sort_devices(entities: List[Dict], max_count: int = 8) -> List[Dict]:
        """
        过滤噪声实体 + 按域优先级排序。
        只保留控制域实体（light/climate/switch/cover/fan/media_player/lock）。
        """
        # Step 1: 域过滤 + 噪声过滤
        filtered = []
        for e in entities:
            domain = e["entity_id"].split(".")[0]
            if domain not in HomeAssistantSkill._CONTROL_DOMAINS:
                continue
            if HomeAssistantSkill._is_noise_entity(e):
                continue
            filtered.append(e)

        # Step 2: 按优先级分组
        buckets: Dict[int, List[Dict]] = {}
        for e in filtered:
            domain = e["entity_id"].split(".")[0]
            pri = _DOMAIN_PRIORITY.get(domain, 70)
            buckets.setdefault(pri, []).append(e)

        # Step 3: 每组内按 名称短 > 状态非unknown 排序
        result = []
        for pri in sorted(buckets.keys()):
            bucket = buckets[pri]
            bucket.sort(key=lambda e: (
                100 if e["state"] in ("unknown", "unavailable") else 0,
                len(HomeAssistantSkill._get_device_display_name(e)),
            ))
            result.extend(bucket)

        return result[:max_count]

    # ════════════════════════════════
    #   操作实现
    # ════════════════════════════════

    async def _list_devices(self) -> str:
        """列出所有可控设备（按电器聚类，简洁展示）"""
        data = await self._ha_get("/states")
        err = self._check_error(data)
        if err:
            return err

        if not isinstance(data, list):
            return "\u274c 无法获取设备列表"

        # 只保留控制域的实体
        devices = [
            d for d in data
            if d["entity_id"].split(".")[0] in self._CONTROL_DOMAINS
            and not self._is_noise_entity(d)
            and "_update" not in d["entity_id"]
        ]

        if not devices:
            return "\u26a0\ufe0f 未发现任何可控制的智能设备"

        # 按域统计摘要
        groups: Dict[str, List] = {}
        for d in devices:
            domain = d["entity_id"].split(".")[0]
            groups.setdefault(domain, []).append(d)

        lines = [f"\U0001f3e0 **智能家居设备概览**（共 {len(devices)} 个可控设备）\n"]

        domain_labels = {
            "light": "\U0001f4a1 灯光",
            "switch": "\U0001f30b 开关",
            "climate": "\U0001f321\ufe0f 空调/温控",
            "fan": "\U0001f300 风扇",
            "cover": "\U0001fa9f 窗帘",
            "media_player": "\U0001f4fa 影音设备",
            "lock": "\U0001f512 门锁",
        }

        total_on = 0
        for domain in list(self._CONTROL_DOMAINS):
            items = groups.get(domain, [])
            if not items:
                continue

            on_states = ("on", "open", "unlocked", "heat", "cool", "playing")
            on_count = sum(1 for d in items if d["state"] in on_states)
            total_on += on_count

            label = domain_labels.get(domain, domain)
            icon = _DOMAIN_ICONS.get(domain, "\U0001f4e6")

            lines.append(f"**{label}** ({on_count}/{len(items)} 开启)")

            # 每个域最多显示 8 个设备
            shown = items[:8] if len(items) <= 8 else items[:6] + [{"_more": len(items) - 6}]
            for d in shown:
                if d.get("_more"):
                    lines.append(f"  ... 还有 **{d['_more']}** 个{domain_labels.get(domain, '设备')}")
                    continue
                name = self._get_device_display_name(d)
                state = self._format_state(d)
                is_on = d["state"] in on_states
                dot = "\U0001f7e2" if is_on else "\u2b55"
                lines.append(f"  {dot} {icon} **{name}** — {state}")

            lines.append("")

        lines.append(f"\U0001f4ca 共 **{total_on}/{len(devices)}** 个设备处于工作状态")
        return "\n".join(lines).strip()

    @staticmethod
    def _extract_device_key(entity_id: str) -> str:
        """
        从 entity_id 提取设备键（与前端 homeassistant.html 的 extractDeviceKey 逻辑一致）。
        例：light.linp_cn_123_bedroom_light → linp_cn_123_bedroom
            switch.linp_cn_123_bedroom_on → linp_cn_123_bedroom
        """
        parts = entity_id.split(".")
        if len(parts) < 2:
            return entity_id
        obj_id = parts[1]
        segments = obj_id.split("_")
        # 至少5段才去尾（linp_cn_123_type_action）
        if len(segments) >= 5:
            return "_".join(segments[:-2])
        elif len(segments) >= 3:
            return "_".join(segments[:-1])
        return obj_id

    @staticmethod
    def _cluster_devices(entities: List[Dict]) -> List[Dict]:
        """
        将实体列表聚类为物理设备（一个电器一张卡片）。
        返回 [{key, name, domain, entities: [...], primary_entity}, ...]
        """
        clusters: Dict[str, Dict] = {}
        for e in entities:
            key = HomeAssistantSkill._extract_device_key(e["entity_id"])
            if key not in clusters:
                clusters[key] = {
                    "key": key,
                    "entities": [],
                    "domain": e["entity_id"].split(".")[0],
                }
            clusters[key]["entities"].append(e)

        # 为每个簇推断显示名称和主实体
        for cluster in clusters.values():
            ents = cluster["entities"]
            cluster["primary_entity"] = ents[0]
            info = HomeAssistantSkill._infer_appliance_info(ents)
            cluster["name"] = info["name"]
            cluster["icon_hint"] = info.get("icon_hint", "")

        return list(clusters.values())

    @staticmethod
    def _infer_appliance_info(entities: List[Dict]) -> Dict:
        """从一组关联实体推断电器的最佳显示名称和类型"""
        names = []
        has_light = False
        has_switch = False
        has_climate = False
        has_cover = False
        has_media = False

        for e in entities:
            raw = ((e.get("attributes") or {}).get("friendly_name") or "")
            # 去掉 " * 自定义属性 *"
            if " * " in raw:
                raw = raw.split(" * ")[0].strip()
            names.append(raw)
            d = e["entity_id"].split(".")[0]
            if d == "light":
                has_light = True
            elif d == "switch":
                has_switch = True
            elif d == "climate":
                has_climate = True
            elif d == "cover":
                has_cover = True
            elif d == "media_player":
                has_media = True

        # 选最短、最有意义的名称（通常是 light 的 friendly_name）
        best_name = min(names, key=len) if names else "未知设备"

        icon_hint = ""
        if has_light:
            icon_hint = "light"
        elif has_climate:
            icon_hint = "climate"
        elif has_cover:
            icon_hint = "cover"
        elif has_media:
            icon_hint = "media_player"

        return {"name": best_name, "icon_hint": icon_hint}

    @staticmethod
    def _chinese_fuzzy_match(keyword: str, text: str) -> bool:
        """
        中文模糊匹配：检查 keyword 中的每个"语义单元"是否都存在于 text 中。

        策略：
        1. 将 keyword 和 text 都拆分为语义片段（按空格/常见分隔符）
        2. 对每个 keyword 片段，检查其是否作为子串存在于 text 中
        3. 所有片段都匹配 → True；支持单字回退（如"灯"应匹配"床头灯"）

        例：
          _chinese_fuzzy_match("次卧灯", "次卧床头灯") → True
            （"次卧"∈text 且 "灯"∈text）

          _chinese_fuzzy_match("客厅空调", "客厅大空调") → True
            （"客厅"∈text 且 "空调"∈text）
        """
        if not keyword or not text:
            return False
        kl = keyword.lower()
        tl = text.lower()

        # 快速路径：精确子串匹配
        if kl in tl:
            return True

        # 将 keyword 拆分为"词"（空格分隔 + 常见中文设备词切分）
        kw_parts = keyword.strip().split()

        # 如果只有一个片段且长度>1，尝试逐字符/双字符滑动窗口匹配
        if len(kw_parts) == 1:
            kw = kw_parts[0]
            if len(kw) <= 2:
                # 短关键词（1-2字）：每个字都必须在目标文本中
                return all(ch in tl for ch in kw)
            else:
                # 长关键词：尝试拆成 2 字组
                bigrams = [kw[i:i+2] for i in range(len(kw)-1)]
                matched = sum(1 for bg in bigrams if bg in tl)
                # 至少一半的 2-gram 匹配就算命中
                return matched >= len(bigrams) * 0.5

        # 多片段关键词：每个片段都必须在 text 中出现
        return all(part.lower() in tl for part in kw_parts)

    async def _search_device(self, args: Dict[str, Any]) -> str:
        """
        智能搜索设备 v3 — 按电器聚类，直接回答用户问题。
        核心原则：
        1. 问「灯」→ 只看 light 域，switch 作为附属信息
        2. 问「空调」→ 只看 climate 域
        3. 彻底过滤 button/select/input_* 等非设备实体
        4. 不暴露原始 entity_id
        5. 聚类后给出简洁的电器级摘要
        """
        kw = (args.get("device_name") or "").strip()
        if not kw:
            return "\u274c 请提供 device_name 搜索关键词"

        data = await self._ha_get("/states")
        err = self._check_error(data)
        if err:
            return err

        if not isinstance(data, list):
            return "\u274c 无法获取设备数据"

        kw_lower = kw.lower()

        # ── 判断查询意图：用户在找什么类型的设备？ ──
        intent_light = any(w in kw for w in ["灯", "照明", "亮", "光"])
        intent_climate = any(w in kw for w in ["空调", "温度", "制冷", "制热", "暖气", "温控"])
        intent_cover = any(w in kw for w in ["窗帘", "卷帘", "百叶窗", "遮阳"])
        intent_media = any(w in kw for w in ["电视", "音箱", "音响", "投影", "播放器", "媒体"])
        intent_fan = any(w in kw for w in ["风扇", "排气扇", "新风机"])
        intent_lock = any(w in kw for w in ["门锁", "智能锁"])

        # 根据意图确定目标域
        target_domains = set(self._CONTROL_DOMAINS)
        if intent_light:
            target_domains = {"light"}  # 灯光查询只关注 light 域
        elif intent_climate:
            target_domains = {"climate"}
        elif intent_cover:
            target_domains = {"cover"}
        elif intent_media:
            target_domains = {"media_player"}
        elif intent_fan:
            target_domains = {"fan"}
        elif intent_lock:
            target_domains = {"lock"}

        # ── Step 1: 全量搜索（用于关键词匹配）──
        all_matches = []
        for d in data:
            name = ((d.get("attributes") or {}).get("friendly_name") or "")
            eid = d["entity_id"]
            if self._chinese_fuzzy_match(kw, name) or kw_lower in eid.lower():
                all_matches.append(d)

        if not all_matches:
            return (
                f"\U0001f50d 未找到匹配「**{kw}**」的设备。\n\n"
                f"建议：用更短的关键词搜索（如「次卧」代替「次卧床头灯」），"
                f"或使用「列出所有设备」查看可用设备列表。"
            )

        # ── Step 2: 多级过滤 ──
        # 2a) 域过滤（根据意图缩窄范围）
        filtered = [e for e in all_matches
                    if e["entity_id"].split(".")[0] in target_domains]
        # 如果意图过滤后为空，回退到所有控制域
        if not filtered and target_domains != set(self._CONTROL_DOMAINS):
            filtered = [e for e in all_matches
                        if e["entity_id"].split(".")[0] in self._CONTROL_DOMAINS]

        # 2b) 噪声实体过滤
        filtered = [e for e in filtered if not self._is_noise_entity(e)]

        # 2c) 排除状态为 unknown/unavailable 的实体（除非全部如此）
        available = [e for e in filtered if e.get("state") not in ("unknown", "unavailable")]
        if available:
            filtered = available

        if not filtered:
            noise_count = len([e for e in all_matches if self._is_noise_entity(e)])
            if noise_count > 0:
                return f"\U0001f50d 找到 {len(all_matches)} 个匹配项，但都是系统内部实体（已自动过滤 {noise_count} 个）。换个关键词试试？"
            return f"\U0001f50d 未找到可控设备匹配「**{kw}**」"

        # ── Step 3: 按电器聚类 ──
        clusters = self._cluster_devices(filtered)

        # ── Step 4: 格式化输出 ──

        # 场景A：只有一个聚类结果 → 直接给详情回答
        if len(clusters) == 1:
            c = clusters[0]
            return self._format_single_device_answer(c, kw)

        # 场景B：多个聚类结果 → 列表展示
        lines = [f"\U0001f50d 找到 **{len(clusters)}** 个相关设备:\n"]
        for i, c in enumerate(clusters, 1):
            name = c["name"]
            icon = _DOMAIN_ICONS.get(c.get("icon_hint", ""), "\U0001f4e6")
            # 取主实体的状态
            pe = c.get("primary_entity", c["entities"][0])
            state = self._format_state(pe)
            is_on = pe.get("state", "") in ("on", "open", "unlocked", "heat", "cool", "playing")
            dot = "\U0001f7e2" if is_on else "\u2b55"

            # 子实体摘要（如 "含2个开关"）
            sub_info = ""
            sub_count = len(c["entities"]) - 1
            if sub_count > 0:
                sub_domains = set(e["entity_id"].split(".")[0] for e in c["entities"][1:])
                sub_labels = {"switch": "开关", "light": "灯", "cover": "窗帘", "fan": "风扇"}
                sub_names = [sub_labels.get(d, d) for d in sub_domains if d in sub_labels]
                if sub_names:
                    sub_info = f"（含{'+'.join(sub_names)}）"

            lines.append(f"{dot} {icon} **{name}**{sub_info} — {state}")

        return "\n".join(lines).strip()

    def _format_single_device_answer(self, cluster: Dict, kw: str) -> str:
        """格式化单设备的详细回答（直接回答用户问题）"""
        name = cluster["name"]
        entities = cluster["entities"]
        hint = cluster.get("icon_hint", "")

        icon = _DOMAIN_ICONS.get(hint, "\U0001f4e6")
        lines = [f"{icon} **{name}** 的状态如下：\n"]

        # 按域分组展示
        by_domain: Dict[str, List] = {}
        for e in entities:
            d = e["entity_id"].split(".")[0]
            by_domain.setdefault(d, []).append(e)

        domain_order = ["light", "climate", "cover", "media_player", "fan", "switch", "lock"]
        shown_any = False

        for domain in domain_order:
            items = by_domain.get(domain, [])
            if not items:
                continue
            shown_any = True

            for e in items:
                e_name = self._get_device_display_name(e)
                state = self._format_state(e)
                is_on = e.get("state", "") in ("on", "open", "unlocked", "heat", "cool", "playing")
                dot = "\U0001f7e2" if is_on else "\u2b55"
                d_icon = _DOMAIN_ICONS.get(domain, "")

                # 只有当名称与设备名不同时才显示子项名称
                display_label = e_name if e_name != name else domain.capitalize()

                lines.append(f"{dot} {d_icon} **{display_label}**: {state}")

                # 额外关键属性
                attrs = e.get("attributes") or {}
                extras = []
                if domain == "light" and e["state"] == "on":
                    bri = attrs.get("brightness")
                    if bri is not None:
                        extras.append(f"亮度 {round(bri/255*100)}%")
                elif domain == "climate":
                    t = attrs.get("current_temperature")
                    h = attrs.get("current_humidity")
                    if t is not None:
                        extras.append(f"室温 {t}\u00b0C")
                    if h is not None:
                        extras.append(f"湿度 {h}%")
                elif domain == "cover":
                    pos = attrs.get("current_position")
                    if pos is not None:
                        extras.append(f"开合度 {pos}%")

                if extras:
                    lines.append(f"   \U0001f4ca {' | '.join(extras)}")

        if not shown_any:
            lines.append(f"  未获取到有效状态数据")

        return "\n".join(lines).strip()

    async def _get_device(self, args: Dict[str, Any]) -> str:
        """查询单个设备详情"""
        eid = args.get("entity_id", "")
        name_kw = args.get("device_name", "")

        if not eid and not name_kw:
            return "\u274c 请提供 entity_id 或 device_name 参数"

        if not eid:
            # 通过 _resolve_entity_id 找到最佳匹配（优先高价值域）
            resolved = await self._resolve_entity_id(args)
            if not resolved:
                # 回退：用搜索结果展示
                return await self._search_device({"device_name": name_kw})
            eid = resolved

        data = await self._ha_get(f"/states/{eid}")
        err = self._check_error(data)
        if err:
            return err

        name = self._get_device_display_name(data)
        domain = eid.split(".")[0]
        state = self._format_state(data)
        attrs = data.get("attributes") or {}

        icon = _DOMAIN_ICONS.get(domain, "\U0001f4e6")
        lines = [f"{icon} **{name}** 详情"]
        lines.append(f"- **当前状态**: {state}")

        lu = data.get("last_updated", "")
        if lu:
            lines.append(f"- **最后更新**: {lu[:19]}")

        # 域特有信息
        if domain == "light":
            bri = attrs.get("brightness")
            if bri is not None:
                lines.append(f"- **亮度**: {round(bri/255*100)}% ({bri}/255)")
            ct = attrs.get("color_temp")
            if ct is not None:
                lines.append(f"- **色温**: {ct}")
            hs = attrs.get("hs_color")
            if hs:
                lines.append(f"- **颜色**: H={hs[0]} S={hs[1]}")

        elif domain == "climate":
            lines.append(f"- **室内温度**: {attrs.get('current_temperature', '--')}\u00b0C")
            lines.append(f"- **目标温度**: {attrs.get('temperature', '--')}\u00b0C")
            lines.append(f"- **湿度**: {attrs.get('current_humidity', '--')}%")
            hvac = attrs.get("hvac_mode", "")
            lines.append(f"- **运行模式**: {_STATE_MAP.get(hvac, hvac)}")

        elif domain == "cover":
            pos = attrs.get("current_position")
            if pos is not None:
                lines.append(f"- **当前位置**: {pos}%")

        elif domain == "media_player":
            vol = attrs.get("volume_level")
            if vol is not None:
                lines.append(f"- **音量**: {int(vol*100)}%")
            med_title = attrs.get("media_title")
            artist = attrs.get("media_artist")
            if med_title:
                lines.append(f"- **正在播放**: {med_title}" + (f" - {artist}" if artist else ""))

        return "\n".join(lines)

    async def _control_device(self, args: Dict[str, Any], action: str) -> str:
        """通用设备开关控制"""
        eid = args.get("entity_id", "") or await self._resolve_entity_id(args)
        if not eid:
            return "\u274c 请提供 entity_id 或 device_name 参数"

        domain = eid.split(".")[0]

        if action == "toggle":
            data = await self._ha_get(f"/states/{eid}")
            err = self._check_error(data)
            if err:
                return err
            current_state = data.get("state", "off") if isinstance(data, dict) else "off"
            if current_state in ("on", "open", "playing", "heat", "cool"):
                svc_action = "turn_off"
            else:
                svc_action = "turn_on"
        else:
            svc_action = action

        service_map = {
            "light": {"turn_on": "turn_on", "turn_off": "turn_off"},
            "switch": {"turn_on": "turn_on", "turn_off": "turn_off"},
            "fan": {"turn_on": "turn_on", "turn_off": "turn_off"},
            "climate": {"turn_on": "turn_on", "turn_off": "turn_off"},
            "lock": {"turn_on": "lock", "turn_off": "unlock"},
            "cover": {"turn_on": "open_cover", "turn_off": "close_cover"},
            "media_player": {"turn_on": "turn_on", "turn_off": "turn_off"},
        }

        domain_services = service_map.get(domain, {})
        ha_service = domain_services.get(svc_action, svc_action)

        result = await self._ha_post(f"/service/{domain}/{ha_service}", {"entity_id": eid})
        err = self._check_error(result)
        if err:
            return err

        action_cn = {
            "turn_on": "开启", "turn_off": "关闭", "toggle": "切换",
            "lock": "上锁", "unlock": "解锁",
            "open_cover": "打开", "close_cover": "关闭", "stop_cover": "停止",
        }.get(svc_action, svc_action)

        name = args.get("device_name") or self._resolve_name_from_eid(eid)
        return f"\u2705 已发送**{action_cn}**指令到 **{name}** (`{eid}`)"

    async def _set_brightness(self, args: Dict[str, Any]) -> str:
        """设置灯光亮度"""
        eid = args.get("entity_id", "") or await self._resolve_entity_id(args)
        brightness = args.get("brightness")

        if not eid:
            return "\u274c 请提供 entity_id 或 device_name 参数"
        if brightness is None:
            return "\u274c 请提供 brightness 参数 (0-255)"

        brightness = max(0, min(255, int(brightness)))
        pct = round(brightness / 255 * 100)

        if brightness <= 0:
            result = await self._ha_post("/service/light/turn_off", {"entity_id": eid})
        else:
            result = await self._ha_post("/service/light/turn_on", {"entity_id": eid, "brightness": brightness})

        err = self._check_error(result)
        if err:
            return err
        return f"\u2705 已将亮度设置为 **{pct}%**"

    async def _set_hvac_mode(self, args: Dict[str, Any]) -> str:
        """设置空调模式"""
        eid = args.get("entity_id", "") or await self._resolve_entity_id(args)
        mode = args.get("mode", "")

        if not eid:
            return "\u274c 请提供 entity_id 或 device_name 参数"
        if not mode:
            return "\u274c 请提供 mode 参数"

        valid_modes = ["cool", "heat", "auto", "off", "dry", "fan_only"]
        if mode not in valid_modes:
            return f"\u274c 无效的模式: {mode}"

        mode_labels = {"cool": "制冷", "heat": "制热", "auto": "自动", "off": "关闭", "dry": "除湿", "fan_only": "送风"}

        result = await self._ha_post("/service/climate/set_hvac_mode", {
            "entity_id": eid,
            "hvac_mode": mode,
        })
        err = self._check_error(result)
        if err:
            return err
        return f"\u2705 空调已设为 **{mode_labels.get(mode, mode)}** 模式"

    async def _control_cover(self, args: Dict[str, Any], action: str) -> str:
        """控制窗帘"""
        eid = args.get("entity_id", "") or await self._resolve_entity_id(args)
        if not eid:
            return "\u274c 请提供 entity_id 或 device_name 参数"

        svc_map = {"open_cover": "打开", "close_cover": "关闭", "stop_cover": "停止"}
        label = svc_map.get(action, action)

        result = await self._ha_post(f"/service/cover/{action}", {"entity_id": eid})
        err = self._check_error(result)
        if err:
            return err
        return f"\u2705 窗帘**{label}**指令已发送"

    async def _control_media(self, args: Dict[str, Any], action: str) -> str:
        """控制媒体播放器"""
        eid = args.get("entity_id", "") or await self._resolve_entity_id(args)
        if not eid:
            return "\u274c 请提供 entity_id 或 device_name 参数"

        svc_map = {"media_play": "播放", "media_pause": "暂停"}
        label = svc_map.get(action, action)

        result = await self._ha_post(f"/service/media_player/{action}", {"entity_id": eid})
        err = self._check_error(result)
        if err:
            return err
        return f"\u2705 **{label}**指令已发送"

    async def _resolve_entity_id(self, args: Dict[str, Any]) -> Optional[str]:
        """根据 device_name 解析出 entity_id（优先匹配高价值域）"""
        name_kw = args.get("device_name", "").strip().lower()
        if not name_kw:
            return None

        data = await self._ha_get("/states")
        if not isinstance(data, list):
            return None

        best_match = None
        best_score = 0

        for d in data:
            if self._is_noise_entity(d):
                continue

            name = ((d.get("attributes") or {}).get("friendly_name") or "").lower()

            # 完全匹配直接返回
            if name_kw == name:
                return d["entity_id"]

            # 模糊匹配（中文分词感知）
            if self._chinese_fuzzy_match(name_kw, name) or name_kw in name or name in name_kw:
                domain = d["entity_id"].split(".")[0]
                pri_weight = 100 - _DOMAIN_PRIORITY.get(domain, 70)
                score = min(len(name_kw), len(name)) + pri_weight
                if score > best_score:
                    best_score = score
                    best_match = d["entity_id"]

            # entity_id 匹配（低优先级）
            if name_kw in d["entity_id"].lower():
                if len(name_kw) > best_score:
                    best_match = d["entity_id"]

        return best_match

    async def _resolve_name_from_eid(self, eid: str) -> str:
        """根据 entity_id 反查显示名称"""
        data = await self._ha_get(f"/states/{eid}")
        if isinstance(data, dict) and "__error__" not in data:
            return self._get_device_display_name(data)
        return eid.split(".")[-1][:20]
