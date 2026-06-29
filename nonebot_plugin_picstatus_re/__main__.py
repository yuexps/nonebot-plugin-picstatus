import asyncio

from nonebot import logger, on_command
from nonebot.adapters import Bot as BaseBot, Event as BaseEvent, Message as BaseMessage
from nonebot.matcher import current_bot, current_event, current_matcher
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.rule import Rule, to_me
from nonebot.typing import T_State
from nonebot_plugin_alconna.uniseg import UniMessage

from .bg_provider import bg_preloader
from .collectors import collect_all
from .config import config
from .misc_statistics import bot_avatar_cache, bot_info_cache, cache_bot_avatar
from .templates import render_current_template


def check_empty_arg_rule(arg: BaseMessage = CommandArg()):
    return not arg.extract_plain_text()


def trigger_rule():
    rule = Rule(check_empty_arg_rule)
    if config.ps_need_at:
        rule &= to_me()
    return rule


_cmd, *_alias = config.ps_command
stat_matcher = on_command(
    _cmd,
    aliases=set(_alias),
    rule=trigger_rule(),
    permission=SUPERUSER if config.ps_only_su else None,
)


@stat_matcher.handle()
async def _(bot: BaseBot, event: BaseEvent, state: T_State):
    if (
        (bot.self_id not in bot_avatar_cache)
        and (info := bot_info_cache.get(bot.self_id))
        and info.avatar
    ):
        await cache_bot_avatar(info.avatar, bot, event, state)

    try:
        bg, collected = await asyncio.gather(bg_preloader.get(), collect_all())
        ret = await render_current_template(collected=collected, bg=bg)
    except Exception:
        logger.exception("获取运行状态图失败")
        await UniMessage("获取运行状态图片失败，请检查后台输出").send(
            reply_to=config.ps_reply_target,
        )
    else:
        await UniMessage.image(raw=ret).send(reply_to=config.ps_reply_target)
