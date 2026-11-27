# World Rise Iai LS Mod for MHGU

## Overview

This project is a **fork of Akumi v1.1** ([MHW-Long-Sword-Moveset-for-MHGU](https://github.com/Akumi-xu/MHW-Long-Sword-Moveset-for-MHGU)). Its goal is to recreate the **Monster Hunter Rise Long Sword experience** inside **Monster Hunter Generations Ultimate (MHGU) Recomp** by porting Rise-style animations, timing, and weapon handling into the existing Akumi moveset.

This is an experimental, work-in-progress fork. It is not a complete conversion of Rise, is not affiliated with CAPCOM or the original Akumi project, and does not replace the original game assets.

## Relationship to Akumi v1.1

The baseline is Akumi v1.1 (internal v11 optimizations with the v13 blade trail retained). The original v1.1 feature set, controls, and structure are preserved wherever possible. Changes in this fork are kept behind separate build flags so the original baseline build remains reproducible.

## Goal

Bring the Long Sword closer to its Rise counterpart:

- Rise-style Quick Special Sheathe animation and blade direction.
- Smooth transition from the sheath swing into the iai stance.
- Skill-aware behavior: Quick Sheathe skill uses the Rise clip; without the skill, the older World special sheathe clip is used.
- Familiar Rise-like flow for Foresight Slash, iai counters, Spirit Helm Breaker, and camera presentation.

## Current experimental flag

The Rise quick sheathe work is isolated behind:

```sh
ML_WORLD_QUICK_SHEATHE_RISE=1
```

Full experimental build:

```sh
cd 01_plugins/mhw_ls_rebuild
ML_WORLD_COMBAT=1 ML_WORLD_INPUT_VM=1 ML_WORLD_PRESENTATION=1 ML_WORLD_QUICK_SHEATHE_RISE=1 cargo forge build --release
```

A normal build without `ML_WORLD_QUICK_SHEATHE_RISE` keeps the original Akumi v1.1 behavior and hash.

## Installation

1. Build or copy the plugin NRO.
2. Place `mhw_ls_rebuild.nro` under `romfs/nativeNX/plugins/`.
3. Copy the `romfs` folder into the game's `mods/MHW_WORLD_DEV/` directory.
4. Restart the emulator or game after replacing the NRO or ARC files.
5. Use Guild Style Long Sword.

Do not stack this mod with another Long Sword moveset or duplicate plugin build.

## Controls

- `R + A` — Foresight Slash
- `R + B` — Special Sheathe
- `R + X` — Spirit Thrust
- After Special Sheathe: `X` — Small Iai Slash, `R` — Big Iai Slash
- After a successful Spirit Thrust hit — Spirit Helm Breaker

## Credits

- Original project and design: **Akumi-xu**.
- Port and experimental changes in this fork: repository contributors.
- Original game assets and characters belong to **CAPCOM**.

The previous Chinese README content is preserved in the repository history.
