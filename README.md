[English](README.en.md)

> 当前公开源包候选版本：0.3.25。游泳扩展与验收见 [游泳技术契约](references/swim-technique-contract.md)。

# training-plan · 综合训练课表

A 12-week hybrid training-planning skill: functional strength + running + swimming, with explicit doses, pre-set progression, and a validated JSON plan format.
一体化训练计划生成与校验工具：功能性力量 + 跑步 + 游泳，剂量明确、递进预设、结构可校验。

## 这是什么

本技能把「排一份能照着练的课表」拆成可检查的结构：一份 `plan.json` 保存全部处方与设计判断，
一组脚本负责校验、渲染与导出，一套 Markdown 文档说明编排原则与判断规则，一个 336 条的动作库提供可选资产。

特点：

- **剂量明确**：每项给确定的组数、次数、时间或距离、强度、恢复与执行要点，不留「视情况而定」。
- **预设递进**：12 周按四个 3 周阶段展开（阶段 1 上量→2 上强度→3 力量接爆发→4 力量耐力＋巩固），每阶段给剂量区间与起点，各周剂量可横向比较。
- **强度双轨**：适用力量用「目标 RPE + 剩余次数」选重（RPE7 ≈ 余 3 次），参考重量取自训练者真实做过的重量（TR），无记录时写「待补 + 首组自校准」。
- **结构可校验**：脚本检查时间预算、组顺序、接触量、有氧当量、动作库引用一致性；语义合理性仍由设计者判断。
- **不外显来源**：课表与交付文件不出现作者、教材、论文、引用编号或原始文件路径。

## 结构

```
SKILL.md                    技能入口与操作流程
references/                 编排原则、剂量规则、数据结构、输出规范
  training-library/         336 条动作库（资产、目录、能力、覆盖、剂量接口）
scripts/                    校验、渲染、导出、筛选
schemas/                    plan / change-set / swim-feedback 的 JSON Schema
assets/examples/            完整虚构示例计划（可跑通全部渲染）
assets/templates/           渲染模板
tests/                      211 项回归测试
```

## 环境

- Python 3.8+，**无第三方依赖**（仅标准库）
- 测试使用标准库 unittest：`python3 -m unittest discover -s tests -q`；也可选用 pytest。

## 快速开始

```sh
# 1. 校验计划（结构、时间、引用、当量）
python3 scripts/validate_plan.py plan.json

# 2. 渲染：总览 / 阶段 / 周 / 单次
python3 scripts/render_plan.py plan.json --view overall --output 总览.md
python3 scripts/render_plan.py plan.json --view block --block B1 --output 阶段.md
python3 scripts/render_plan.py plan.json --view week  --week 1  --output 周.md
python3 scripts/render_plan.py plan.json --view session --session W01-F1 --output 单次.md

# 3. 记录式周文档（一个文档 = 一周，末列留回填）
python3 scripts/render_weekly_log.py plan.json --week 1 --output 第1周训练计划.md

# 4. 整包导出
python3 scripts/export_plan.py plan.json --output-dir 课表/

# 5. 动作库筛选
python3 scripts/select_assets.py --family "水平推"
python3 scripts/select_assets.py --id trap_bar_deadlift
python3 scripts/validate_library.py
```

草案（尚未就绪的计划）加 `--draft`；不加会被拒绝，避免把未完善内容当执行版发出去。

试跑：`assets/examples/plan.json` 是完整虚构示例，校验 0 错误，可用上述全部命令验证。

## 计划格式

`plan.json`（`schema_version` 见 `schemas/plan.schema.json`）：

- `objectives` 目标与递进安排；`blocks` 阶段；`weeks` 周；`sessions` 单次课；每个动作是 `modules[].items[]` 里的一个工作项。
- `dose` 区分组数、次数、每侧、时长、距离、强度与恢复；`work_seconds_per_set` 是**完整一组**的秒数（已含两侧）。
- 配对/三联组用 `module.group_label` 与 `module.set_sequence` 表达逐组次序，不用文字声明代替结构。
- `design_context` 保存能力覆盖、有氧目标、DUP 主力波动、审查取舍与重返策略。
- 未知值写 `null`/`unknown`，不当 0 或 false；空日期不显示成休息日。

## 动作库

`references/training-library/` 下 336 条目录资产 / 362 条运行接口（302 动作＋60 单元）/ 11 项能力；目录内 286 动作＋50 单元，余下 16 动作与 10 单元为历史适配与课部件。

扩充条目必须同步六处，否则 `validate_library.py` 必报错：
① `assets-v3.json` 的 `assets`；② 同文件 `families[].entry_ids`；③ `catalog.json` 的 `entries`；
④ `exercises.json` / `training-units.json` 的 runtime 接口；⑤ `coverage.json` 各能力的 `operational_assets`；
⑥ 校验器与测试里的硬编码条数、`index.md` 与 `selection.md` 的条目数文字。

条目内不直接放书名、页码或 URL；蛙泳条目通过 `evidence_refs` 关联独立的 `references/swim-technique-evidence.json` 来源登记。

## 游泳接口与覆盖边界

- 当前支持已确认的 25 米或 50 米池；未知连续能力不默认 50 米。
- 蛙泳有 6 项条件下可排技术任务，2 项仅参考且不可排。静止技术任务用时长，不虚构游距。
- 距离任务逐 ID 核对掌握、器材、task readiness 与该任务连续距离，不从整泳或另一泳姿继承。
- `session.swim_focus` 保存本课目的与一个观察点。反馈区分完成、难度、技术保持与症状；未反馈不自动升级掌握。
- 尚未覆盖完整蛙泳耐力、速度、竞赛或康复方案。测试通过不构成医学许可、效果保证或设计审查通过。

## 技能与个人内容的分界

- **本包（技能）**：可复用的方法、动作库与默认剂量、编排策略、脚本、输出形态。不含任何具体人的可用时长、历史重量或剂量偏好。
- **计划文件（`plan.json`）**：某个人、某个周期的事实。
- **训练者的历史记录**：真实做过的重量（TR）优先取这里。

## 测试

```sh
python3 -m unittest discover -s tests -q
python3 scripts/validate_library.py
python3 scripts/check_links.py
python3 scripts/check_exercise_names.py
python3 scripts/validate_plan.py assets/examples/plan.json
```

## 变更记录

见本包版本号与 `references/` 各文件。

## 许可

原创代码与文档采用 [MIT](LICENSE)。MIT 不授予所引用第三方书籍、论文、图像或原始材料的额外权利，见 [第三方说明](THIRD_PARTY_NOTICES.md)。本包不提供原书、原图、私人记录或模型密钥。
