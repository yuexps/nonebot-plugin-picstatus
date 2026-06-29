<!-- markdownlint-disable MD033 MD036 MD041 -->

<div align="center">

# NoneBot-Plugin-PicStatus-Re

以精美的卡片图片形式展示 NoneBot2 运行设备的系统状态（CPU、内存、磁盘、网速、进程等信息），采用 [nonebot/plugin-htmlkit](https://github.com/nonebot/plugin-htmlkit) 将 HTML 渲染为图片。

</div>

## 安装

```bash
# 使用 nb-cli 安装（推荐）
nb plugin install nonebot-plugin-picstatus-re

# 或使用 pip 安装
pip install nonebot-plugin-picstatus-re
```
使用包管理器安装时，需在项目的 `pyproject.toml` 中的 `[tool.nonebot]` 部分的 `plugins` 列表中手动追加 `"nonebot_plugin_picstatus_re"`。

## 使用与配置

- **触发指令**：`状态` / `status`（可在配置中修改）
- **参数配置**：参数均在项目的 `.env.*` 文件中配置，完整说明请参考 **[.env.example](.env.example)**。

## 常见问题

### 启动时出现 `Fontconfig error` 警告

如果在启动时控制台输出大量类似以下的报错：
```log
Fontconfig error: Cannot load default config file: No such file: (null)
Fontconfig error: No writable cache directories
```

**解决方法**：

1. 在 Debian/Ubuntu 系统下，安装系统 `fontconfig` 依赖：
   ```bash
   sudo apt update && sudo apt install -y fontconfig fonts-noto-cjk
   ```
2. 在项目的 `.env` 配置文件中指定环境变量：
   ```env
   FONTCONFIG_PATH="/etc/fonts"
   ```

## 鸣谢

- [nonebot-plugin-picstatus](https://github.com/lgc-NB2Dev/nonebot-plugin-picstatus) (原版插件)
- [nonebot/plugin-alconna](https://github.com/nonebot/plugin-alconna) (命令解析)
- [noneplugin/nonebot-plugin-userinfo](https://github.com/noneplugin/nonebot-plugin-userinfo) (用户信息获取)
- [nonebot/plugin-htmlkit](https://github.com/nonebot/plugin-htmlkit) (HTML 渲染)
- [LoliApi](https://www.loliapi.com/acg/pe/) (图片源)
