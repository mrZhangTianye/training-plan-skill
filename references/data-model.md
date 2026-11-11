# 数据结构

计划交换格式为JSON，Markdown负责展示。用户条件、目标、安排、阶段、周、单次和审查使用稳定ID；版本递增并保留已完成历史。通用Skill不保存真实用户个人计划。

## 起点与预定递进

`schema_version=0.3`为当前格式。兼容0.1和0.2版本号，但旧计划须迁移到当前字段契约，包括移除已废弃的资料来源字段；真实执行版仍需符合当前判据。未知值用null或unknown，不当作false或0。

`objectives.capability_ids`关联能力词表；`baseline_basis`保存用户自述、近期训练、已有测试或未知起点的依据、日期及局限。有限或未知起点配合`design_context.uncertainty_actions`中的明确保守初始剂量即可支持执行建议，不要求额外测试或逐次日志。

每个develop目标提供`progression_plan`数组。每条包含`first_week、last_week、session_frequency、planned_dose、progression`；阶段恰好覆盖整个周期。`planned_dose`写具体组次、时长、距离与强度，`progression`写预先安排的变化。已展开周的对应刺激课数不能少于预定频率。默认用户正常完成并按计划推进；反馈是修正依据，不是允许进阶的必经证明。脚本检查结构与频率，剂量是否足以支持目标仍须训练判断。

`arrangement.status`为proposed、selected或confirmed。selected表示在用户已授权直接排课的范围内选择了推荐结构，可用`selection_basis`说明授权范围；confirmed表示用户已明确认可安排。两者都可支持执行版，不能把selected冒称用户确认。已明确的整体安排沿用，用户要求先讨论方案时才保留proposed。

## 单次与时间

每次保存`mini_goal`和`purpose`，前者是本次可执行的小目标，后者说明阶段作用。`goal_ids`引用已有目标。新计划给跨周同一课程稳定的`session.course_id`，模块给`module.id`，模块内工作项给`item.id`；改名、调日期或换行序仍沿用ID，改变训练任务时换工作项ID。模块与items的分配分钟合计必须一致，总时长预留工作、恢复及转换。

`weeks.variation`仅兼容旧的定性说明，不再保存组次、分钟或距离等数字处方。周主力剂量和跨周矩阵从sessions实际工作项生成，禁止手写第二套剂量声明。

`dose`区分组数、次数、每侧信息、单侧／组时长、每组距离、强度和恢复。适用力量内容用目标RPE，重量为参考；实际表现与目标分开。**公斤数不是必填**：`load.selection_method`写选重方法（如「首组取熟悉且偏轻的重量，做完明显多于目标余次数就按最小档加重」），配合组次、目标RPE与`rest_seconds`预设单值即可生成完整课表；只有来自TR记录时才写`reference_weight_kg`。`rest_seconds`对本类内容必填，不许留空等执行时定。力量或爆发不用RPE时，`load.execution_target`写本组具体用力或质量锚点，如快速髋伸且躯干稳定，不能用通用说明代替。强度可采用清楚的呼吸、速度或技术质量要求，不强制全部内容使用RPE。

`item.work_seconds_per_set`是**完整一组的全部工作秒数，已经包含所有侧**，不能再乘per_side。`dose.duration_minutes`仍表示每侧／组时长，脚本按sets和per_side展开。已知动作节奏可给`tempo_seconds_per_rep`，按次数×节奏×每侧系数推导；已知个人泳速可给`swim_pace_seconds_per_100m`，按组距推导。多种估算同时提供时必须一致。不知道节奏或泳速时给透明的整组秒数估算，不捏造测得值。`timing_summary`区分可推导、作者估算和缺少估算；时间预算通过不代表现实一定按时完成。

配对／三联组使用单次内唯一的`module.group_label`；每个动作保留自己的`dose.sets`。组数相同时默认按items行序循环；组数不等时必须提供`module.set_sequence`，用1起算的items位置表示逐组次序。爆发3组、两个核心各2组可用`[1,2,3,1,2,3,1]`；每个位置的出现次数必须等于该动作sets。不允许靠文字声称组合却缺少结构化顺序。

所有组内动作给完整组工作秒数。`rest_seconds`指本动作一组结束到下一组开始的最低恢复；穿插工作计入。脚本按序列为每组计算满足自身恢复后的启动时刻，合计工作与必要等待，再与模块时间比较；必要补休向上取整至30秒，模块余量用于转换和调负重；转换可以占用已经需要的等待，不能重复累计。课表用A1/A2/A3等可读顺序，显示不同组数及补足恢复的组序，不把所有动作恢复相加。

`item.display_name`可选，用于具体本次任务名称，例如“自由泳：换气巩固”或指定部位的滚压，不改变unit_id、器械、能力或技术前置条件。

`design_context.strength_waves`可选，声明DUP主力锚点，每条为`unit_id、first_week、last_week、rationale`；相应主工作项用`wave_role=capacity/heavy`标记。已展开周须在不同日期有同一动作两类工作组，明确次数与目标RPE，较重课次数低于容量课。准备组不标wave_role，其他模式分日无需伪造DUP。脚本检查声明一致性，不认证实际公斤数变重或训练效果。

`item.execution_note`为可选的本行必要执行提示，例如泳姿、简单准备的具体形式或某周改变负重的规则。已知动作特殊限制也须写入该字段，不能藏在后台stop_condition；它不能掩盖未满足的复杂技能前置条件。单次表只展示日期、预计用时、小目标、模块表与必要提示，不重复全部cue、notes和停止条件。profile.restrictions中的已知限制仍显示，明显不适或动作失控的异常规则只留一条短句。阶段按课程和模块展示横向周剂量，配对／三联动作相邻；固定准备和整理在当周单课查看，真正变化的剂量和执行提示仍保留。

跨周合并靠显式稳定编号，构建时必须写对，否则阶段视图会退化成每周一份重复块：`session.course_id`取稳定课型码（如F1、S1），**不能取session id**；`item.id`取`unit_id`加模块内重复序号（同一模块内同一unit_id第二次出现才追加`-2`、`-3`），**不能用全局计数器**——全局计数器每周产出新编号，跨周无法对齐。`module.id`可留空，按group_label或title归并。编号在同一父级内重复会被拒绝并报`稳定编号重复`。

`dose.recovery_type`区分rest、active_recovery和sendoff。sendoff为游泳出发间隔，使用`sendoff_seconds`，同项`rest_seconds=0`，工作时间不能超过间隔。主动恢复的时长仍计入总时间。

单日单课可不指定时刻，按当日`available_minutes`检查，周表统一注明未标时刻的单课时间灵活安排。已提供`profile.windows`时需`start_time`以核实。双课始终指定各课开始时间，不能重叠、跨日或超出用户窗口。已给出的开始时间在周表和单次可见；不会为单课灵活安排强制增加时间窗问答。

## 有氧净运动与安排目标

`profile.pool.length_m`保存常用池长，`pace_seconds_per_100m`可保存已知可持续泳速；不同场地的单课用`session.pool_length_m`覆盖。组距须为本课池长的整数倍。短段技术或速度任务用`partial_length=true`并在execution_note说明起止与余下池长如何完成，不能让25米任务在50米池中无出口。游泳距离不按每侧计数。

库内`endurance_role`标记实际运动形式。泛用准备、整理项在item注明run、swim或walk，不能把已明确跑泳资产改标为其他形式。实际跑段再给`run_intensity=easy/tempo/interval/fast`；与健康用途的aerobic_intensity分开。跑步热身、恢复慢跑与冷身均按实际形式参与总量，步行、纯休息和陆上准备排除。时间型跑段缺可靠配速时距离为未知；可给每组`dose.distance_estimate_m`及`distance_estimate_basis`，输出明确为预计距离。部分已知距离不能冒称全课总距，未知值不显示为零。

`item.aerobic_minutes`保存本项计划计入的净运动分钟，`aerobic_intensity`为light、moderate或vigorous，两者同时明确才进入统计。净分钟不能大于完整组工作秒数乘组数，或duration_minutes乘组数和每侧系数。全课时间、休息、转换和未标注的力量工作不能自动计入；训练类型和RPE不能替代有氧强度标注。

每周同时显示已标注净运动和计划中等当量。light只计入净运动，当量为moderate分钟加2倍vigorous分钟。跑／泳项未标明净时间或强度时列为未核定，不根据类型推断，也不自动双计。数字是编排时的强度假设，不是脚本对实际生理强度或健康效果的认证。

可选的`design_context.aerobic_plan`保存`target_weekly_equivalent_minutes、rationale`及`target_by_week`。target_by_week使用周期内周号字符串作为键，只检查明确指定的中间目标；末周取总目标与末周明确目标中的较高值。未指定中间目标的前期可为渐进阶段，不因首周低于150分钟自动阻塞。目标周出现未核定项或实际安排当量缺口时，insufficient_basis给出具体问题，执行版须修改剂量、标注或目标；取舍理由不能填补实际缺口。未设当量目标时goal_pass为null，不能据结构执行检查宣称有氧维度达标。

## 能力与恢复取舍

`design_context.coverage`逐项说明11项能力的develop、maintain、defer或unassessed，允许重点发展部分能力。`item.capability_ids`只能选择注册资产已有能力的子集，不能给热身随意加速度标签制造覆盖。需要新能力时先核验和注册合适资产。

跳跃以`contacts_per_rep × sets × reps × 每侧系数`计算接触量，`contact_budget`保存逐日期预算。预算依当前耐受和任务设计，不是医学阈值。

脚本对相邻同部位高成本训练、同日两次非低成本课及接触量超预算生成稳定`review_id`：`overlap:课ID:课ID`、`same_day:课ID:课ID`、`contact_budget:日期`。前两种课ID按字符串排序。执行版须在`design_context.review_resolutions`逐条提供`{review_id, context_hash, decision, rationale}`，decision为accepted_tradeoff或modified_plan，rationale说明本项具体取舍。`context_hash`由脚本在review_requirements给出，绑定当次相关课的实质负荷、时间、恢复、局部疲劳或接触量及预算；旧处理与当前hash不同需Skill复审并更新理由，不能用旧理由直接通过。标题、组合编号、说明中的排版或标点变化不单独触发复审。它是后台设计记录，不新增用户日志或重复确认。主动确认一次设计决定不要求训练日志。普通提醒和远期未展开提示不一律阻塞；已失效的历史处理记录保留并注明。

`design_context.reentry`保留新建、继续、暂停、退出、重返状态及中断天数、原因、当前依据、首课策略和后续关联。`recovery_review`保存总体恢复判断，不能代替实际触发事项的处理。

## 版本与观察

`weeks.detail_status=summary`表示仅有方向和模块安排；scheduled表示本周单次已展开，休息日在`rest_days`中明确。空日期不显示成休息。完整导出执行课表时每周都须scheduled。

`evidence`可为空。用户主动反馈时保存`source_type`、原话、观察、解释、日期与可选实际组；这里的source_type表示用户内容类型，不是资料来源。实际组分别保存重量、次数及实际RPE。不要求记录每次训练才能推进或改课。

计划数据不保存文献书目、作者、检索链接或私有资料路径。训练资产保留执行字段与稳定ID；蛙泳来源以 evidence_refs 关联独立来源登记，候选条目不自动成为可处方资产。

注册资产的dose_domain.fields标明machine_check、plan_field及换算系数；脚本据此检查本项明确参数界限及适用池长，不能把目录默认剂量当本人的固定剂量。未有结构化接口的参数及文字前提由设计者检查，check_coverage保留这一边界。混合走跑或变强度单元按requires_segment_expansion拆成实际工作段；混合形式不整段默认计跑，走、跑和强度变化分别标注。

每条design_review给`checked_ids`，引用具体目标、阶段、课程、计划或用户条件ID；reason说明检查了哪个实际处方、如何支持任务及剩余取舍。ID存在性检查不认证理由的质量，仍由设计者逐项判断。

脚本输出errors（确定的数据错误）、review_items（提醒及已处理取舍）、insufficient_basis（当前执行缺口）、review_requirements（具体取舍）、aerobic_summary（健康用途计划净量及当量）、endurance_summary（逐课逐周跑泳总量与跑步分配）、timing_summary（时间依据）、check_coverage（本次覆盖的检查）与执行状态。草案输出展示具体执行缺口。语义审查是设计者的明确判断，不是科学认证；通过检查不等于训练效果或个体安全保证。

## 改字段的完整链条

新增或重命名字段不是改 schema 一处就完事。按顺序走完六处，缺哪一步的报错形式都不一样：

1. **`schemas/plan.schema.json` 的 `$defs.*.properties`**（`load`、`dose`、`item` 各算一处）。这些对象是 `additionalProperties: false`，**漏这一步的症状是每条 fixture 都报 `…: unexpected field`、几十条测试一起红**——不是判据逻辑写错了，别往那儿找。
2. **`scripts/validate_plan.py`** 的判据分支：把新字段接进已有校验链，并各配一条反向断言（缺它报具体文案）与一条正向断言（有它就通过）。
3. **`scripts/render_plan.py`**：课表要能照着写出来。可选字段要有「无该值时的降级显示」，别让表里留下空白强度格。
4. **`scripts/design_checks.py` 的课次快照**：它把每项的 `sets/reps/rest/target_rpe/reference_weight_kg…` 拍平成签名，比「相邻两课剂量是否雷同」。**新字段不进快照，改了它也会被判成同一剂量没变化**，台阶检查形同失效。
5. **`tests/test_workflows.py` 的 fixture**：fixture 要带新字段，否则所有用例测的还是旧形状。
6. **把该字段当交付要求写死的文档**：`intake.md`（问什么）、`output-spec.md`（表里写什么）、`decision-rules.md`（判据）。这类要求通常以「必须取到…」「取不到就标待补」的口吻**分散在多份文件里**，`grep -rn '关键词' references/` 一次扫干净；只改一处，下一版照旧被旧句拉回原点。

**放宽一条交付要求时，做法是「换锚点」不是「删要求」**：某字段从必填降为可选（如公斤数让位给选重方法），要在同一轮里把「缺什么才算不合格」重新说清（缺的是选重方法，不是公斤数），并让脚本按新锚点报错——否则脚本继续拦旧条件、文档已经许了新车，用户按新文档做出来的课表一律被判不合格。

## 改示例课次的结构性编辑

改 `assets/examples/plan.json` 里的一课（加模块、换组距、把陆上段塞进泳课）时，下面五件事不一起做就会换来一串看似无关的报错：

1. **照抄模块会把 `id` 一起带过去**，同一课内出现两个相同 `module.id` 即报稳定编号重复。新模块重新生成 id（按其所在课派生），`item.id` 用 `unit_id` 加模块内序号。
2. **`item.duration_minutes` 是含休息的整组分钟**。改 `sets` 或组距时 `item`、`module`、`session` 三层一起改：`module`＝其 items 之和，`session`＝其 modules 之和，差一点就报「模块时间与 items 合计不一致」。
3. **陆上模块放进泳课，不能继承泳项字段**：`swim_pace_seconds_per_100m`、运动形式一类留着会被当成水中项，校验器按泳速要求确定组距并报「泳段需有确定组距」；item 也不能挂 `endurance_role`（schema 只认 run／swim／walk）。陆上准备与泳后拉伸用通用 unit（`cooldown` 一类），不挂 `endurance_role`、不给距离，不进水中量。
4. **池长写在本课**：`session.pool_length_m` 覆盖 `profile.pool.length_m`，组距必须是它的整数倍——25 m 池配 `4×50` 是内部矛盾，两种池长的技术块也不等量（25 m 池 4×25＝100 m、50 m 池 4×50＝200 m），换池长要重算技术块、主组和整课总量。
5. **改完剂量就重算当量目标**：`design_context.aerobic_plan` 的末周目标高于实际计划当量时，该周直接进 `insufficient_basis`、出稿被拦。做法是把目标改成实际值并在 rationale 写明为什么降，不是回头把剂量凑到目标上。

**测试硬编码了示例的数字**：示例总量、周量、当量目标一改，先 `grep -rn '旧数' tests/` 再跑全量——泳 800→600、跑 147→107 这类改动都会同时打到 `test_dose_basis` 与阶段断言上，逐条按新值改，别只改脚本常量。

## 改一组主项组次后的连带更新

改 `dose.sets`／`dose.reps` 是改一个数、动四处副本。按这个顺序走，漏一步就换来一批看着像「改坏了」的报错：

1. **先认准哪几行是工作组**：按 `dose.load.target_rpe` 筛（准备组是 RPE4 或 null）。拿 `target_rpe is None` 当「不是工作组」会把准备组一起改掉（2×3@RPE4 被写成 2×8），而这批改动不报错、只是剂量多了一大块。
2. **`module.set_sequence` 要跟着重建**：模块里各动作 `sets` 相等时可以整个键删掉（默认按行序循环）；不等时才给，每个位置出现次数必须等于该动作 `sets`。改完组数不等还留着旧序列，报 `set_sequence counts must match each item set prescription`。
3. **时长重算用 `duration_model.apply(plan)`**，`item→module→session` 三层一次写回；手改任一层就和别的层对不上。
4. **`mini_goal` 重生成**：力量和跑泳一样是「手写副本与处方并存」，组次一改原文案还写着「各 3×8」。按新剂量重写（动作名取资产表 `name`，分组按 `(sets, reps, per_side)` 归并），改完 `summary_drift` 必须回到 0。
5. **`design_context.review_resolutions` 的 `context_hash` 全部失效**：hash 绑定实质负荷，组次一变旧 hash 全过期，`stage_handoff:<block>`／`overlap:*`／`contact_budget:*` 会要求逐条复审，actual 模式下直接不出表。拿 `validate()` 返回的 `review_requirements` 里的新 hash 逐条回写，理由里写明这次变化的方向（如「跑抬一档、力量只降不升，不是叠加」）。
6. **跨文件数字对齐**：`references/stage-dosing.md` 这类阶段表与示例是两份副本，组次一改就可能一处 3×8、一处 3×9／3×10。改完 `grep -rn '旧组次' references/ SKILL.md`，把阶段表、表下旁注、待定区一起核。


## 短期日期范围（0.3.24）

可选 `scope={"window":"day","dates":["YYYY-MM-DD"]}` 只声明起始日；`window=week` 必须列起始日起七天。两者只用于 `duration_weeks=1`，不填仍保持原整周契约。单日数据继续使用一个内部周容器，不代表计划覆盖七天或多阶段周期。所有课次、休息日须在声明范围内，scheduled 范围必须完整交代；原剂量、恢复与就绪检查仍执行。总览、课表、记录式输出和导出的默认文件名按单日呈现。周目标并不因为单日范围自动折算或免检，缺少整体上下文时应保留待核定状态，不能宣称完成一周训练目标。

## 固定球日与替换审核（0.3.24）

可选 `ball_days` 是日程约束，不是训练处方。每项包含 `id,date,sport,source`；球种为任意非空文本，可用「其他」。可选 `start_time`（HH:MM）和 `duration_minutes` 仅保存已知信息，未知不猜、不强制问。不得把球日写成力量、跑泳课来骗过覆盖校验。

验证器 `ball_check` 分为 `errors`（日期/休息/明确重叠等冲突）、`reminders`（包括总时长未核定、相邻日恢复提醒）和 `unverified`（同日所需依据不足，关联周不可伪标就绪）。两个开始时刻不能代替真实课间恢复；非重叠不代表恢复充分，同日安排需现有 `load_recovery` 审核明确涵盖双方ID。48/24小时指引在仅有日期时只能作邻近日提醒，不是假精确的小时判定。

球替换用 `compare_ball_replacement(before,after,replacements,reason,evidence_ids,association)` 审核独立前后快照，提案项为 `session_id,ball_day_id,source`。必须保留原快照、形成递增版本；不能用 `displaced_by` 隐藏原课程跳过验证。已完成或带执行事实的课次与证据不能被替换或删去。该入口生成差异而不写回原计划，不支持自动删除或无人确认的重排。

日期校验不证明球类负荷、医学安全或长期效果。已有具体身体限制和训练组合约束仍需检查。


## 游泳技术扩展 0.3.25

profile.swim_task_readiness以unit_id为键，保存status、basis及距离型任务的continuous_distance_m；不由整泳能力或另一泳姿填入。session.swim_focus指向本课实际选中泳任务，保存goal与单一observation。原地技术练习保持category=swim但swim_task_mode=stationary，按每组时间计，distance_m=null且不计有氧泳量。可选反馈用[独立schema](../schemas/swim-feedback.schema.json)，不改已有记录，不通过缺日志阻断正常计划。完整语义见[游泳技术契约](swim-technique-contract.md)。
