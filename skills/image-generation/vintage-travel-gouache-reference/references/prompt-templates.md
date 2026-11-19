# Prompt 模板与验收规则

## 模板 A：风格迁移＋适度扩展（中文，默认首选）

请将【目标图】转换为「复古旅行海报厚涂风」。

输入角色：
- 【风格参考图】：本 Skill 的 `assets/style-reference.webp`。只参考**绘画技法、色彩关系、光照处理和哑光颗粒**，不复制具体对象。
- 【目标图】：用户提供的目标图。以它为内容与构图的唯一依据。

保留【目标图】的核心主体、人物可见特征、重要服饰道具、关键表情姿态、主要建筑/场景关系及画面叙事；明确要求保留的颜色、文字或 Logo 必须准确保留。**允许适度扩展图片内容**：顺着现有空间逻辑补齐画面边缘，丰富天空、植被、地形、街道或室内陈设等环境细节，加入少量符合场景逻辑的远景/点缀物，并在不改变主体身份和动作的前提下适度优化取景、景深和构图留白。所有新增内容必须自然、克制、不抢主体、不产生新的关键情节。

风格：20 世纪中期欧美复古旅行海报（Mid-century Vintage Travel Poster）＋不透明水粉（Opaque Gouache）＋轻度油画厚涂（Painterly Impasto）。使用精致但可见的手绘短笔触、层叠的哑光色块、细腻画布/纸张颗粒与略带装饰性的造型概括。阴影带有柔和冷色层次；亮部使用温润暖光。色彩借鉴灰蓝、海青、暖金、奶油橙与赤陶色的和谐关系，但不得覆盖目标图固有色、指定主题色或时间氛围。形体准确，光影丰富，避免照片写实。

**不要照搬**风格参考图里的邮轮、灯塔、帆船、巨大太阳、海湾、棕榈树、海岸建筑或浪花及其具体布局；只有它们本身自然适合目标场景时，才可独立设计同类元素。默认不增加重要人物、标志性新地标、故事转折、标题、标语、Logo 或水印。

画幅：【沿用目标图比例／用户指定比例】。
内容扩展等级：【默认 1｜适度扩展；要求原样保留则改为 0｜严格复刻；明确鼓励创作则改为 2｜较自由扩展】。
其他硬性要求：【填写人物特征、指定配色、裁切需求、不可改变元素】。

负面约束：photorealistic, 3D render, glossy CGI, plastic skin, smooth airbrush gradients, anime cel shading, flat vector illustration, transparent watercolor bleeding, excessive impasto, heavy grunge, harsh neon colors, oversharpening, unwanted text, watermark, copied reference-scene objects, intrusive additions, subject drift, new main characters.

## 模板 B：同系列原创插画（中文）

请原创绘制【主体/场景设定】，画幅为【比例】，用途为【头像/壁纸/旅行插画/海报】。采用本 Skill《海边度假》风格参考图的视觉语言，而非其场景内容：复古欧美旅行海报、不透明水粉、轻微油画厚涂、明显但细腻的笔触、哑光颜料层叠、温柔的冷暖光照、低强度纸张颗粒。人物/物体结构准确、主题突出、背景层次清晰，配色复古而不暗淡。

严格遵循：【主体的历史/生物/地点信息、人物姿态、指定物体、指定主色和禁止元素】。可适度创造能强化氛围的配景、装饰性自然元素与空间细节，但不能取代主体或自创无依据的重要故事情节。不要照搬参考图中的邮轮、灯塔、落日、海岸房屋或特定构图。无文字要求时不添加文字、水印。

## 模板 C：English (for image models)

Use the attached style reference image strictly as a **style reference**, not as a source of scene content. Transform the separate target image while preserving its **main subject identity, defining features, key pose, signature wardrobe/props, and essential scene relationships**. Moderate, scene-consistent expansion is allowed: extend the surroundings, fill in out-of-frame background, add a few subordinate environmental details, and subtly improve framing or depth while keeping the main subject dominant. Do not invent major characters, landmarks, or new plot points.

Visual style: an elegant mid-century vintage European travel poster illustration, painted in **opaque gouache** with subtle **painterly impasto**. Refined but clearly visible hand-painted strokes, layered matte pigments, sculpted shapes, softly textured paper/canvas grain, warm golden highlights, nuanced cool blue-teal shadows, and harmonized vintage color relationships. Detailed yet artistically simplified shapes; luminous, romantic atmosphere without looking photographic.

Do NOT copy any specific ship, lighthouse, oversized sun, sailboat, waterfront town, or architecture from the style reference; a similar *type* of element may be independently added only if it naturally fits the target scene and remains secondary. Preserve the target's color-critical details, essential time-of-day/weather context, and requested aspect ratio. No new important characters, invented titles, labels, logos, or watermarks.

Avoid photorealism, glossy CGI, 3D rendering, flat vectors, anime cel-shading, translucent watercolor wash, plastic materials, smooth AI airbrushing, oversaturated neon, excessively rough oil paint, and copied reference-scene motifs.

## 可插入的扩展指令

- **默认适度扩展（Level 1）**：「允许顺着现有画面自然补景，丰富远景、天空、地面、植被与环境小物件；可轻微拉远镜头并优化留白，但不改变主体身份、动作和关键关系。新增元素不应抢镜。」
- **严格保留（Level 0）**：「关闭内容扩展；不得增加或删除人物、道具、建筑及背景内容，仅改变绘画风格。」
- **自由丰富（Level 2，仅明确指定时）**：「可明显扩大场景范围，增强前中后景和叙事细节，在保留用户指定主角与关键事实的前提下进行创意扩展。」
- **扩图补全**：「以目标图边缘已有的地形、建筑透视和光源为依据扩展画布，接缝自然，不重复目标图元素，不生成破碎建筑或额外肢体。」

## 可插入的用途约束

- **圆形头像**：「人物和关键道具位于画面中心，保留适当外边距，圆形裁切后轮廓完整；镜头拉远至能清楚呈现主体姿态。」
- **保持原图文字**：「仅保留原图可辨识的所有文字，不新写任何字；文字位置和语义不变。」
- **品牌颜色优先**：「保留主体品牌色与标识，复古色板主要作用于背景、阴影与高光。」
- **城市地标**：「地标建筑不得凭空改变立面、塔楼数量、轮廓和主要窗格关系。」
- **夜景/雨景**：「保留时间天气，不强加参考图的日落暖阳；只迁移冷暖层次、笔触和质感。」

## 负面提示词清单（根据需要摘取）

photorealistic, photographic filter, CGI, glossy reflections, plastic surface, vector flatness, cel-shaded anime, translucent watercolor blooms, over-smoothed gradients, heavy impasto ridges, noisy digital grain, oversaturated neon, copy-pasted reference composition, illogical scenery, distracting additions, changed main subject, invented key characters, caption, watermark, garbled text

## 交付前检查（5 分制）

- [ ] **主体保真（目标 >= 5/5）**：关键人物/建筑/物体身份与姿态准确；指定不可变项未被改动。
- [ ] **绘画一致性（目标 >= 4/5）**：不透明水粉 + 轻厚涂 + 可见细笔触，而非滤镜。
- [ ] **色彩关系（目标 >= 4/5）**：复古柔和冷暖对比；尊重固定主体颜色。
- [ ] **材质质感（目标 >= 4/5）**：哑光颜料层次、细腻纸张颗粒；不过于光滑或脏污。
- [ ] **内容扩展质量（目标 >= 4/5）**：新增元素逻辑合理、丰富但克制，未抢主体，原画与新补部分过渡自然；严格复刻模式则应无新增元素。
- [ ] **用途适配（目标 >= 5/5）**：符合比例、裁切、安全区与文字约束。
- [ ] **无风格参考场景照搬（必须通过）**：没有机械复制参考图里的船、灯塔、海岸、巨型圆日及其相对布局。

如未通过，优先修复主体保真和新增元素逻辑；其次加强手绘色块与笔触；最后微调色彩/纹理。不要一次大幅改动全部维度。
