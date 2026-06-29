import base64
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import jinja2
from cookit import flatten
from nonebot import get_plugin_config, require
from pydantic import BaseModel

from ...config import DEFAULT_AVATAR_PATH, config
from ...util import debug
from .. import pic_template
from ..render import register_global_filter_to

require("nonebot_plugin_htmlkit")
from nonebot_plugin_htmlkit import html_to_pic

if TYPE_CHECKING:
    from ...bg_provider import BgBytesData

RES_PATH = Path(__file__).parent / "res"
TEMPLATE_PATH = RES_PATH / "templates"
CSS_PATH = RES_PATH / "css"
GLOBAL_RES_PATH = Path(__file__).parent.parent.parent / "res"

ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATE_PATH)),
    autoescape=jinja2.select_autoescape(["html", "xml"]),
    enable_async=True,
)
register_global_filter_to(ENVIRONMENT)

COMPONENT_COLLECTORS = {
  "header": {"bots", "nonebot_run_time", "system_run_time"},
  "cpu_mem": {
    "cpu_percent",
    "cpu_count",
    "cpu_count_logical",
    "cpu_freq",
    "cpu_brand",
    "memory_stat",
    "swap_stat",
  },
  "disk": {"disk_usage", "disk_io"},
  "network": {"network_io", "network_connection"},
  "process": {"process_status"},
  "footer": {
    "nonebot_version",
    "ps_version",
    "time",
    "python_version",
    "system_name",
  },
}
PERIODIC_COLLECTORS_MAP = {
  "cpu_percent": "cpu_percent_periodic",
  "cpu_freq": "cpu_freq_periodic",
  "disk_usage": "disk_usage_periodic",
  "disk_io": "disk_io_periodic",
  "memory_stat": "memory_stat_periodic",
  "swap_stat": "swap_stat_periodic",
  "time": "time_periodic",
  "network_io": "network_io_periodic",
  "process_status": "process_status_periodic",
}
PERIODIC_COLLECTORS_MAP_REVERSE = {v: k for k, v in PERIODIC_COLLECTORS_MAP.items()}

class TemplateConfig(BaseModel):
  ps_default_components: list[str] = [
    "header",
    "cpu_mem",
    "disk",
    "network",
    "process",
    "footer",
  ]
  ps_default_pic_format: Literal["jpeg", "png"] = "jpeg"
  ps_default_use_periodic: bool = True

template_config = get_plugin_config(TemplateConfig)
collecting = set(
  flatten(COMPONENT_COLLECTORS[k] for k in template_config.ps_default_components),
)
if template_config.ps_default_use_periodic:
  collecting = {(PERIODIC_COLLECTORS_MAP.get(x) or x) for x in collecting}

@pic_template(collecting=collecting)
async def default(collected: dict[str, Any], bg: "BgBytesData", **_) -> bytes:
  for k, v in collected.copy().items():
    if (
      template_config.ps_default_use_periodic
      and k in PERIODIC_COLLECTORS_MAP_REVERSE
    ):
      del collected[k]
      k = PERIODIC_COLLECTORS_MAP_REVERSE[k]
    if isinstance(v, deque):
      collected[k] = v[0] if v else None

  from ...misc_statistics import bot_avatar_cache
  bot_avatars = {}
  for bot_info in collected.get("bots", []):
    self_id = getattr(bot_info, "self_id", None) or bot_info.get("self_id")
    avatar_bytes = None
    if self_id in bot_avatar_cache:
      avatar_bytes = bot_avatar_cache[self_id]
    else:
      avatar_path = config.ps_default_avatar if config.ps_default_avatar.is_file() else DEFAULT_AVATAR_PATH
      if avatar_path.is_file():
        avatar_bytes = avatar_path.read_bytes()
    if avatar_bytes:
      bot_avatars[self_id] = base64.b64encode(avatar_bytes).decode("utf-8")
    else:
      bot_avatars[self_id] = ""

  bg_base64 = ""
  bg_data = getattr(bg, "data", None)
  bg_path = getattr(bg, "path", None)
  if bg_data:
    bg_base64 = base64.b64encode(bg_data).decode("utf-8")
  elif bg_path and bg_path.is_file():
    bg_base64 = base64.b64encode(bg_path.read_bytes()).decode("utf-8")

  css_content = ""
  index_css_path = CSS_PATH / "index.css"
  if index_css_path.is_file():
    css_content += index_css_path.read_text(encoding="utf-8")

  if "process_status" in collected:
    collected["process_status"] = sorted(
      collected.get("process_status", []),
      key=lambda x: getattr(x, "cpu", 0.0) or 0.0,
      reverse=True
    )

  if "network_io" in collected:
    active_nets = []
    for net in collected.get("network_io", []):
      sent_speed = getattr(net, "sent", 0) or 0
      recv_speed = getattr(net, "recv", 0) or 0
      bytes_sent = getattr(net, "bytes_sent", 0) or 0
      bytes_recv = getattr(net, "bytes_recv", 0) or 0
      if (sent_speed > 0 or recv_speed > 0) or (bytes_sent > 0 or bytes_recv > 0):
        active_nets.append(net)
    if not active_nets and collected.get("network_io"):
      active_nets = [collected["network_io"][0]]
    collected["network_io"] = active_nets[:3]

  collected["bot_avatars"] = bot_avatars
  template = ENVIRONMENT.get_template("index.html.jinja")
  html = await template.render_async(
    d=collected,
    config=template_config,
    css_content=css_content,
    bg_base64=bg_base64,
  )

  if debug.enabled:
    debug.write(html, "default_{time}.html")

  return await html_to_pic(
    html=html,
    max_width=650,
    dpi=192.0,
    image_format=template_config.ps_default_pic_format,
  )
