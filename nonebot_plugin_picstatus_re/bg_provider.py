import asyncio as aio
import mimetypes
import random
import sys
import time
from collections.abc import AsyncIterable
from pathlib import Path
from typing import NamedTuple, TypeAlias

from cookit.common import race
from cookit.loguru import warning_suppress
from nonebot import get_driver, logger

from .config import BG_PRELOAD_CACHE_DIR, DEFAULT_BG_PATH, ASSETS_PATH, config

if sys.version_info >= (3, 11):
    from asyncio.taskgroups import TaskGroup
else:
    from taskgroup import TaskGroup


class BgBytesData(NamedTuple):
    data: bytes | None
    mime: str


class BgFileData(NamedTuple):
    path: Path | None
    mime: str


BgData: TypeAlias = BgBytesData | BgFileData
DEFAULT_MIME = "application/octet-stream"


def get_bg_files() -> list["Path"]:
    if not config.ps_bg_local_path.exists():
        logger.warning("Custom background path does not exist, fallback to default")
        return [DEFAULT_BG_PATH]
    if config.ps_bg_local_path.is_file():
        return [config.ps_bg_local_path]

    if config.ps_bg_local_path == ASSETS_PATH:
        files = [x for x in config.ps_bg_local_path.glob("default_bg_*.webp") if x.is_file()]
    else:
        files = [
            x for x in config.ps_bg_local_path.glob("*")
            if x.is_file() and x.name != "default_avatar.webp"
        ]
    if not files:
        logger.warning("Custom background dir has no file in it, fallback to default")
        return [DEFAULT_BG_PATH]
    return files


BG_FILES = get_bg_files()


def refresh_bg_files():
    global BG_FILES
    BG_FILES = get_bg_files()


async def local(num: int) -> AsyncIterable[BgData]:
    files = random.sample(BG_FILES, num)
    for x in files:
        yield BgFileData(
            x,
            mimetypes.guess_type(x)[0] or DEFAULT_MIME,
        )


async def none(num: int) -> AsyncIterable[BgData]:
    for _ in range(num):
        yield BgBytesData(None, DEFAULT_MIME)


async def fetch_bg(num: int) -> AsyncIterable[BgData]:
    provider = none if config.ps_bg_provider == "none" else local
    async for x in provider(num):
        yield x


def cache_bg(bg: BgBytesData):
    if not bg.data:
        return BgFileData(None, bg.mime)
    BG_PRELOAD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = BG_PRELOAD_CACHE_DIR / f"{time.time_ns()}.{bg.mime.split('/')[-1]}"
    path.write_bytes(bg.data)
    return BgFileData(path, bg.mime)


def read_cached_bg_file(bg: BgFileData) -> BgBytesData | None:
    if not bg.path:
        return BgBytesData(None, bg.mime)
    with warning_suppress("Failed to read cached file"):
        data = bg.path.read_bytes()
        if bg.path.is_relative_to(BG_PRELOAD_CACHE_DIR):
            with warning_suppress("Failed to unlink cached file"):
                bg.path.unlink()
        return BgBytesData(data, bg.mime)
    return None


async def get_one_fallback() -> BgBytesData:
    with warning_suppress("Failed to get local bg file, fallback to none"):
        async for x in local(1):
            if bg := read_cached_bg_file(x):
                return bg
    logger.warning("Failed to read local bg file, fallback to none")
    return BgBytesData(None, DEFAULT_MIME)


class BgPreloader:
    def __init__(self, preload_count: int):
        self.preload_count = preload_count
        self.background_queue = aio.Queue[BgData]()
        self.current_load_task_main: aio.Task | None = None
        self.consumed_in_loading: bool = False
        self.image_got_signal = aio.Event()
        self.fire_tasks: set[aio.Task] = set()

    async def preload_task(
        self,
        count: int,
        fire: bool = False,
        fire_done_signal: aio.Event | None = None,
    ):
        logger.debug(f"Preload task started, will preload {count} images, {fire=}")
        try:
            async for x in fetch_bg(count):
                logger.debug("Got one image")
                if self.preload_count > 0 or (
                    fire_done_signal and fire_done_signal.is_set()
                ):
                    x = cache_bg(x) if isinstance(x, BgBytesData) else x
                await self.background_queue.put(x)
                self.image_got_signal.set()
                self.image_got_signal.clear()
        except Exception:
            logger.exception("Unexpected error occurred in preload task")
        else:
            logger.debug("Preload task finished")

        if fire:
            return
        if (
            self.consumed_in_loading
            or self.background_queue.qsize() < self.preload_count
        ):
            self.consumed_in_loading = False
            self.start_preload()
        else:
            self.current_load_task_main = None

    def start_preload(self, force: bool = False):
        count = self.preload_count - self.background_queue.qsize()
        if count <= 0 and not force:
            logger.debug(
                "Current background queue size meets preload count, skip preload",
            )
            return
        task = aio.create_task(self.preload_task(count))
        self.current_load_task_main = task

    def set_defer_preload(self):
        if self.current_load_task_main:
            logger.debug("Main preload task already running, set flag")
            self.consumed_in_loading = True
        else:
            self.start_preload()

    async def _get_on_fire(self) -> BgBytesData:
        task_done_signal = aio.Event()
        fire_task = aio.create_task(
            self.preload_task(1, fire=True, fire_done_signal=task_done_signal),
        )
        fire_task.add_done_callback(lambda _: task_done_signal.set())
        fire_task.add_done_callback(lambda _: self.fire_tasks.discard(fire_task))
        self.fire_tasks.add(fire_task)
        try:
            await race(
                task_done_signal.wait(),
                aio.sleep(15),
            )
        finally:
            task_done_signal.set()

        if not self.background_queue.empty():
            bg = await self.background_queue.get()
            self.set_defer_preload()
            if (not isinstance(bg, BgFileData)) or (bg := read_cached_bg_file(bg)):
                return bg

        logger.error("Unable to get an background image, falling back to local")
        return await get_one_fallback()

    async def get(self) -> BgBytesData:
        self.set_defer_preload()

        while not self.background_queue.empty():
            bg = await self.background_queue.get()
            self.set_defer_preload()
            if (not isinstance(bg, BgFileData)) or (bg := read_cached_bg_file(bg)):
                return bg

        return await self._get_on_fire()


bg_preloader = BgPreloader(config.ps_bg_preload_count)

driver = get_driver()


@driver.on_shutdown
async def _():
    for t in bg_preloader.fire_tasks:
        t.cancel()
