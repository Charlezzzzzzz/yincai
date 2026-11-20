# 重建协作圆桌

`build.py` 读取仓库中六个独立角色的 GLB，去除各自的展示底座，构建桌面、凹槽、书写垫、支架、铅笔和教案簿。最终六席位置、各部件变换和正交相机保存在 `layout.json`。制作流程使用 Blender 5.2.2 LTS。正常运行教师工作台只需安装项目根目录的 Python 依赖。

从仓库根目录执行。核验脚本需在本机 Python 环境中提供 NumPy、OpenCV 与 Numba；开发机实测版本分别为 2.2.6、4.11.0 与 0.68.0。

```sh
output_dir="$PWD/build/roundtable"
mkdir -p "$output_dir"
blender --background --factory-startup --python-exit-code 1 -P roundtable/source/build.py -- "$output_dir"
python3 roundtable/source/measure.py "$output_dir"
blender --background --factory-startup --python-exit-code 1 -P roundtable/source/render.py -- "$output_dir"
```

- `assembly.glb` 包含六席人物与 21 个家具、教案及文具部件。发行版 SHA-256 为 `fc0594ecedb7b62af07fb739450979d294ce706b2121e86be7a2a367b00951c2`。
- `camera.json` 保存相机、六个人物和书页的归一化轮廓。定镜与点击区域同用 1720 × 790 的画幅。
- `visibility-audit.json` 报告默认相机下的逐席遮挡、脸部及手持物可见像素和桌腿、铅笔及教案的支承间距。脚本校验被遮挡的脸部及手持细节像素为零，并检查桌体各接合面的误差小于 0.00001 米。
- `hero.png` 是从输出 GLB 重新载入、布光并渲染的桌面定镜。重建图像的像素可随 Blender 和渲染设备而异。

随仓库提供的三张纹理已可用于重建。若需重排书页，请将 `NotoSansSC-Regular.ttf` 及 `NotoSerifSC-Bold.ttf` 放在自备的字体目录中，执行 `python3 roundtable/source/texture.py 字体目录`。此命令使用 NumPy 和 Pillow，更新本目录内的两张书页 PNG 与木纹 JPEG。素材与字体使用范围见[素材说明](../../ASSETS.md)。
