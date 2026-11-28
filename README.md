# World Rise Iai LS Mod for MHGU

## Overview

This project is a **fork of Akumi-xu v1.1** ([MHW-Long-Sword-Moveset-for-MHGU](https://github.com/Akumi-xu/MHW-Long-Sword-Moveset-for-MHGU)). Its goal is to recreate the **Monster Hunter Rise Long Sword experience** inside **Monster Hunter Generations Ultimate (MHGU) Recomp** by porting Rise-style animations, timing, and weapon handling into the existing Akumi-xu moveset.

This is an experimental, work-in-progress fork. It works with **all Hunter Styles** (Guild, Striker, Adept, Aerial, Valor, Alchemy). The ready-to-install bundle is under `Rise-LS-MHGU/`.

## Implemented Features

Bring the Long Sword closer to its Rise counterpart:

- Iai Spirit Slash mechanics follow Rise's rule set.
- Rise-style Quick Special Sheathe animation and blade direction.
- Smooth transition from the sheath swing into the iai stance.
- Skill-aware behavior: Quick Sheathe skill uses the Rise clip; without the skill, the older World special sheathe clip is used.
- Familiar Rise-like flow for Foresight Slash, iai counters, Spirit Helm Breaker, and camera presentation.

## To Do

- Rebalance the damage values of this Long Sword moveset to follow MHGU damage values, since the mechanics already follow Rise.

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

1. Copy the `Rise-LS-MHGU` folder into the game's `mods/` directory.
2. Use Long Sword in any Hunter Style.

Do not stack this mod with another Long Sword Mod or duplicate plugin build.

## Controls

- `ZR + A` — Foresight Slash
- `ZR + B` — Special Sheathe
- `ZR + X` — Spirit Thrust
- After Special Sheathe: `X` — Small Iai Slash, `ZR` — Big Iai Slash
- After a successful Iai Spirit Slash counter: `ZR + B` — Special Sheathe, `ZR + A` — Foresight Slash, `ZR + X` — Spirit Thrust, or `ZR` → `ZR` — Valor Spirit Blade III → Reckoning Slash
- After a successful Spirit Thrust hit — Spirit Helm Breaker

## Credits

- Original project and design: **Akumi-xu**.
- Port and experimental changes in this fork: repository contributors.
- Original game assets and characters belong to **CAPCOM**.

