# 重建工作簿封面

封面使用六个岗位角色、两张随附书页和脚本生成的工作簿、铅笔、摄影机与灯光。两张书页 PNG 可直接作为纹理，常规渲染无需安装中文字体。[左页](page-0.png) · [右页](page-1.png) · [场景脚本](build_studio.py)

以下命令从发行目录根部运行。渲染使用 Blender 5.2 系列和 Cycles，静帧合成使用 Python 3 与支持 WebP 的 Pillow；短片编码另需 `ffmpeg` 在命令搜索路径中可用并支持 `libx264`。

### 静态封面

```sh
blender -b --offline-mode --factory-startup --python-exit-code 1 -P model-source/create_cast.py -- --scene-only
blender -b --offline-mode --factory-startup --python-exit-code 1 -P cover/source/build_studio.py
python3 cover/source/export.py
```

第一条命令从随附的 Python 源码生成 `model-source/build/cast.blend`。已完成角色重建时可从第二条继续。场景脚本读取六个岗位集合和本目录两张书页，每次都会核对十二只鞋底与工作簿封面的接触距离，并检查六个角色的面部中心是否在镜头内。静帧先写为 `cover/source/build/hero.png`，合成后得到同目录的 `studio.webp`（1344 × 944）。[角色重建说明](../../model-source/README.md) · [合成脚本](export.py)

### 入场短片

首次运行时，先完成上面的角色场景生成步骤。

```sh
blender -b --offline-mode --factory-startup --python-exit-code 1 -P cover/source/build_studio.py -- motion
python3 cover/source/export.py movie
```

脚本将 19 帧镜头运动渲染至 `cover/source/build/`，再合成该目录的 `enter.mp4`（982 × 690，24 帧/秒，H.264，无声）。仅核验场景可使用以下命令。

```sh
blender -b --offline-mode --factory-startup --python-exit-code 1 -P cover/source/build_studio.py -- audit
```

### 修改书页文字（可选）

在[书页排版脚本](paper.py)中编辑标题和栏目文字。将环境变量 `NOTO_SC_DIR` 设为本机同时包含 `NotoSansSC-Regular.ttf` 与 `NotoSerifSC-Bold.ttf` 的目录。以下命令会重写本目录两张 1024 × 1220 书页 PNG。再次渲染即可将新文字排入封面。

```sh
python3 cover/source/paper.py --font-dir "$NOTO_SC_DIR"
```

发行包附有两款字体的许可文本。书页、封面与短片的使用范围见[素材来源说明](../../ASSETS.md)。[Noto Sans SC 许可](../../third-party-notices/NotoSansSC-LICENSE.txt) · [Noto Serif SC 许可](../../third-party-notices/NotoSerifSC-LICENSE.txt)
