# 游泳技术、前置条件与反馈契约

本版1.0包含游泳技术扩展。泳课剂量的唯一入口是[游泳编排](swim-programming.md)。[来源登记](swim-technique-evidence.json)定位 Ruben J. Guzman《The Swimming Drill Book》Human Kinetics 2007版；不是后来的第2版。按原文目的和观察点自行概括；插图未核，不复制书图或大段译文。组数、距离、休息、安全筛选和反馈都是产品设计，不冒充书本处方。

## 注册范围

8项均有稳定ID、中文name、english_name、stroke、swim_task_mode、task_requirements/task_requirements_en、equipment_options、observation及evidence_refs。原文18–20在纸页38–43，66/70–73在纸页142–143/150–157。它们是不同任务，不按书中编号自动升级。

- swim_breaststroke_kick_deck（18）：stationary，pool + safe_poolside_seating。
- swim_breaststroke_pull_standing（66）：stationary，pool + safe_standing_depth。
- swim_breaststroke_kick_supine（19）、swim_breaststroke_controlled（72）、swim_breaststroke_two_kicks_one_pull（73）：distance，pool。
- swim_breaststroke_breathe_kick_slide（70）：distance，pool + kickboard。
- swim_breaststroke_kick_streamline（20）、swim_breaststroke_slide_stroke_slide（71）：reference_only，training_allowed=false。单次试做、安全停下换气和实测短段接口尚未开放，不为凑池长虚构25/50米。

67–69的脚蹼/深水变式及74的海豚式变式不进入首批资产；74原文明确不是key drill。不给独自深水练习、屏息挑战或跳发默认处方。

## 首次选取与计划推进

profile.mastery仍是unknown/learning/independent。profile.swim_task_readiness按具体unit_id记录status（unknown/learning/ready）与basis。ready仅表示本次所需前提已明确，basis准确写用户自述或观察，不称医疗许可、水安认证或自动验证事实。距离型还需continuous_distance_m，为该具体练习已知能正常呼吸连续完成的距离；未知或不足25米不猜数。组距不得超此值，不从整泳、其他练习或另一泳姿复制。

四个distance条目须mastery=independent；两项stationary可保留mastery=unknown，在简单动作理解、器材/场地及无已知相关限制明确后按正常完成假设安排。首次有缺口保留draft，不把unknown改成independent。已有确认沿用，不每周重新认证；计划先行、预设正常递进，实际异常反馈才修改后续未执行部分。

器材、场地、伤病限制分别核对。ready不覆盖banned_units、既有专业限制或任务剂量依据。不能把蛙泳视作无条件康复替代。

## 单课目的与计量

session.swim_focus={unit_id,goal,observation}指向本课实际选择的一项泳任务。goal描述本课技术目的，observation只选一个可理解观察点；不列五个同时评分。原文三拍仅作该练习的节奏提示，不变成人人固定三秒或比赛配速。

stationary的dose.duration_minutes是每组真实练习时间，dose.distance_m必须为null；不加假泳距，也不将其算作中高强有氧分钟。distance使用真实组距、组数与恢复，池长变更要重算组距、能力匹配和整课时间。两类均保留正常呼吸与明确停止条件。

资产中的2组、30秒、2×池长是满足写明前提后的产品示例，不是通用成人剂量。量与密度分别记录，一步只改一个主要变量。技术观察不能单独覆盖限制规则。划数可选，只在同泳姿/池长/组距及相近努力下观察，不追逐无限滑行。

## 可选反馈

结构见[swim-feedback.schema.json](../schemas/swim-feedback.schema.json)，入口scripts/swim_contract.py的feedback_errors。必填session_id、unit_id、completion（done/partial/notdone）、difficulty（easy/appropriate/hard）、focus_result（maintained/intermittent/not_maintained/not_observed）；实际组数、距离、时间、恢复及symptoms/next_day_response可选。不观察用not_observed，不报告用not_reported，不把空值当无症状。

反馈只纠偏，不自动修改掌握度或生成医疗判断。无反馈继续预设正常计划，不伪造完成；新发或加重症状按既有限制处理，并可调整后续未执行课。示例见[接口示例](../assets/examples/swim-technique-contract.json)。

## 已知覆盖限制

这是蛙泳技术模块，不是完整蛙泳耐力、速度、竞技或康复课程库。6项可编排、2项仅参考。需要未注册主课时如实保留缺口，不改自由泳资产显示名冒充蛙泳。结构验证和示例通过不等于所有人的处方适宜，也不得直接把设计审查改成pass。
