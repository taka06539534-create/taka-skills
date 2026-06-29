# 可视化报告数据规范

处理任何新生儿喂养护理记录时，默认先把原始记录整理成结构化 JSON，再使用 `scripts/render_visual_report.py` 生成文件产物；不要只在聊天中输出文本报告。

## 产物

脚本默认把 `--output-dir` 视为父级输出目录，并在其中创建一个新的报告文件夹。报告文件夹命名包含记录日期，默认格式为 `<记录日期>-<basename>`；同名已存在时追加序号，避免覆盖。

报告文件夹内生成：

- `index.md`：默认访问入口，只保留一个 `可视化图表` 小节，并把它作为统计/可视化视图放在文档最后；有 PNG 时嵌入 PNG 并链接 SVG，没有 PNG 时嵌入 SVG。
- `structured-data.json`：本次报告使用的结构化数据快照。
- `<basename>.svg`：主图表，可直接嵌入 Markdown。
- `<basename>.html`：包裹 SVG 的浏览器预览页，用于截图。
- `<basename>.png`：截图。仅在本地 Chrome/Edge/Chromium headless 可用，或后续通过浏览器/Chrome 插件生成时存在。

## 运行方式

```bash
python scripts/render_visual_report.py \
  --input structured-data.json \
  --output-dir output-parent \
  --basename baby-feeding-report \
  --screenshot auto
```

如果环境没有本地浏览器但有浏览器/Chrome 插件：

1. 先运行脚本生成报告文件夹及其中的 `index.md`、`report.svg`、`report.html`。
2. 用浏览器插件打开报告文件夹里的 `report.html`，优先使用 `file://`；不支持时用本地静态服务器打开 `localhost`。
3. 截图保存为与 SVG 同目录、同 basename 的 `report.png`。
4. 重新运行脚本并使用 `--screenshot never`，脚本会检测已存在的 `report.png` 并写入 `index.md`；或手动把 `![宝宝喂养可视化图表](report.png)` 放入 `## 可视化图表` 小节。

平台兼容说明：

- Codex 可使用 Browser/browser-use 或 Chrome 插件能力打开本地 HTML 并截图。
- Claude Code、OpenClaw 或其他 Agent 若有浏览器截图工具，也走同样的 HTML 截图流程。
- 没有截图能力时，不要阻塞任务；最终 Markdown 入口 `index.md` 的 `## 可视化图表` 小节至少必须嵌入 SVG，且放在文档最后。

## JSON 顶层结构

```json
{
  "title": "新生儿喂养可视化日报",
  "date": "6月27日",
  "summary": ["短句概览1", "短句概览2"],
  "report_markdown": "完整中文报告正文，包含今日概览、喂养分析、排便排尿分析、睡眠推测、观察优先级、信息缺口、统计视图。",
  "metrics": {},
  "reference": {},
  "feedings": [],
  "diapers": [],
  "sleep": [],
  "comparisons": []
}
```

`date` 只能来自原文或用户明确说明。没有日期时写 `日期未记录`；生成的 Markdown 需要提醒用户补充记录日期，不能使用系统日期或聊天日期代替。脚本会使用该字段生成报告文件夹名。

`report_markdown` 是最终 `index.md` 的正文主体。必须使用 `references/parsing-and-output.md` 的章节顺序生成；不要包含 `## 可视化图表`，该章节由脚本追加到文档最后。

## metrics

| 字段 | 类型 | 含义 |
|---|---|---|
| `bottle_total_ml` | number | 瓶喂母乳 + 奶粉总量 |
| `bottle_breastmilk_ml` | number | 瓶喂母乳总量 |
| `formula_ml` | number | 奶粉/配方奶总量 |
| `direct_feeding_count` | number | 亲喂次数 |
| `direct_total_min` | number | 亲喂总分钟数 |
| `wet_diapers` | number | 明确或按换尿布规则推定的小便次数 |
| `stool_count` | number | 明确大便次数 |
| `sleep_sessions` | number | 入睡记录次数 |

## feedings

```json
{
  "time": "03:09",
  "type": "bottle_breastmilk",
  "amount_ml": 70,
  "duration_min": null,
  "note": "吐一口奶"
}
```

`type` 可用值：

- `direct_breastfeeding`
- `bottle_breastmilk`
- `formula`
- `unknown_bottle`

亲喂使用 `duration_min`，瓶喂使用 `amount_ml`。不要把亲喂换算为 ml。

## diapers

```json
{
  "time": "21:24",
  "urine": true,
  "stool": true,
  "note": "黄色糊状，少量奶瓣，量多"
}
```

`urine` / `stool` 使用：

- `true`：明确有，或换尿布相关描述未明确写大便有时按项目口径推定小便。
- `false`：明确无；但换尿布相关事件不能因“小便无/大便无”直接写 `urine: false`，应先应用默认小便口径。
- `null`：非换尿布事件且尿便信息无法判断。只记录换尿不湿、换尿布、换纸尿裤时不要写 `null`，按项目口径记小便。

## sleep

```json
{
  "start": "03:20",
  "end": "06:20",
  "confidence": "estimated"
}
```

`confidence` 可用值：

- `exact`：原文明确入睡和醒来。
- `estimated`：用下一条护理/喂养记录作为上限。
- `start_only`：只有入睡时间。

不要把 `estimated` 写成真实睡眠总时长。

## comparisons

```json
{
  "indicator": "湿尿布",
  "value": "换尿布口径统计 3 次",
  "reference": "出生 4-5 天后常见至少 5-6 次/日",
  "status": "记录不足",
  "note": "未写大便的换尿布已按小便计入"
}
```

`status` 避免使用“正常/异常”，优先使用：

- `接近参考`
- `记录不足`
- `需结合日龄观察`
- `无法判断`
- `建议咨询医生`
