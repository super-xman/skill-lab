# 从原图到交付文件

命令从任意工作目录执行。使用本技能所在目录定位脚本和网页模板。示例中的原图路径、镜头、标题和视角按当前作品填写。Python 3.11+，依赖为 NumPy、OpenCV 和 Pillow。

```bash
pano_skill="${CODEX_HOME:-$HOME/.codex}/skills/image-to-8k-panorama"
pano_job="$PWD/pano-work"
pano_source="/path/to/original.png"
python3 -m venv "$PWD/.pano-venv"
pano_py="$PWD/.pano-venv/bin/python"
"$pano_py" -m pip install -r "$pano_skill/scripts/requirements.txt"
"$pano_py" "$pano_skill/scripts/panorama.py" init "$pano_source" "$pano_job" \
  --projection perspective --hfov 74 --horizon 0.51
```

已有满足依赖的解释器可直接用于后续命令。普通相机可用 35mm 等效焦距作为视场估计的起点。地平线比例按图像完成 EXIF 旋转后的高度测量。宽幅绘画适用时选 `--projection cylindrical`。检查 `layout.png` 中的位置和尺度，然后用编辑模型补绘 2∶1 的 `base.png`，保存到工作目录。若回图比例偏离 2∶1，按引导图重新取景或重新生成。

## 镜头与合成

`scene.json` 里的 `original` 记录输入的投影。`panels` 数组按先后叠加，角度单位为度。yaw=0 向原图中央看，正值向右，±180 在背后；pitch=90 向上，−90 向下。hfov 是水平视场，宽和高决定垂直视场。相邻视角保留共用地标和足够的边缘羽化余量。例如可在已有广角层后增加一个细节镜头。

```json
{"id":"facade","yaw":78,"pitch":-4,"hfov":66,"width":1600,"height":1200}
```

```bash
"$pano_py" "$pano_skill/scripts/panorama.py" guides "$pano_job"
```

检查 `scaffold.png` 中原图边缘的结构和色温。每个 `panels/<id>/guide.png` 都是独立的透视编辑目标。将对应的生成回图存为同目录的 `paint.png`，保留原生尺寸和引导图的宽高比。低特征天空、水面可能无法测出可靠的特征匹配；用云缘、浪线和视角中心复核。回图改变取景或出现大幅位移时，按原引导图重新补绘。只修一个位置时可追加新 ID，复用已有且相机相同的补画。

```bash
"$pano_py" "$pano_skill/scripts/panorama.py" assemble "$pano_job" --width 2048 --out "$pano_job/draft.png"
"$pano_py" "$pano_skill/scripts/panorama.py" assemble "$pano_job"
"$pano_py" "$pano_skill/scripts/panorama.py" view "$pano_job/scaffold.png" "$pano_job/before.png" \
  --yaw 78 --pitch -4 --hfov 72 --width 1600 --height 1000
"$pano_py" "$pano_skill/scripts/panorama.py" view "$pano_job/master.png" "$pano_job/after.png" \
  --yaw 78 --pitch -4 --hfov 72 --width 1600 --height 1000
"$pano_py" "$pano_skill/scripts/export.py" "$pano_job/master.png" "$pano_job/image-release"
```

交付的 `panorama.jpg` 在导出目录中，`master.png` 为无损母版。导出器会回读 JPEG 的像素尺寸和 GPano XMP。覆盖图按 8K 估算，蓝色阈值约为目标密度的八成，绿色单独标示保留的原图。原图自身分辨率不足时，优先忠实保留用户指定的主体，并说明可放大的程度。

背面接缝有明显的地形错位时，可先单独生成跨缝镜头并合成。随后在新工作目录沿用原图、投影和地平线，把这轮无损母版作为新的 `base.png`，按已修好的背面取景，再补周边近景。覆盖图中的底图色表示本轮继承的内容；结合上一轮底图的真实细节判断清晰度。

## 手机网页

```bash
"$pano_py" "$pano_skill/scripts/export.py" "$pano_job/master.png" "$pano_job/web-release" --web --title "海港全景"
"$pano_py" -m http.server 8000 --bind 127.0.0.1 --directory "$pano_job/web-release"
```

查看器自带 Pannellum 和许可证。8K 配置使用六个 4096 像素的立方体面、512 像素切片、四级清晰度，共 510 张分级切片和 6 张回退图。网页按当前视角请求所需部分。支持 `?yaw=78&pitch=-4&hfov=72` 直达同一机位。

部署时只上传 `web-release/` 的内容。按本次授权的访问范围发布到用户指定的平台，未指定平台时可用当前可用的 Sites 或其他静态托管。改已有站点时复用原项目和网址。拿到链接即可查看的作品，用无登录会话打开实际的 HTTPS 网址，检查切片响应和触控，再把该网址交给用户。注明触控验证使用真机还是模拟器。

判断某个视角模糊时，在足以触发最高级切片的窗口和缩放下，对照相同相机、同像素尺寸的母版渲染。
