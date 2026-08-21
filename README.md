# agent-kit

跨工具的多 Agent 协作层。一份权威源，装到任何项目或装到全局，
Cursor、Codex、Claude Code、OpenCode 读的是同一套工作流。

从 SmoothiewareRAG 抽出通用部分而来；领域相关的 Skill（检索循环、
回答审计、MFC 追踪等）留在原仓库，不进这里。

## 核心不变量

**`agents/skills/` 是工作流正文的唯一权威源。所有工具目录只做发现适配，不复制正文。**

任何一处复制都会造成漂移，而漂移是这套系统唯一会致命的失败模式，
所以 `scripts/validate_agent_system.py` 专门检查它。

```
agents/
  skills/
    decide-and-deliver/     个人决策与交付风格：审计输入、反驳一次、
                            最多三个会改变行动的问题、推进一个可逆的下一步
    decision-journal/       决策日志：结果未知前留快照，事后追加复盘，
                            区分决策质量与结果质量，五次以上才谈规律
  templates/
    task-contract.md        协调者内部填写，不要求用户填
    handoff.md              交接格式（落 commit message 或 PR 描述）
adapters/
  claude/skills/project-skill-router/   Claude Code 自动路由（薄指针）
  claude/commands/                      /decide-and-deliver 显式入口
  cursor/rules/                         Cursor always-apply 契约
  opencode/opencode.json                OpenCode 配置
docs/
  AGENTS.template.md        规则入口模板（项目自己填主线与验证命令）
  CLAUDE.template.md        Claude Code 入口
  CONTRIBUTING.template.md  并发模型、四种角色、标准工作流、完成定义
scripts/
  install.py                装进一个项目
  install_global.py         装进 ~/.claude（所有项目生效）
  validate_agent_system.py  漂移检查，可进 CI
```

## 两种装法

### 1. 全局（推荐日常用）

```powershell
python scripts\install_global.py
```

把每个 canonical Skill 复制到 `~/.claude/skills/`，并生成 `~/.claude/commands/`。
**所有项目立即可用，无需任何项目文件。** 装完重启 Claude Code。

只覆盖 Claude Code。Cursor / Codex / OpenCode 拿不到。

### 2. 项目（需要跨工具或项目级并发治理时）

```powershell
python scripts\install.py C:\path\to\project --dry-run   # 先看要动什么
python scripts\install.py C:\path\to\project
cd C:\path\to\project
python scripts\validate_agent_system.py
```

装入 `.agents/`、各工具适配层、验证器，并在项目**没有**
`AGENTS.md` / `CLAUDE.md` / `CONTRIBUTING.md` 时用模板播种（有则原样不动）。
`.agent-work/` 会追加进 `.gitignore`。

`--tools claude,cursor` 可只装部分适配层。

### 安全边界

装载脚本不覆盖项目已有内容：

- 内容相同 → 跳过；
- 内容不同 → 报 `CONFLICT` 并跳过，需要显式 `--force`；
- `AGENTS.md` / `opencode.json` 这类项目自有配置 → 只在缺失时播种。

所以对已经有自己 `.agents/skills/` 的项目（比如平台脚手架生成的），
装载是**合并**，不是替换。

## 两个 Skill 在干什么

**`decide-and-deliver`** —— 覆盖在任何任务之上的推理与沟通层：
把粘贴进来的其他 Agent 答案当作待审材料而非事实；区分事实 / 推断 / 未知；
用最强反驳测试一次当前判断，但不无限找盲点；只保留最多三个会改变本周行动的问题；
先诊断瓶颈再谈架构；给出最小可逆、能产生新证据的下一步，并写明什么证据会推翻它。

**`decision-journal`** —— 在结果已知**之前**留下可证伪的决策快照，
事后只追加复盘事件、绝不改写历史；把决策质量和结果质量分开评分
（好决策可能坏结果，坏决策可能走运）；少于五次复盘不谈"你有某种偏差"。
ledger 默认写在 git common dir 下，多个 worktree 共享同一份且永不被 git 跟踪。

## 更新

```powershell
git -C C:\path\to\agent-kit pull
python scripts\install_global.py --force
python scripts\install.py C:\path\to\project --force
```

改 Skill 只改 `agents/skills/` 下的正文，然后重装。
**不要**去改 `~/.claude/skills/` 或某个项目的 `.agents/`——那是副本，
下次重装会被覆盖，而且会让 `validate_agent_system.py` 报漂移。

## 验证

```powershell
python scripts\validate_agent_system.py     # 在装好的项目根目录运行
```

检查：canonical Skill 的 frontmatter 与目录名一致；
`.claude/commands/` 的 description 与 canonical SKILL.md 逐字一致；
router 没有抄任何 canonical 章节；opencode / cursor 适配器指向 `.agents/skills`；
`.agent-work/` 已被 gitignore。
