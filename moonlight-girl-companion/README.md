# moonlight-girl-companion

中文名称：午夜闺蜜文案生成 skill

`moonlight-girl-companion` 是一个面向 Codex 等 Agent 的内容生成 skill，用于自动创作适合微信公众号发布的午夜情感故事发布包。它默认从女性视角展开，面向中年女性读者，支持自主选题、故事生成、章节插图规划、真实封面图、真实章节插图、封面图 Prompt、质量验收、Goal 模式循环优化，并在最终输出中明确给出 `PASS` 或 `FAIL`。

> 说明：Agent 触发和执行入口是 `SKILL.md`。本 README 面向人类读者，用来快速理解目录结构、使用方式和维护要点。

## 适用场景

- 生成微信公众号午夜情感故事。
- 生成女性视角、中年女性、婚姻情感、家庭边界、自我觉醒类故事。
- 自动完成公众号文章正文、标题、描述、摘要、标题备选、文末深夜寄语、互动话题、更多文章入口、封面图、章节插图、封面图 Prompt、章节插图 Prompt。
- 在 Codex Goal 模式下循环执行生成、验收、修订，直到达到发布标准或输出失败原因。
- 用户没有明确主题时，由 Agent 自主选题并评分。

## 不适用场景

- 只需要一句标题、短文案或单张图片 Prompt，不需要完整故事发布包。
- 请求低俗、血腥、恶意惊悚、真实人物造谣、医疗法律定论等高风险内容。
- 要求直接发布、推广、绕过平台审核或替代人工审稿。

## 默认产物

调用该 skill 生成内容时，默认产出一个发布包目录，而不是单个 Markdown 文件。发布包默认包含：

1. `article.md`：可直接使用的公众号文章，含主标题、描述、完整正文、章节图片引用、文末深夜寄语、互动话题和更多文章入口。
2. `metadata.json`：公众号标题、描述、封面图路径、文章路径、章节插图路径。
3. `cover.png` 或同等格式封面图。
4. `images/chapter-01.png` 到 `images/chapter-05.png` 或同等格式章节插图。
5. `prompts/cover_prompt.md` 与 `prompts/illustration_prompts.md`。
6. `review_report.md`：质量验收报告。
7. `iteration_log.md`：Goal 模式迭代日志。
8. 文章正文中的自主选题报告、内容简报、故事设定卡、角色视觉设定卡、标题备选、公众号摘要、文末深夜寄语、互动话题、更多文章入口和最终 `PASS` 或 `FAIL` 状态。

只有 `.md` 文档、只有图片 Prompt、没有真实封面和章节插图文件时，不能输出 `PASS`。

## 工作模式

### 指定选题模式

当用户提供明确主题、人物设定、故事梗概、关键情节或素材时启用。Agent 必须保留用户给出的核心方向，只能优化标题、章节结构、人物细节、情绪路径、插图规划和 Prompt，不能擅自推翻原主题。

示例：

```text
请使用 moonlight-girl-companion skill，在 Goal 模式下循环优化，帮我生成一个可直接使用的微信公众号午夜情感故事发布包。主题是：一个中年女人在丈夫旧大衣里发现一把钥匙，由此揭开婚姻背后的秘密。要求女性视角，5 个章节，每章配真实插图和插图 Prompt，文章结尾依次添加深夜寄语、互动话题和进入更多文章的入口描述，包含 article.md、metadata.json、封面图、章节插图、标题、描述、质量验收报告和最终 PASS/FAIL。
```

### 自主选题模式

当用户没有提供明确主题，或只说“帮我自动生成一篇适合公众号发布的午夜情感故事”时启用。Agent 必须先生成 5 到 8 个候选选题并评分，最终选题不低于 80 分才允许进入正文创作。

示例：

```text
请使用 moonlight-girl-companion skill，在 Goal 模式下自动生成一个适合微信公众号发布的午夜情感故事发布包。你需要自主选题，生成 5 到 8 个候选选题并评分，选择最适合中年女性读者的选题，然后完成正文、文末深夜寄语、互动话题、更多文章入口、真实封面图、每章真实插图、封面图 Prompt、每章插图 Prompt、metadata.json、质量验收和循环修订。最终只有满足 Done Criteria 才能输出 PASS，否则输出 FAIL 和人工修改建议。
```

## Goal 模式流程

Goal 模式下，Agent 不应只生成一次内容，而应循环执行：

1. 判断是指定选题模式还是自主选题模式。
2. 自主选题模式下先生成候选选题、评分并选择最终选题。
3. 生成内容包初稿。
4. 锁定角色视觉设定卡、统一美术风格和统一色彩系统。
5. 生成真实封面图和真实章节插图；环境允许时可用 subagent 并行生成封面和各章节图。
6. 组装发布包目录，写入含文末深夜寄语、互动话题和更多文章入口的 `article.md`、`metadata.json`、图片、Prompt、验收报告和迭代日志。
7. 运行结构校验脚本。
8. 执行规则型质量验收。
9. 输出质量验收报告。
10. 判断是否通过 Hard Gate 和 Done Criteria。
11. 未通过时定位问题层级，生成修订计划。
12. 根据修订计划改写内容或补齐素材。
13. 再次校验和验收。
14. 最多循环 5 轮。
15. 最终输出 `PASS` 或 `FAIL`。

并行生成图片时，subagent 只能负责自己对应的图片文件和 Prompt 草稿，不能修改正文、角色设定或 metadata；主 Agent 必须统一回收检查一致性。

## 目录结构

```text
moonlight-girl-companion/
├── SKILL.md
├── README.md
├── references/
│   ├── acceptance_criteria.md
│   ├── goal_loop_protocol.md
│   ├── illustration_consistency_guide.md
│   ├── quality_checklist.md
│   ├── safety_and_compliance.md
│   ├── story_style_guide.md
│   └── topic_selection_guide.md
├── assets/
│   ├── article_output_template.md
│   ├── illustration_prompt_template.md
│   ├── iteration_log_template.md
│   ├── publish_metadata_template.json
│   ├── review_report_template.md
│   └── topic_selection_report_template.md
└── scripts/
    └── validate_article_package.py
```

## 文件说明

- `SKILL.md`：Agent 入口文件，包含触发描述、执行流程、默认参数、Goal 模式要求、Hard Gate 摘要和输出结构。
- `references/story_style_guide.md`：故事风格、叙事节奏、情绪基调和手机端阅读体验要求。
- `references/topic_selection_guide.md`：自主选题方向、候选选题字段、评分标准和通过标准。
- `references/illustration_consistency_guide.md`：角色视觉一致性、插图风格统一和章节分镜规则。
- `references/safety_and_compliance.md`：内容安全边界和合规处理原则。
- `references/quality_checklist.md`：质量评分维度、发布建议和 Goal 模式额外要求。
- `references/goal_loop_protocol.md`：Codex Goal 模式循环协议、修订优先级和停止条件。
- `references/acceptance_criteria.md`：最终验收标准、Done Criteria、Hard Gate 和 Soft Gate。
- `assets/*.md`：自主选题报告、文章输出、插图 Prompt、验收报告和迭代日志模板。
- `assets/publish_metadata_template.json`：发布包元数据模板。
- `scripts/validate_article_package.py`：发布包结构校验脚本，输出 JSON 格式的 `passed`、`errors`、`warnings`、`stats`。

## 校验脚本

生成发布包目录后，可运行：

```bash
python moonlight-girl-companion/scripts/validate_article_package.py <article-package-dir>
```

脚本也支持传入 `article.md` 路径，但仍会检查同目录下的 `metadata.json` 和图片资产。脚本会检查必要模块、章节数量、插图占位、插图 Prompt、角色一致性字段、自主选题字段、粗略中文字数、真实封面图、真实章节插图、正文图片引用、文末深夜寄语、互动话题、更多文章入口及其顺序。输出示例：

```json
{
  "passed": true,
  "errors": [],
  "warnings": [],
  "stats": {
    "chinese_chars": 3120,
    "chapter_count": 5,
    "illustration_placeholder_count": 5,
    "illustration_prompt_count": 5,
    "topic_candidate_count": 5,
    "metadata_present": true,
    "cover_image_count": 1,
    "chapter_image_file_count": 5,
    "markdown_image_reference_count": 5,
    "deep_night_message_present": true,
    "interaction_topic_present": true,
    "more_articles_entry_present": true,
    "ending_sections_order_valid": true
  }
}
```

脚本只做结构、素材和粗略字数检查，不能替代 `quality_checklist.md` 与 `acceptance_criteria.md` 中定义的质量验收。

## 安装到 Codex 全局

按 Codex user-scope skill 约定，可将整个目录复制到：

```text
$HOME/.agents/skills/moonlight-girl-companion
```

Windows 示例：

```powershell
Copy-Item -Recurse -Force .\moonlight-girl-companion "$env:USERPROFILE\.agents\skills\moonlight-girl-companion"
```

安装后如果 Codex 没有立刻识别新 skill，重启 Codex。

## 维护建议

- 修改触发场景时，优先更新 `SKILL.md` 的 frontmatter `description`。
- 修改验收规则时，同步检查 `references/quality_checklist.md`、`references/acceptance_criteria.md` 和 `scripts/validate_article_package.py`。
- 修改插图要求时，同步检查 `references/illustration_consistency_guide.md` 和 `assets/illustration_prompt_template.md`。
- 修改输出结构时，同步检查 `assets/article_output_template.md`、`assets/publish_metadata_template.json` 和校验脚本。
- 修改正文结尾、文末深夜寄语、互动话题、更多文章入口或公众号导流要求时，同步检查 `SKILL.md`、`references/story_style_guide.md`、`references/acceptance_criteria.md`、`assets/article_output_template.md`、`assets/review_report_template.md` 和校验脚本。
- 不要把真实用户隐私、账号密钥、未授权素材或不可公开资料写入 skill。

## 当前限制

- 校验脚本不理解全文语义，只能做结构、素材文件和粗略字数检查。
- 质量评分仍需要 Agent 按规则执行，不应只依赖脚本。
- Goal 模式循环质量取决于 Agent 是否严格读取上一轮验收报告并按问题层级修订。
- 如果当前 Agent 环境没有图片生成能力，skill 应输出 FAIL 并说明缺少真实封面或章节插图，不能把只有 Prompt 的内容包标记为可直接发布。
