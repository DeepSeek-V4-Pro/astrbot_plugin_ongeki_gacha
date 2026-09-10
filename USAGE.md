# 使用说明

当前版本：1.2

## 简介

音击抽卡模拟器用于在聊天环境中模拟音击卡牌抽卡、收藏和成长体验，
并附带覆盖音击、舞萌 DX、中二节奏三款音游的随机任务系统。

抽卡结果图底部会按 RinNET 前端样式叠加一条黑色半透明信息条，显示卡牌数字 ID 和完整卡号（例如 `104490 [O.N.G.E.K.I.]1.50-E-0371`）；`/卡图` 发送的是原始高清卡面，不会叠加这条信息。

## 安装

1. 将 `astrbot_plugin_ongeki_gacha` 目录放入 `<ASTRBOT_ROOT>\data\plugins\`。
2. 在 WebUI「插件管理」中加载或重载插件。
3. 插件默认读取自身目录下的 `assets/card_data/`。

如果卡面素材未随插件提供，请先用 `card_asset_tools.py scan` 检查本地素材、
用 `card_asset_tools.py import` 接入，再运行数据同步脚本校验；
也可以在插件配置中指定已有数据的绝对路径。

卡面素材的来源、公开可查询方式和使用权限说明，请阅读
[CARD_ARTWORK_SOURCES.md](CARD_ARTWORK_SOURCES.md)。

## 数据目录

默认数据目录：

```text
assets/card_data/
```

其中包含：

- `card_info_merged.json`：卡牌元数据。
- `card_data_manifest.json`：卡面、卡牌 JSON 与 `gacha_pools.json` 的大小和 SHA-256 校验清单。
- `gacha_pools.json`：官方 CARDMAKER 卡池排表（63 个池，2020-10～2026-07），每个池由“当期版本已有全部 R/SR/SSR 基础卡 + 官方 UP 标记与天井选择名单”组成，每张卡附带 `id / version / cardNumber`、UP/选择标记和非抽卡掉落池。
- `ui_card_*.png`：卡面素材，通常不随代码仓库分发。

可通过配置面板中的「素材路径」修改 `cards_dir` 和 `card_info_json` 为外部绝对路径。
重载插件或触发配置更新后会重新加载卡牌数据、概率、签到、月卡和管理员配置。

## 卡池与轮替

- `[pool] rotation_mode = "cycle"`：按 `rotation_interval_days`（默认 15 天）循环使用 63 个历史官方卡池。
- `[pool] rotation_mode = "official"`：按官方公告日期选池，可能同时启用多个官方卡池；`/卡池` 会列出全部启用池，默认抽取最近开启的池，也可用 `/抽卡 <池ID> <1/5/11>` 指定其他池；若当天没有活动池则使用常驻池（当前版本已有全部 R/SR/SSR）。
- 当前排表收录的是已抓取到的 63 个官方公告池；2023～2026 年存在大量日常池缺失，
  official 模式只能表示“当前排表内”的池，不能保证完整还原官方历史/当前状态。
- 轮替起点会持久化到插件数据库，重启后仍从原位置继续，不会重新回到第 0 期。
- 与原游戏卡牌机的规则一致：活动池不会只有公告列出的新卡/选择卡，而是按活动日期过滤出该版本已存在的全部 R/SR/SSR，再叠加上本期 UP 与天井选择卡；UP 卡按 `pickup_multiplier`（默认 ×10）加权。
- `strict_pool_cards = true`：严格按池子候选卡列表抽取；排表 `cards` 已经包含“当期版本基础卡 + UP/天井选择标记”，不会把未在当期出现的未来版本卡混入。
- 可通过 `/卡池` 查看默认池 / 全部启用池、历史轮替进度、天井信息，并同时发送 SEGA 官方活动图（网络不可用时只显示文字）。
- `/卡池` 会展示各启用池的 UP SSR 角色预览、UP/天井选择数量；`/卡池 列表` 会以图片卡片列出全部 UP SSR。
- 官方公告未标注 UP 的池会显示 `UP 卡：0 张`，但候选仍是当期版本已有全部 R/SR/SSR；天井选择卡只表示可兑换名单，不代表抽卡候选只有这些卡。
- 常驻池包含当前版本已有的全部 R/SR/SSR 基础卡（包括历史活动卡）；可先 `/抽卡 常驻 <1/5/11>` 抽取，`/抽卡` 默认仍是当前轮替活动池。
- `gacha_pools.json` 的 `non_gacha_pool` 卡不会进入任何抽卡池，改为每日签到按概率随机掉落。
- 天井按卡池独立累计：每次抽取一张卡 +1 点；达到 `select_points` 上限后可用 `/天井 <卡ID>` 兑换默认池的可选卡，或用 `/天井池 <池ID> <卡ID>` 指定池兑换，每个池只能兑换一次。
- `/天井列表`（或 `/天井 列表`）可查看全部当前启用池的天井进度与可选卡；池轮换后旧池天井不会带入新池。
- 帮助只保留命令列表；详细规则使用 `/规则` 查看。较长的内容会自动渲染为分页图片卡片，
  图片生成失败时回退为转发消息或纯文本。

排表来源：SEGA 官方 CARDMAKER 公告 + Artemis `static_gachas.csv` / `static_gacha_cards.csv`。

## 随机任务

随机任务从音击、舞萌 DX、中二节奏三款音游的真实曲库中随机生成，任务日期与每日重置
统一使用国际时间 UTC。

- 普通任务：任意难度，默认每天 5 次，完成奖励 20 点。
- 挑战任务：随机选出一张达到 `challenge_min_level`（默认 10 级）门槛的最低真实谱面，
  要求“该谱面或以上，S 及以上”；默认每天 3 次，按审核评级发放 S 30 / SS 40 /
  SSS、SSS+ 50 点。
- 终极任务：从谱面定数 ≥ `ultimate_min_level`（默认 14.7）的超高难谱面中随机，
  要求 SSS+，奖励默认 30000 点；完成后该曲从该用户的终极候选池永久移除，
  由管理员确认后才能接取下一个；同一时间只能有一个未完成或待审核的终极任务。
  这里的 14.7 是谱面内部定数阈值，不是“14 级+”。

相关命令：

```text
/接任务 普通
/接任务 挑战 舞萌
/接任务 终极 中二
/任务列表
/任务完成 <任务ID>          # 需要同时发送成绩照片（可在配置中关闭）
/任务审核 <任务ID> S        # 管理员
/任务审核列表               # 管理员
/终极完成 <用户> <任务ID>    # 管理员
/任务重置 <任务ID>          # 管理员隐藏命令
/任务清理 [天数]            # 管理员立即清理已结束任务
```

- 接取任务时优先发送柔和渐变任务卡；曲绘或任务卡生成失败时自动回退文字模式。
- 曲绘下载优先使用系统 `curl`，失败时回退 Python 下载，带重试和
  `!webp` / `assets2` 多 URL 兜底，并复用本地缓存。
- 普通 / 挑战任务按每日次数限制；未完成与已拒绝任务在每日 00:00（UTC）自动过期，
  已提交待审核任务始终保留。
- 已审核、已过期、已重置的历史任务默认保留 30 天后自动清理（`auto_cleanup_history`、
  `task_history_retention_days`），待审核任务不会被自动清理。
- 管理员审核与重置都会写入 `task_audit` 审计记录，清理历史不会影响审计日志。
- `/任务重置 <任务ID> [备注]` 是管理员隐藏指令，用于处理玩家没有对应游戏等情况，
  重置后用户可重新接取。
- 使用 QQ 官方等以 openid 识别用户的平台时，需要先发送 `/绑定QQ <QQ号>`，
  之后才能接取、查看或提交任务。

## 数据同步与校验

已有本地素材时，运行（默认从插件自身的 `assets/card_data/` 读取并生成校验清单）：

```powershell
python sync_card_data.py --dry-run
python sync_card_data.py
python sync_card_data.py --check
```

素材不在默认位置时，指定来源：

```powershell
python sync_card_data.py `
  --source ./path/to/cards `
  --source-json ./path/to/card_info_merged.json
```

`--check` 会校验卡面文件大小与 SHA-256，并检查 `card_info_merged.json`、
`gacha_pools.json` 哈希、manifest 覆盖和重复项；`--quick` 只检查文件是否存在与清单覆盖。

### 卡面素材接入工具箱

插件同时提供 `card_asset_tools.py`，用于处理用户自己已经取得的本地卡面素材。
脚本不包含抓取、下载、解包或解密功能，也不会修改插件版本号：

```powershell
# 扫描素材目录并检查缺口
python card_asset_tools.py scan --source .\素材目录

# 从角色图层合成近似标准卡面
python card_asset_tools.py compose `
  --source .\角色图层 `
  --layers .\通用图层 `
  --out temp\card_art

# 需要更接近上游排版时，用浏览器版合成（需 Playwright）
python compose_card_art.py `
  --chara-dir .\角色图层 `
  --layers-dir .\通用图层 `
  --out temp\card_art_browser

# 将成品卡面接入插件数据目录
python card_asset_tools.py import --source .\成品卡面

# 校验接入结果
python card_asset_tools.py verify
```

工具支持随机文件名映射（`--mapping`）、分批导入（默认保留已接入卡面）、
独立素材目录（`--dest`）和只检查尺寸/缺失的快速校验。
完整说明见 [CARD_ASSET_TOOLS.md](CARD_ASSET_TOOLS.md)。

## 命令

| 命令 | 说明 |
| --- | --- |
| `/签到` | 每日领取基础点数，并结算连续签到、7 天/15 天周期和月卡加成 |
| `/抽卡 1` | 单抽 |
| `/抽卡 常驻 1` | 从常驻池单抽；也支持 `/抽卡 常驻 5`、`/抽卡 常驻 11` |
| `/抽卡 <池ID> <1/5/11>` | official 模式指定当前启用中的官方卡池抽取（例如 `/抽卡 12296 5`） |
| `/抽卡 5` | 五连，每用户每周首次包含 SR 或以上保底 |
| `/抽卡 11` | 十一连，始终包含 SR 或以上保底 |
| `/点数` | 查看当前点数；点数达到囤点门槛时自动发放对应奖励 |
| `/月卡` | 查看月卡状态；发送 `/月卡 购买` 购买，`/月卡 续费` 续费 |
| `/概率` | 查看当前模拟权重、消耗和保底规则 |
| `/绑定QQ <QQ号>` | 把当前内部 ID 绑定到数字 QQ，合并重复档案 |
| `/卡池` | 查看本期卡池、UP SSR 角色、UP/天井选择数量与轮替进度，并发送官方活动图 |
| `/天井` | 查看当前卡池天井进度；满后可 `/天井 <卡ID>` 兑换选择卡 |
| `/天井池 <池ID> <卡ID>` | 指定启用中的官方卡池兑换天井选择卡 |
| `/天井列表` | 查看全部当前启用池的天井进度与选择卡；也可使用 `/天井 列表` |
| `/接任务 普通/挑战/终极 [游戏]` | 从真实曲库随机领取任务；不指定默认三游戏全随机，游戏可填音击/舞萌/中二 |
| `/任务列表` | 查看今日任务、剩余次数与任务状态 |
| `/任务完成 <任务ID>` | 附带成绩照片提交任务，提交后等待管理员审核 |
| `/任务审核 <任务ID> <评级>` | 管理员审核任务；普通任务用“普通”，挑战任务用 S/SS/SSS/SSS+，或“拒绝” |
| `/任务审核列表` | 管理员查看全部待审核任务 |
| `/终极完成 <用户> <任务ID>` | 管理员确认终极任务完成并发放奖励 |
| `/任务重置 <任务ID>` | 管理员隐藏命令，重置无法游玩的任务 |
| `/任务清理 [天数]` | 管理员立即清理已结束的历史任务；保留天数可省略，待审核任务不会删除 |
| `/规则` | 以分页图片卡片查看完整奖励、抽卡、天井、任务和月卡规则 |
| `/卡册` | 查看收藏进度 |
| `/卡图 <ID>` | 发送已拥有卡牌的高清原图 |
| `/奖励 @用户 <点数> [备注]` | 管理员向指定用户发放点数；也可直接填写 QQ 号 |
| `/帮助` | 显示精简命令列表；详细规则请发送 `/规则` |

所有点数均为模拟货币，不代表真实游戏资源。

## 连续签到与月卡

- 连续签到每天递增奖励：第 2 天起每天额外 +10 点，最高每日额外 +100 点；断签后重新从第 1 天计算。
- 连续签到第 7 天、14 天、21 天等额外获得 500 点。
- 连续签到第 15、30、45 天等同额外获得卡池周期奖励，默认 1000 点；第 15 天刚好对应一次 15 天猫池轮替。
- 每日基础签到默认随机获得 100～250 点，平均约 175 点；连续签到、卡池周期、月卡、管理员发放等奖励在此基础上累加。
- 每日签到有 `non_gacha_checkin_probability`（默认 5%）概率随机获得一张
  `non_gacha_pool` 中的非抽卡卡，并发送对应卡面图；图片生成失败时回退为文字提示。
- 购买月卡消耗 1500 点，有效期 30 天，有效期内每日签到额外获得 100 点。
- 月卡剩余不超过 3 天才能续费，购买后获得两次半价五连（默认 2 次）。
- 点数达到 1000 / 3000 / 10000 时，签到或查看点数会自动领取 100 / 500 / 2000 点囤点奖励；
  默认每个档位领取后每 60 天重置一次，可在 `savings_bonus_reset_days` 调整。
- 以上数值均可在配置中调整：`[economy]` 下的连续签到、卡池周期与囤点项，
  以及 `[monthly_card]` 下的月卡项。
- 日期切换、签到重置、任务重置与周保底统一使用国际时间 UTC，`tz_offset_hours` 仅保留兼容。

这种结构会让每天都能抽 11 连的人减少，但长期签到、囤积点数、购买月卡的人会有更明显的周期收益；攒到 500 点再抽 11 连的性价比也更高。

## 管理员发放

- 在 WebUI 的「管理员」分组中，把管理员 ID 加入 `admin_ids` 列表。
- 管理员可使用 `/奖励 @用户 <点数> [备注]` 或 `/奖励 <QQ号> <点数> [备注]` 为指定用户增加点数。
- QQ 官方平台下发送者 ID 是 QQ 官方 openid；请用 `/绑定QQ <QQ号>` 绑定后，
  再使用数字 QQ 发放或识别，否则数字 QQ 会被视为另一个玩家。
- `allow_local_operator` 默认关闭；需要本地操作用户也可以发放点数时手动开启。
- 每次发放会写入 `admin_grants` 表，方便后续核对。

## 配置项

默认配置由 `_conf_schema.json` 生成，所有数值均可在 WebUI 的插件配置面板中调整。
下面列出与默认值等价的配置内容，仅作对照；运行时不需要 `config.toml`。

```toml
[economy]
cost_1 = 50
cost_5 = 250
cost_11 = 500
min_reward = 100
max_reward = 250
tz_offset_hours = 0
streak_daily_step = 10
streak_daily_max = 100
streak_weekly_reward = 500
streak_cycle_days = 15
streak_cycle_reward = 1000
non_gacha_checkin_probability = 0.05
savings_threshold_1 = 1000
savings_bonus_1 = 100
savings_threshold_2 = 3000
savings_bonus_2 = 500
savings_threshold_3 = 10000
savings_bonus_3 = 2000
savings_bonus_reset_days = 60

[pool]
weight_n = 0
weight_r = 77
weight_sr = 20
weight_sr_plus = 0
weight_ssr = 3
schedule_json = "assets/card_data/gacha_pools.json"
rotation_mode = "cycle"
rotation_interval_days = 15
pickup_multiplier = 10
strict_pool_cards = true

[monthly_card]
price = 1500
duration_days = 30
daily_bonus = 100
renew_max_remaining_days = 3
half_price_5_pull_count = 2

[admin]
admin_ids = []
allow_local_operator = false

[task]
enabled = true
normal_count = 5
challenge_count = 3
challenge_min_level = 10.0
ultimate_min_level = 14.7
normal_reward = 20
challenge_reward_s = 30
challenge_reward_ss = 40
challenge_reward_sss = 50
ultimate_reward = 30000
exclude_special = true
require_photo = true
auto_reset = true
auto_cleanup_history = true
task_history_retention_days = 30
catalog_cache_ttl = 3600
```

## 临时文件清理

抽卡结果临时图片保留 24 小时，插件加载时清理过期文件，运行期间每天自动清理一次。
任务曲绘缓存在插件数据目录的 `runtime/task_covers/` 中复用；任务曲库合并结果缓存在
插件数据目录的 `task_catalog_merged.json`，按 `catalog_cache_ttl` 刷新。

## 故障排查

- 加载失败并提示数据不可用：运行 `card_asset_tools.py scan` 检查素材，
  用 `card_asset_tools.py import` 接入后运行 `sync_card_data.py`；
  也可在配置中填写正确的绝对路径。
- `/卡池` 显示空排表：确认 `assets/card_data/gacha_pools.json` 存在。
  插件发布包随附该排表；如果排表损坏或丢失，请重新获取插件包。
- `/卡池` 显示 `UP 卡：0 张`：官方公告没有提供 UP 名单时属于正常；可发送 `/天井列表` 查看天井选择卡，发送 `/概率` 查看实际稀有度权重。
- 卡图命令提示未拥有：该命令只允许查询当前玩家已获得的卡牌。
- 签到重复提示：同一日期只能签到一次。
- `/接任务` 提示“任务曲库获取失败”：检查机器网络与「随机任务」分组中的曲库地址；
  已有旧缓存时会自动回退到本地 `task_catalog_merged.json`。
- `/任务完成` 提示需要照片：任务配置默认要求随指令一起发送成绩截图；
  若平台不支持图片消息，可在配置中关闭 `require_photo`。
- 任务卡显示文字而非图片：曲绘下载或 Pillow 渲染失败时会自动回退文字模式，
  任务本身仍可正常提交和审核。

更多限制请阅读 [DISCLAIMER.md](DISCLAIMER.md)。
