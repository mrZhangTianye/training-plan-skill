# 动作中英对照

以《体育运动中的功能性训练》第 2 版（中文版）的译名为准。术语对不上会导致同一动作两个名字、或两个动作被叫成一个名字，这类错误在写课表时看不出，执行时才出错。

页码为中文版印刷页码。

**skill id 列的三种取值**：`xxx` ＝ 库内已有条目，能在 `training-library/exercises.json`（302 条动作）或 `training-units.json`（60 条课内单位）里查到，写课表按 id 引用；`—` ＝ 还没对应，待定；`not_in_library` ＝ **书里有这个动作、库内没有任何条目**——既不写 id，也不许拿近义动作顶替（按中文名或英文名去库里模糊匹配出来的近似动作一律不算）。**资产层只有这两份文件算数**；`assets-v3.json` 是分类索引，不单独提供动作定义，`assets-v3` 里查不到不代表库里没有、查到也不代表可直接引用。

## 一、髋主导

| 书译名 | 英文 | skill id | 现用中文名 | 书页 |
|---|---|---|---|---|
| 直腿硬拉 | Straight-leg Deadlift (SLDL) | — | 未收录 | 48 |
| 单腿直腿硬拉 | Single-leg SLDL | `single_leg_rdl` | 单腿直腿硬拉 | 71, 115 |
| 罗马尼亚式硬拉 | Romanian Deadlift (RDL) | `rdl` | 罗马尼亚硬拉 | 48 |
| 哑铃单腿硬拉 | Dumbbell Single-leg Deadlift | `single_leg_rdl` | 单腿直腿硬拉 | 115, 223 |
| 杠铃硬拉 | Barbell Deadlift | `barbell_conventional_deadlift` | 传统硬拉（杠铃，地面启动） | 206 |
| 六角杠硬拉 | Trap-bar Deadlift | `trap_bar_deadlift` | 六角杠硬拉 | 11（仅提器材） |
| 壶铃硬拉 | Kettlebell Deadlift | `kb_deadlift` | 壶铃硬拉 | — |

书里把 SLDL 与 RDL 明确分开：RDL 是“改良版直腿硬拉”（页 48 脚注），两者不混用。写课表时应以前者为髋主导初阶、后者为负重过渡。

| 书译名 | 英文 | skill id | 现用中文名 | 书页 |
|---|---|---|---|---|
| **深蹲保持** | Squat Holds | not_in_library | 深蹲保持 | 208 |
| **药球触脚趾下蹲** | Toe Touch Squat with Medicine Ball | not_in_library | 药球触趾蹲 | 209 |

**这两条是同一槽位的两档，不是可互换的两个动作**：春季表（11.2）第 4 天用 Squat Holds，后续阶段（11.3–11.5）第 4 天换成 Toe Touch Squat with Medicine Ball。先做蹲位保持，再加重药球升级。

**两条包内保留用语（与书译名不同，以包内为准）：**

| 书译名 | 包内用 |
|---|---|
| 罗马尼亚式硬拉 | **罗马尼亚硬拉** |
| 哑铃斜卧推 | **上斜哑铃卧推** |

## 二、膝主导

| 书译名 | 英文 | skill id | 现用中文名 | 书页 |
|---|---|---|---|---|
| 后脚抬高分腿蹲 | Rear-foot-elevated Split Squat | `rear_foot_elevated_split_squat` | 后脚抬高分腿蹲 | 33, 100, 112 |
| 分腿蹲 | Split Squat | `split_squat` | 分腿蹲 | 41 |
| 弓步蹲 | Lunge | — | — | 34, 100 |
| 侧弓步蹲 | Lateral Lunge | `lateral_lunge` | 侧弓步蹲 | 70 |
| 单腿深蹲 | Single-leg Squat | `single_leg_box_squat` | 单腿深蹲（箱上） | 48, 114 |
| 手枪式深蹲 | Pistol Squat | — | — | 105, 114 |
| 高脚杯深蹲 | Goblet Squat | `goblet_squat` | 高脚杯深蹲 | — |
| 颈后深蹲 / 颈前深蹲 | Back Squat / Front Squat | `barbell_high_bar_back_squat` | 杠铃高杠后蹲 | 33 |

**两条硬约束（书明确写了的）：**

1. **“保加利亚分腿蹲”不是正名。** 书页 100：“可以将它称为保加利亚弓步蹲（说它傻是因为它既不是保加利亚的，也不是一个弓步蹲）”。正名用**后脚抬高分腿蹲**。
2. **手枪式深蹲不推荐。** 书页 105：“下蹲到力量举式平行，避免当前流行的手枪式深蹲”；页 114：“不应混淆单腿深蹲与手枪式深蹲。我们有很多理由不做也不赞成做手枪式深蹲……这两个练习看起来很像，但它们是不可互换的”。**单腿深蹲**才是书推荐的那个。

## 三、推

| 书译名 | 英文 | skill id | 现用中文名 | 书页 |
|---|---|---|---|---|
| 卧推 | Bench Press | `bench_press` | 卧推 | 178 |
| 哑铃卧推 | Dumbbell Bench Press | `db_bench_press` | 哑铃卧推 | 178 |
| 哑铃斜卧推 | Incline Dumbbell Press | `incline_db_bench_press` | 上斜哑铃卧推 | 178, 223 |
| 俯卧撑 | Push-up | — | — | 30 |
| 地板卧推 | Floor Press | `db_floor_press` | 哑铃地板卧推 | **书中无** |

**书中没有地板卧推。** 卧推族只有卧推 / 哑铃卧推 / 哑铃斜卧推三个。地板卧推是无凳场景的包内补充，引用时必须标“包内补充”，不得说成书里的动作。

## 四、拉

| 书译名 | 英文 | skill id | 现用中文名 | 书页 |
|---|---|---|---|---|
| 引体向上（正握） | Pull-up | `pull_up` | 引体向上 | 31, 171 |
| 反握引体向上 | Chin-up | `chin_up` | 反握引体向上 | 31, 171 |
| 吊环划船 | Ring Row | `ring_row` | 吊环划船 | 171, 223 |
| 悬吊划船 | Suspension Row (TRX) | — | — | 171 |
| 反向划船 / 仰卧悬垂引体 | Inverted Row | — | 未收录 | 32, 176 |
| 哑铃划船 | Dumbbell Row | `db_row` | 哑铃划船 | 223 |
| 下拉器械（宽握） | Lat Pulldown | `lat_pulldown` | 宽握高位下拉 | 164, 223 |
| X 下拉 | X Pull-down | `x_pulldown` | 交叉绳索下拉 | 164, 223 |

“反向划船”与“仰卧悬垂引体”是同一个动作的两个名字（页 32 原话），不是两个动作。

## 五、核心

| 书译名 | 英文 | skill id | 现用中文名 | 书页 |
|---|---|---|---|---|
| **下劈** | Chop | `split_stance_cable_chop` | 分腿低位保持绳索下劈 | 141 |
| **上拉** | Lift | `split_stance_cable_lift` | 分腿低位保持绳索上拉 | 141 |
| 直线单膝跪地稳定下劈 | Half-kneeling Cable Chop | — | — | 141 |
| 正面平板支撑 | Front Plank | — | — | 140 |
| 平板侧撑 | Side Plank | — | — | 140 |
| 平板侧撑划船 | Side Plank Row | `side_plank_row` | 侧桥划船 | 140 |
| **提箱子行走** | Suitcase Carry | `suitcase_carry` | 单侧手提走 | 140 |
| 农夫行走 | Farmer Carry | `carry` | 农夫走 | 141 |
| 过顶负重行走 | Overhead Carry | `overhead_carry` | 过顶负重行走 | — |
| 臀桥 / 单腿臀桥 | Bridge / Single-leg Bridge | — | — | 124 |
| 土耳其起立（总称） | Turkish Get-up | — | — | 223 |
| 四分之一土耳其起立 | Quarter Get-Up（Baseline） | `unloaded_quarter_get_up` | 徒手四分之一起身 | 208, 223 |
| 半程土耳其起立 | Half Get-Up（Progression 1） | — | — | 223 |
| 全程土耳其起立 | Full Get-Up（Progression 2） | — | — | 223 |
| TK 抗旋转前推 | TK Anti-rotation Press | — | — | 223 |

**chop/lift 的中文是“下劈 / 上拉”，不是“下砍 / 上举”。** 来源是库克（Gray Cook）的 PNF 对角线模式（页 141）。书里同一段还批评了早期那种“砍伐练习”，所以写课表时不要用“砍”字，会和被批评的那类练习混在一起。

## 六、爆发

| 书译名 | 英文 | skill id | 现用中文名 | 书页 |
|---|---|---|---|---|
| **跳箱** | Box Jump | `box_jump_stick` | 低箱跳箱接稳 | 193 |
| 蹲跳 | Squat Jump | — | — | 214 |
| 悬垂高翻 | Hang Clean | `hang_power_clean` | 悬垂力量高翻 | 404–416 |
| 窄握抓举 | Close-Grip Snatch | **缺**（库里无对应） | — | 416 |
| 单臂哑铃抓举 | Single-Arm Dumbbell Snatch | `single_arm_db_snatch` | 单臂悬垂哑铃抓举 | 426 |
| 单腿高翻与抓举 | Single-Leg Cleans and Snatches | **缺**（库里无对应） | — | 426 |
| 药球胸前传球 | Chest Pass | `medicine_ball_standing_chest` | 站姿药球胸前投掷 | 44 |
| 药球过顶抛球 | Overhead Throw | `medicine_ball_overhead` | 站姿药球过顶投掷 | 44 |
| **猛摔砸球** | Slam | `medicine_ball_overhead_slam` | 站姿猛摔砸球 | 44 |
| 药球侧抛 | Side Throw | `medicine_ball_standing_side` | 站姿药球侧向投掷 | 48 |

“箱跳”是倒装，书里一律写“跳箱”。

## 七、能量代谢

| 书译名 | 英文 | skill id | 书页 |
|---|---|---|---|
| 雪橇车 / 负重雪橇车 | Sled / Loaded Sled | — | 84 |
| 滑板 | Slide Board | — | 30–31 |
| 迷你滑板 | Mini Slide Board | — | 31 |
| 滑垫 | Slide Mat | — | 31 |
| 风阻自行车（Airdyne / Assault） | Air Bike | — | 238 |
| 椭圆机 | Elliptical | — | 236 |
| 滑板屈腿 / 瑞士球屈腿 | Slideboard / Swiss-ball Leg Curl | — | 124 |

## 八、书中未收录的动作

| 动作 | 英文 | 包内 id | 处理 |
|---|---|---|---|
| 地板卧推 | Floor Press | `db_floor_press` | 哑铃地板卧推 |
| 北欧腿弯举 | Nordic Hamstring Curl | — | 保留为补充；书的腿弯举形式是滑板屈腿 / 瑞士球屈腿（页 124） |
| 手枪式深蹲 | Pistol Squat | — | **不用**，书明确反对 |
| 保加利亚分腿蹲 | Bulgarian Split Squat | — | **不用这个名**，正名后脚抬高分腿蹲 |

## 九、已统一的用语

以下已在**动作库与本表**同时执行（只换术语，保留部位与变体限定）。本表「现」一列就是库里的 `name` 原值，改名前先核库，不要只改文档：

| 旧 | 现 |
|---|---|
| 单腿硬拉 | 单腿直腿硬拉 |
| 壶铃髋铰链硬拉 | 壶铃硬拉 |
| 箱上单腿蹲 | 单腿深蹲（箱上） |
| 平凳哑铃卧推 | 哑铃卧推 |
| 杠铃卧推 | 卧推 |
| 下砍 | 下劈 |
| 上举 | 上拉 |
| 胸前推掷 | 站姿药球胸前投掷 |
| 过顶砸地 | 猛摔砸球 |
| 箱跳 | 跳箱 |

**不作统一的两条**：罗马尼亚硬拉、上斜哑铃卧推（见第一节）。书译不同但包内保留，写课表以包内为准。

## 十、移动技能（第 5 章热身末段 / 第 11 章「动作技能」段）

| 书译名 | 英文 | skill id | 现用中文名 | 书页 |
|---|---|---|---|---|
| 侧向滑步 | Lateral Shuffle | `lateral_shuffle` | 低速侧滑步 | 73 |
| 卡里奥卡步 | Carioca | `carioca` | 交叉步行进 | 73 |
| 侧向爬行 / 横向爬行 | Lateral Crawl | not_in_library | 侧向爬 | 74, 226 |
| 侧向跨步跳 / 横向垫步跳 | Lateral Skip | `lateral_skip` | 侧向跳步 | 64, 226 |
| 上交叉跳 | Crossover Skip（Fig 5.38） | not_in_library | 上交叉跳 | 66, 226 |
| 下交叉跳 | Cross-Under Skip | not_in_library | 下交叉跳 | 66, 226 |

**上交叉跳与下交叉跳是同一个侧向跳的两种发力腿，不是两个方向**：外观一样，发力腿相反——上交叉跳是跨出那条腿蹬地（Crossover Skip），下交叉跳是跨下那条腿蹬地（Cross-Under Skip）。**不要写成「前交叉／后交叉」**：前交叉、后交叉是第 5 章 ladder 里的另一族动作（Cross in Front／Cross Behind），跟这对不是一回事，混写会让写课表的人排错。同理，侧向跨步跳／横向垫步跳只是译名差异，写课表统一用「现用中文名」列。

## 十一、热身与激活段（第 5 章 / 第 11 章准备段）

| 书译名 | 英文 | skill id | 现用中文名 | 书页 |
|---|---|---|---|---|
| 毛毛虫 | Inchworm | `inchworm_prep` | 虫行 | 208 |
| 熊爬 | Bear Crawl | `bear_crawl_prep` | 熊爬 | 208 |
| 行进抱膝 | Knee Hug（Walking Knee Hug） | `knee_hug_walk` | 行进抱膝 | 208 |
| 摇篮抱腿 | Leg Cradle | `leg_cradle_prep` | 抱腿髋外旋 | 208 |
| 单腿下落 | Leg Lower | `leg_lower` | 仰卧交替降腿 | 208 |
| 库克式提髋 | Cook Hip Lift | `cook_hip_lift` | 抱膝单腿髋桥 | 208 |
| 箱子屈髋肌拉伸 | Box Hip Flexor | `box_hip_flexor_stretch` | 箱式髋屈肌拉伸 | 208 |
| 内收肌后坐拉伸 | Adductor Rock | `adductor_rockback` | 内收肌后坐 | 208 |
| 交替蜘蛛侠 | Alternating Spiderman | `alternating_spiderman` | 交替蜘蛛侠弓步 | 208 |
| 四点接触式胸椎旋转 | Quadruped T-Spine Rotation | `quadruped_t_spine_rotation` | 四点支撑胸椎旋转 | 208 |
| 仰卧屈膝呼吸 | Supine Knees-Bent Breathing | `supine_knees_bent_breathing` | 仰卧屈膝呼吸 | 208 |
| 仰卧地面滑臂 | Supine Floor Slide | `supine_floor_slide` | 仰卧地面滑臂 | 208 |
| 迷你弹力带外旋和内旋 | Mini-band External & Internal Rotation | `mini_band_rotation` | 迷你带内外旋 | 208 |
| 迷你弹力带深蹲 | Mini-band Squat | `mini_band_squat` | 小环带自重深蹲 | 208 |
| 向后弓步走加腘绳肌拉伸 | Backward Lunge Walk w/ Hamstring Stretch | `reverse_lunge_hamstring_prep` | 后撤弓步接腿后侧伸展 | 208 |

**这一段的坑是英文词直译**：Inchworm 的字面意思是尺蠖（一种弓身行走的蛾幼虫），但**书译作「毛毛虫」**，写「尺蠖」算自造译名。同理不要把 Leg Cradle 留英文、不要写「腿摇篮」，也不要把 Cook Hip Lift 写成中英混写——这一段一律用本表「现用中文名」列。

## 十二、禁则

- 不把“后脚抬高分腿蹲”写成“保加利亚分腿蹲”或“保加利亚弓步蹲”。
- 不把“单腿深蹲”与“手枪式深蹲”当成同一个动作，也不用后者作进阶。
- 不把“下劈 / 上拉”写成“下砍 / 上举”。
- 不把“地板卧推”说成书里的动作。
- 不用“箱跳”，用“跳箱”。
- 不把 Inchworm 写成“尺蠖”（书作“毛毛虫”）；不把 Leg Cradle 留英文或写成“腿摇篮”。
- 不把“单腿下落”写成“仰卧降腿”，不把“箱子屈髋肌拉伸”写成“半跪髋屈肌拉伸”。
