# 重建八个既有角色

以下命令从发行目录根部运行，使用本机 Blender 5.2 系列及其内置的 Python、Cycles 和 glTF 导出器。角色建模与渲染所需的几何、材质、摄影机和灯光均在本目录的 Python 文件中。[源码入口](create_cast.py)

### 重建与核验

```sh
blender -b --offline-mode --factory-startup --python-exit-code 1 -P model-source/create_cast.py
blender -b --offline-mode --factory-startup --python-exit-code 1 -P model-source/validate_cast.py
```

第一条命令在 `model-source/build/` 生成可编辑的 `cast.blend`。同目录的 `models/` 包含八个 GLB、八张 800 × 920 全身 PNG、两张 640 × 640 教师头像，以及岗位角色的正面和教师助理的转面校样。应用使用的六张二维 WebP 来自既有 AI 头像，可直接取用发行包内的文件。[原二维头像](../avatars/)

第二条命令重新打开生成的场景和八个 GLB。它比对网格顶点、角色朝向、鞋底到台座的距离和图像透明边界，并检查六个岗位角色的手、道具及衣身接合。结果写入 `model-source/build/rebuilt-check.json`。[核验脚本](validate_cast.py)

在 Blender 5.2.2 LTS 实测中，发行版和重建版的八个 GLB 都通过了上述核验，八张全身图和两张教师头像分别与发行版逐像素一致。重新导出的八个 GLB 与发行版的文件字节有差异。校验原始发行文件可使用其哈希，校验自行重建的模型可使用上述几何检查。

若只需制作封面或检查**发行包已有的 GLB 与 PNG**，可跳过全套逐人渲染，运行以下两条命令。第一条只生成可编辑场景，第二条读取发行目录的 `models/`，结果写入 `model-source/build/published-check.json`。

```sh
blender -b --offline-mode --factory-startup --python-exit-code 1 -P model-source/create_cast.py -- --scene-only
blender -b --offline-mode --factory-startup --python-exit-code 1 -P model-source/validate_cast.py -- --published
```

### 重新排版两张对照板（可选）

排版用 Python 3、Pillow 和两款 Noto SC 字体。将环境变量 `NOTO_SC_DIR` 设为本机同时包含 `NotoSansSC-Regular.ttf` 与 `NotoSerifSC-Bold.ttf` 的目录，然后运行下列命令。脚本读取发行包中的原头像、两版校样和投影坐标，在 `model-source/build/models/` 写出六角色对照板和教师助理转面板。追加 `--check` 可在内存重排后与发行版两张图逐像素比对；此项比对依赖制作时的字体与栅格化环境。[排版脚本](review_portraits.py) · [两版校样及坐标](../models/校样/)

```sh
python3 model-source/review_portraits.py --font-dir "$NOTO_SC_DIR"
```

封面使用同一个重建场景。制作书页、静帧与短片的命令见[封面重建说明](../cover/source/README.md)。代码和成品各自的许可范围见[素材来源说明](../ASSETS.md)。
