# 音击抽卡模拟器（AstrBot 版）

版本：1.1.0

本目录是 [ongeki_gacha](https://github.com/DeepSeek-V4-Pro/ongeki_gacha)
（MaiBot 版原作）的 AstrBot 本地运行版。抽卡规则、数据库、卡池排表和
Pillow 渲染逻辑全部沿用原作，本地代码不是框架重写；这里只增加一个最小
MaiBot SDK 兼容层，并把消息入口、配置与数据目录接到 AstrBot。

## 功能

- `/签到`：每日领取点数、连续签到奖励、月卡加成和非抽卡卡彩蛋；
- `/月卡`：购买、续费或查看月卡；
- `/抽卡 [常驻] [1|5|11]`：按卡池概率抽卡，并发送合成卡面图；
- `/点数`：查看余额、连续签到、月卡与囤点状态；
- `/卡册`：查看已收集卡牌和进度；
- `/卡图 <ID>`：发送已拥有的高清卡面；
- `/卡池 [列表|下一期]`：查看当前 / 未来卡池与 UP 信息；
- `/天井 <ID>` / `/天井列表`：天井状态和兑换；
- `/绑定QQ <QQ号>`：把当前 AstrBot 内部 ID 与数字 QQ 绑定，合并重复玩家数据；
- `/概率`：查看当前权重与保底规则；
- `/奖励 @用户 <点数> [备注]`：管理员发放点数；
- `/规则` / `/帮助`：完整玩法和命令说明。

## 安装

把整个 `astrbot_plugin_ongeki_gacha` 目录放到
`<ASTRBOT_ROOT>\data\plugins\`，然后在 WebUI「插件管理」中加载 / 重载插件。

支持 OneBot（`aiocqhttp`）和 QQ 官方机器人（`qq_official`）。QQ 官方适配器
只提供内部 openid，不使用数字 QQ 识别用户；请先用 `/绑定QQ <QQ号>` 建立关联。

插件安装时会自动安装 `requirements.txt` 中的依赖。首次加载会读取
`assets/card_data` 下的卡牌 JSON 和 PNG；本地开发副本保留了从 ONGEKI
素材同步的完整卡面（约 2.5GB），但发布仓库和插件发布包不附带卡面 PNG。
卡面的来源、获取方式和版权说明见
[CARD_ARTWORK_SOURCES.md](CARD_ARTWORK_SOURCES.md)。

## 配置

配置面板由 `_conf_schema.json` 生成，落盘到
`<ASTRBOT_ROOT>\data\config\astrbot_plugin_ongeki_gacha_config.json`。

| 分组 | 说明 |
| --- | --- |
| 素材路径 | 卡面目录与卡牌 JSON，可改为外部绝对路径 |
| 概率权重 | R/SR/SSR 权重、UP 倍率、轮替模式与间隔 |
| 点数 | 抽卡消耗、签到奖励、连续签到与囤点档位 |
| 月卡 | 价格、有效期、每日加成与半价五连次数 |
| 管理员 | 可使用 `/奖励` 的列表；QQ 官方适配器填内部 ID（openid），也可绑定数字 QQ |

运行数据（SQLite 数据库、抽卡临时图）保存在 AstrBot 为插件分配的
`data/plugin_data/astrbot_plugin_ongeki_gacha/` 目录，不会写入插件目录。

## 卡牌素材

- `assets/card_data/card_info_merged.json`：卡牌元数据；
- `assets/card_data/gacha_pools.json`：官方卡池排表；
- `assets/card_data/ui_card_*.png`：本地高清卡面；
- `assets/ui/`：抽卡结果图使用的字体与 UI 贴图。

卡面 PNG 已被 `.gitignore` 忽略，发布 / 同步仓库时不会携带；本地开发环境
保留完整素材即可。`sync_card_data.py --check` 可校验素材完整性。
如需自行取得和校验卡面，请阅读
[CARD_ARTWORK_SOURCES.md](CARD_ARTWORK_SOURCES.md)。

## 来源与许可

原始项目与 AGPL-3.0 许可：
[DeepSeek-V4-Pro/ongeki_gacha](https://github.com/DeepSeek-V4-Pro/ongeki_gacha)。

详细玩法见 [USAGE.md](USAGE.md)，免责声明见
[DISCLAIMER.md](DISCLAIMER.md)，第三方素材声明见
[NOTICE.md](NOTICE.md)。

卡面获取方式：[CARD_ARTWORK_SOURCES.md](CARD_ARTWORK_SOURCES.md)<br>
素材接入工具：[CARD_ASSET_TOOLS.md](CARD_ASSET_TOOLS.md)
