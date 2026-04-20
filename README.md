# Quest Agent - 故事驱动的目标追踪系统

将你的现实世界目标（健身、学习、工作等）映射为一段持续演进的中世纪奇幻冒险故事。每日任务完成推动剧情正向发展，未完成则遭遇挫折，用叙事的力量激励你达成目标。

## 快速开始

```bash
# 安装依赖
pip install -e .

# 配置 LLM API Key
# 编辑 config.yaml 或设置环境变量
export OPENAI_API_KEY="your-key-here"

# 查看所有可用命令
python -m src.main --help

# 开启新冒险（交互式，会一步步问你目标、职业、角色名）
python -m src.main new

# 每日签到（交互式，汇报每个任务的完成情况）
python -m src.main check-in

# 查看最新故事
python -m src.main story

# 查看角色面板 + 世界状态 + 当前任务
python -m src.main status

# 浏览所有历史章节
python -m src.main history

# 查看当前配置
python -m src.main config
```

## 命令一览

| 命令 | 说明 |
|------|------|
| `quest new` | 开启新冒险（设定目标、创建角色） |
| `quest check-in` | 每日进度汇报 |
| `quest story` | 阅读当前故事章节 |
| `quest status` | 查看角色面板、任务、世界状态 |
| `quest history` | 浏览历史章节 |
| `quest config` | 配置 LLM 提供商和 API 密钥 |

## 架构

基于 **LangChain** 框架构建，使用 LCEL（LangChain Expression Language）编排 LLM 调用链。

系统由 5 个协作智能体驱动：

- **GameMaster** - 总协调器，路由用户输入到各子智能体
- **TaskPlanner** - 将现实目标分解为每日任务（`ChatPromptTemplate | ChatOpenAI | JsonOutputParser`）
- **StoryTeller** - 生成中世纪奇幻风格叙事，可调用 `roll_dice` 工具
- **Evaluator** - 评估完成度并映射为故事走向
- **WorldBuilder** - 管理世界状态、NPC、地点

核心技术栈：
- **langchain-openai** / **langchain-core** — LLM 调用与 LCEL 链编排
- **ChromaDB** — 向量数据库持久化，支持语义相似度检索历史章节与关键线索
- **ChatPromptTemplate** — 提示词模板
- **JsonOutputParser** / **StrOutputParser** — 输出解析
- **StructuredTool** — 工具定义（骰子、角色属性、日历）
- **with_fallbacks** — 主模型失败时自动降级到备用模型

## 配置

编辑 `config.yaml` 切换 LLM 提供商：

```yaml
llm:
  provider: openai       # openai / anthropic / ollama
  model: gpt-4o          # 模型名称
  api_key_env: OPENAI_API_KEY
```
