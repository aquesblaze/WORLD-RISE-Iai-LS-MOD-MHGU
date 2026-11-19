# 公会太刀 · 世界招式移植 v1.0.7

**[下载 PC 成品包](https://github.com/Akumi-xu/MHW-Long-Sword-Moveset-for-MHGU/releases/download/v1.0.7/MHW-LS-MHGU-PC-v1.0.7.zip)** · [下载模拟器包](https://github.com/Akumi-xu/MHW-Long-Sword-Moveset-for-MHGU/releases/download/v1.0.7/MHW-LS-MHGU-Emulator-v1.0.7.zip) · [下载源码包](https://github.com/Akumi-xu/MHW-Long-Sword-Moveset-for-MHGU/releases/download/v1.0.7/MHW-LS-MHGU-Source-v1.0.7.zip)

> **来源与署名**：本仓库是基于 [Akumi-xu/MHW-Long-Sword-Moveset-for-MHGU](https://github.com/Akumi-xu/MHW-Long-Sword-Moveset-for-MHGU) v1.0.7 源码的非官方改版。上游未声明 LICENSE，署名、改动范围与许可说明见 [ATTRIBUTION.md](ATTRIBUTION.md)；本仓库的具体改动见文末「本改版改动」及 `docs/改动说明.md`。

在太刀上加入《怪物猎人：世界／冰原》的看破斩、特殊纳刀、小居合、大居合、气刃突刺和气刃兜割。

**本改版（非官方）**：① 去掉「仅公会风格」限制，六种风格均可用；② ISS 改为 Rise 规则：counter 成功升一级且不清空练气槽，失败不掉级，成功后可回特殊纳刀，只有成功后才能接看破斩；③ 特殊纳刀 stance 就位后才允许 B 方向回避；④ 居合无敌帧改用与另一版相同的判定：源 `common` bit26 窗口，末尾少 2 帧（不再额外延后）；⑤ ISS 成功后单按 ZR / 单按 B 有 10 帧合流窗口（单按 ZR 还会从 ZR 自己的按下帧起算）：先按 ZR 再补 B 仍判定为 ZR+B 特殊纳刀，不会被抢成 Spirit III；登龙落地单按 ZR 同样有 10 帧合流窗口，晚到的 B/A 仍进特殊纳刀/看破斩。详见文末「本改版改动」。PC 主要验证环境为 MHGURecomp 0.16.0；模拟器对应 GU 国际版 v1.4.0、0100770008DD8000 和现有 Forge 加载器。

## v1.0.7 更新（含 v1.0.6 修复）

- 修复转向时 ZR+B 被侧滚抢先执行：有效窗口内同时按 ZR+B 或先 ZR 后 B，优先特殊纳刀。单按 B 仍正常回避；已经由先按 B 启动的回避不会追溯改成纳刀。
- 补齐公会原生空中气刃落地接特殊纳刀，无刃/白/黄/红及满/空练气槽已做按键验证；临近落地可预输入 ZR+B。
- 修正气刃突刺挂点，三层刀光逐帧跟随刀刃、碎光在刀尖附近发出；把加色贴图的黑底转换为透明度，去除黑线、黑边及偏位光斑。
- 兜割命中音在首次实际延迟命中时播放，落地接特殊纳刀后仍可发声；复测七次实际扣血。
- 删除大居合第一段额外命中闪光；第二段刀线最后40帧平滑淡出，总寿命保持110帧，三种开刃色分别验证。
- 新增气刃兜割落地接 **Sakura Slash I**：落地后松开再新按 **ZR** 直接请求原生狩技动作 51（flags `0x40`），不需要装备 Sakura Slash，也不要求狩技槽；一直按住下劈的 ZR 不会误触发。单按 ZR 落地后还会等 `W_LAND_CHORD_GRACE`（10 帧）才发动，给晚到的 B/A 留出合流时间：ZR+B 仍进特殊纳刀、ZR+A 仍接看破斩，不会被抢成 Sakura；B/A 先按住、ZR 后按同样成立。使用时改为**扣 1 级练气等级**（原版狩技会升 1 级），插件会取消原生的升级，并在**招式发动那一瞬间**扣级（不再等动画播完）。按《世界》的节奏，这一招**只有黄色练气等级能发动**：红刃兜割落地扣到黄后可以接，出招后立刻降到白；黄刃及以下兜割落地后等级已是白/无，按 ZR 会被拒绝且不扣级。
- 保留普通攻击基础练气 **1.1 倍**、普通突刺/上挑派生修复、登龙异常下落恢复及 v1.0.5 的指定插件入口兼容。

本轮没有继续扩展折射、光照或粒子移植，也没有新增PC渲染模块。错误的突刺折射代理层已停用，画面仍非《世界》完全还原。

## 安装与操作

**不要同时安装其他太刀动作、派生或连招修改 MOD。** 升级前关闭游戏，把旧版公会太刀移出 MOD 目录，再安装新版。使用太刀（本改版任意风格均可）。本版没有独立参数菜单。

PC：解压 PC 成品包，将 `romfs` 放到游戏目录的 `mods/MHW_WORLD_DEV/` 下，确认 `mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro` 存在。

Eden：解压模拟器包，将 `romfs` 放到 `load/0100770008DD8000/MHW_WORLD_DEV/` 下。需要已安装的 Forge 加载器，本包不附带或覆盖加载器。

GU 按键：攻击中 **ZR+A** 看破斩、**ZR+B** 特殊纳刀、**ZR+X** 气刃突刺；特殊纳刀后 X 小居合、**ZR** 大居合；开刃突刺命中可接气刃兜割。气刃兜割落地后先松开 ZR，再新按 **ZR** 可直接接 **Sakura Slash I**：这是原生狩技动作，不需要把 Sakura Slash 装在狩技槽，也不要求狩技槽充满；落地时一直按住下劈那一下的 ZR 不会误触发。单按 ZR 落地后会先等 10 帧确认没有 B/A 伙伴键：这期间按 B 仍进特殊纳刀（ZR+B）、按 A 仍接看破斩（ZR+A），不会被抢成 Sakura；伙伴键先按住、ZR 后按也一样。这一招使用时**扣 1 级练气等级**，而不是原版的升 1 级；插件会在招式发动那一瞬间（动作链开始的那一帧）取消原生升级并扣级，不等动画结束。并且**只有黄色练气等级能发动**（与《世界》一致）：红刃兜割落地扣到黄，接 Sakura 后立刻到白；黄刃兜割落地已变白，按 ZR 不会出招。注意兜割落地本身原有的扣级规则不变（落地后 0.5 秒结算），所以这套派生要从红刃起手，整套总共扣 2 级（兜割 1 级 + Sakura 1 级）。这里的 ZR 是 Switch 右扳机（内部符号 `ML_R`），不是 GU 原生 R 肩键。特殊纳刀要等源 306 进入 phase1（F73，收刀根位移结束、stance 真正就位）后才允许按 B 摇杆方向回避，早按不会截断收刀动画。大居合（ISS）按 Rise 规则：counter 成功升一级且不清空练气槽；失败不掉级；成功后 **ZR+B** 可回特殊纳刀，也可直接单按 B 回避；成功后才能 **ZR+A** 接看破斩，ISS 成功后单按 **ZR** 出气刃斩 III，再按一次 **ZR** 接气刃大回旋斩（需练气≥25）。ISS 的四种派生统一延后到 F70 才发动，早按会缓冲，动画不会被切断；B 回避不必先 ZR+B 回纳刀再等 stance 就位。收刀术使特殊纳刀起手加速为1.45倍；小居合及兜割命中后保留各自练气回复。

卸载：关闭游戏，移除 `MHW_WORLD_DEV` 文件夹。

## PC 插件兼容性

以下为 v1.0.5 对用户提供版本的联测结果；v1.0.6～v1.0.7 保留对应入口兼容实现，本轮未重跑所有第三方MOD组合。第三方 MOD 不包含在本包中，不代表任意同名或后续版本均兼容。

| MOD | MHGURecomp 0.16.0 检查结果 |
| --- | --- |
| FF14 显伤 v011（20261025） | 字体、飘字、登龙七段实际扣血和练气1.1倍检查通过；未给世界移植动作补专用招式名 |
| 崛起风格会心显伤及动画优化包 | 派生、登龙恢复、七段实际扣血、小居合回气通过；中文字体加载正常 |
| 崛起喝药 v1.3 | 实际消耗回复药、恢复体力且喝药时可以移动；与太刀派生和落地共存 |
| 伪翔虫受身闪避插件包 | 太刀入口冲突已修复；原受身插件自身拒绝PC玩家地址，受身功能尚不能在PC版使用 |
| 道具轮盘 v2.0（WCore版） | 依赖 WCore 专用加载器与接口，当前PC Forge不能直接加载 |

两款显伤可共同运行，实测没有翻倍扣血，但会重叠绘制数字，建议二选一。旧盾斧变4G动作插件仍有PC运行时不支持的ARM指令补丁，不能视作完整移植。详细结果见[兼容性说明](兼容性说明.txt)。

## 验证与已知限制

v1.0.7 在 PC 副本存档完成20项真实按键回归：四方向同时ZR+B、先ZR后B、B单按、B先按，看破后左右转向纳刀，以及无方向纳刀和前滚。v1.0.6另验证空中气刃纳刀、突刺画面、四刃色大居合画面、真实反击、兜割七段扣血、系统输出中的两路命中音和清零速度/重力后的下落恢复。编译、入口保护回归及NRO重定位检查通过。

**怪物身体附近极低概率的自然悬浮仍未复现**；故障注入通过只能证明已知清零停滞状态可以恢复。Eden此前做过基础检查，v1.0.6和v1.0.7未重新实战；与PC共用同一份NRO并通过重定位检查。未覆盖所有装备、地图、坡面和第三方插件版本，也未做实机战斗验收。

## 编译插件

源码包在纯 ASCII 路径展开，保留目录结构；需要项目指定的 Rust 工具链、ARM 编译器和 cargo-forge。先按本机位置调整 `build.rs` 与 `.cargo/config.toml` 中的编译器/链接器路径，再在 PowerShell 执行：

```powershell
cd 01_plugins/mhw_ls_rebuild
$env:ML_WORLD_COMBAT="1"
$env:ML_WORLD_INPUT_VM="1"
$env:ML_WORLD_PRESENTATION="1"
cargo forge build --release
```

源码包包含编译所需的生成头文件、C/Rust源码及测试，不包含游戏转储、存档、密钥、第三方插件、缓存日志或暂停开发的特效候选。资源转换脚本仍需自行提供游戏数据；安装成品无需重新生成资源。

## 其他实用 MOD

[怪物显隐、无边缘传送、斩味条 HUD](utility_mods/)：五个安装包、三个完整 Rust 工程，以及构建、打包和安装说明。斩味条提供主机、掌机、可调整三个版本。

## 手柄震动

- 居合 GP 成功（大居合反击）→ 0.9 强度，约 0.15 秒；
- 登龙首次命中 → 0.8 强度，约 0.13 秒；
- 走游戏自身 HID（sdk `SendVibrationValues`），不需要额外插件；
- 实现细节见 `docs/震动说明.md`。

## 本改版改动（相对官方 v1.0.7 源码）

1. **去掉公会限定**：`c/gu_adapter.c` 的 `local_guild()` 改为 `local_ls()`，接受原生风格编号 0..5
   （公会/强袭/空战/武士道/勇气/炼金），越界值仍然关闭控制器；17 处调用点同步改名。
   世界招式本身走私有动作 240..250 + 追加动作库，与风格无关。
2. **Rise 化的居合派生**：`c/world_command_driver.inc` 不再让小居合/大居合任意帧 ZR+B 循环回特殊纳刀
   （旧的 `world_sheathe_chord()` / `WORLD_IAI_SHEATHE_GRACE` / `sheathe_latch` 已移除）。
   当前规则：
   - 普通地面招式仍按源 TIML 窗口用 ZR+B 进特殊纳刀；
   - 大居合（ISS）counter 成功后，ZR+B 可直接回特殊纳刀（成功的专属派生）；
   - 大居合成功后，ZR+A 才能接看破斩（whiff 不可）；
   - 特殊纳刀里的「大居合」需要一次新的 ZR 按下（`fresh=b->held&~s->consumed`）。
   判定图节点 64/65 没有指向节点 61 的边，公共转移也被 `node!=0&&node!=64&&node!=65` 排除，
   所以这两条 ISS 派生由命令层直接处理。
3. **居合无敌帧判定（与另一版一致）**：`c/world_adapter.inc` 的 `world_damage()` 里，
   判定仍是"当前 TIML 事件的 `common` bit26"，但把这段连续 bit26 事件窗口的**最后两帧**排除：
   命中时沿同一 source 往后走到窗口最后一个事件得到 `last`，只在 `f <= last - 2` 时无敌。
   窗口：小居合 ~5→3 帧；大居合（308）约 12→10 帧；大居合（309-311）约 14→12 帧。
   原先"+2 帧延后"的 `WORLD_IAI_INVULN_EXTEND` 机制已移除。
4. `build.rs` 支持 `ARM_NONE_EABI_GCC` 环境变量；安装日志
   `installed; all styles; iai roll; sheath x1.45; iframe-2; native collision retained; rumble; chord-grace; lens-off`。
5. **Iai stance 的 B 回避只在 stance 就位后开放**：`c/world_command_driver.inc` 的 `W_SHEATHE` 分支用
   `fresh=b->held&~s->consumed` 排除进纳刀那一下 B，并要求 `event->phase==1`（源 306 从 F73 起）。
   早于 F73 按 B 不缓冲、不打断收刀根位移；就位后新按 B 才发 `W_ROLL`。
   源 306 没有 roll 权限位，所以不能等 `WI_ROLL` 窗口；heading 取
   `magnitude>=50?input_heading:heading`，回避方向跟随摇杆，摇杆回中则保持当前朝向。
6. **ISS 改为 Rise 规则**：`c/world_core.c` 里 counter 成功（`o->counter`）发 `rank_delta=1`，
   whiff 不再发 `rank_delta=-1`；`world_adapter.inc` 删除了每帧监控 `actor+0x3330` 上升就清
   `0x2780` 的逻辑，连段大回旋开刃也不再 `gauge_clear/gauge_hold`，所以升级不清空练气槽。
   `world_command_driver.inc` 为 `W_BIG` 增加原始按键派生：counter 成功后 ZR+B 可回 `W_SHEATHE`，
   或直接单按 B roll；counter 成功后 ZR+A 可接 `W_FORESIGHT`（whiff 不可）；成功后单按 ZR 出气刃斩 III。
   四种派生统一延后到 F70 起才发动，早按都会锁存，以免切断 ISS 回收动画又丢输入。ZR+B 与单按 B 另加 2 帧 debounce，
   ZR/B 状态必须连续 2 帧稳定才认，避免边界帧误判；whiff 时 B 不会 roll，不能回纳刀，也不能接看破斩。
   单按 ZR / 单按 B 还会在 F70 后再等 `W_ISS_CHORD_GRACE`（10 帧）才兑现，给稍晚按下的伙伴键留出合流时间；
   ZR 这一下还会从它自己的按下帧重新计算这段宽限，所以即使 ZR 在 F70 之后才按，也能等满整个窗口：
   ZR 先按、B 晚到仍判定为 ZR+B（特殊纳刀），不会抢成 Spirit III；B 先按、ZR 晚到同理。
   伙伴键先按住、ZR 后按也按 ZR+B / ZR+A 处理。ZR+B / ZR+A 一旦成立立即发动，不再等这 10 帧。
7. **收刀术加速改回 1.45**：`c/world_adapter.inc` 的 `world_motion_speed()` 保留四个 GU 速纳技能 ID，
   把原本 World 衰减后的 `1.16f` 改为 `1.45f`，只作用于特殊纳刀起手段。
8. **ISS 成功后 ZR 收尾连段**：`c/world_command_driver.inc` 在 `W_BIG` 分支里锁存一次新的单按 ZR
   （`follow_ready`），到 F70 且 counter 成功时才兑现 → `ground_enter(s,o,36,ML_R)`。这样即使玩家在
   counter 发生的 F12～F14 立刻按 ZR、到 F70 前已松开，也不会丢输入；同时给 ISS 回收动画留出
   F20→F70 的间隔，不被派生切断。节点 36 是源生成的 Spirit III
   辅助节点，会保留 `124 → 108`（F9）的起手段，落到节点 2（气刃斩 III，扣 20 练气）。之后不再有自定义
   桥接：节点 2 自己的 ZR 边在源 108 的 F110 execute 窗口触发，练气≥25 时走正常路由发原生动作 30
   （气刃大回旋斩）。单按 ZR 在 F70 后还要再等 `W_ISS_CHORD_GRACE`（10 帧）确认没有 B/A 伙伴键，
   避免 ZR+B 的 ZR 先到就被判成 Spirit III；这段宽限也会从 ZR 自己的按下帧重新起算，
   所以 F70 之后才按的 ZR 同样能等到晚到的 B/A。单按 B 同样等 10 帧，让 B 先按时能被晚到的 ZR 合流成 ZR+B。
   伙伴键先按住、ZR 后按也能合流。whiff、ZR+B/ZR+A、一直按住的 ZR 以及练气不足 20/25 都不会误触发。
9. **气刃大回旋的原生镜头推拉已彻底关闭**：GU 的气刃大回旋（原生 motion `0x57F`，source 109）
   自带一段约 104 帧的镜头 work：FOV 50° → F19 44.8° → F33 65.5° → F104 50°。
   GU 在换动作时会以当前 FOV 为起点重播这段 work，所以它既会在世界招式里重播，也会在每次
   换动作时留下跳变。现在 `c/world_camera.inc` 在**整个气刃动作（action `0x1E`，包含 `0x57F`）**、
   **所有世界私有动作**以及**最后一个之后 110 帧**里，把镜头 FOV（`camera+0x3c`）直接钉在静止 FOV
   （默认 50°）。这样连大回旋本身的推拉也不会再出现，换动作时也没有跳变。
   静止值只从真正平坦的镜头上学习（单帧变化 <0.02° 且持续 12 帧），work 即使到 65.5° 峰值附近
   每帧仍变化约 0.04°，不会被误采；钉住是瞬间切换，不做缓动（缓动本身就是可见的缩放）。
   过场动画、非长刀角色和窗口结束后的正常镜头不受影响，near/far/aspect 从未被插件写入。
   验证：日志里 `world_lens` 每个动作只剩 1 行且约 50°，新增的 `world_lens_leak` 应为 0。

编译（本机实测组合）：

```powershell
rustup toolchain install nightly --component rust-src   # nightly-x86_64-pc-windows-gnu
cargo install cargo-mhgu-forge                          # 1.5.0
cd 01_plugins/mhw_ls_rebuild
$env:ML_WORLD_COMBAT="1"; $env:ML_WORLD_INPUT_VM="1"; $env:ML_WORLD_PRESENTATION="1"
$env:ARM_NONE_EABI_GCC="<arm-none-eabi-gcc.exe>"
$env:CARGO_TARGET_ARMV7A_NONE_EABI_LINKER=$env:ARM_NONE_EABI_GCC
cargo forge build --release
```

产物 `mhw_ls_rebuild.nro` 487424 字节，SHA256 `8e3dbee6513e81e0f1d4f9eaa2ad59b21534117e8560849d309e200556b88ad2`，段大小（.text 0x16a20 / .rodata 0x5e3d0 / .data 0x91c / .bss 0xc000）
与官方 v1.0.7 一致。
