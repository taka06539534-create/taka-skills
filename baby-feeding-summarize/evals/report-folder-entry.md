# Eval: 结果文件夹与 Markdown 入口

## Prompt

使用 `baby-feeding-summarize` 整理下面的新生儿喂养护理记录。用户没有额外要求图表或 `.md`，但 skill 仍应默认生成文件产物。

## Input

```text
【宝宝护理记录｜6月29日】

07:20 母乳：左12分/右10分
08:10 换尿不湿
09:30 奶粉：60ml
10:15 睡眠：入睡
```

## 成功标准

- 默认必须运行脚本；`--output-dir` 表示父级输出目录，不直接散放结果文件。
- 脚本每次创建一个新的报告文件夹，文件夹名包含记录日期，例如 `6月29日-baby-feeding-report`；同名已存在时追加序号，避免覆盖。
- 报告文件夹内至少包含 `index.md`、`baby-feeding-report.svg`、`baby-feeding-report.html`、`structured-data.json`，如果截图可用还包含 `baby-feeding-report.png`。
- `index.md` 是默认访问入口，正文中包含完整中文报告，并引用同文件夹内的 PNG 或 SVG 相对路径。
- 缺失日期时，文件夹名使用 `日期未记录` 或同义占位，并在 `index.md` 中继续提醒用户补充日期。
