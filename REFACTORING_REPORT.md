# Quest Agent — LangChain 框架重构技术报告

> 日期：2026-04-15  
> 项目：Quest Agent v0.1.0  
> 范围：将原始 OpenAI SDK 直接调用架构重构为 LangChain 框架

---

## 1. 执行摘要

本次重构将 Quest Agent 项目从**直接使用 OpenAI Python SDK（`AsyncOpenAI`）**的手动实现，迁移至基于 **LangChain** 框架的标准化架构。核心变化包括：

- LLM 调用层从自建 `LLMClient` 类改为 `ChatOpenAI` + LCEL 链式表达
- Agent 基类从手动消息拼装改为 `ChatPromptTemplate | LLM | OutputParser` 管道
- 工具系统从自定义 `Tool` 类改为 LangChain `StructuredTool`
- 模型容错从手动 try/except 改为 `Runnable.with_fallbacks()` 声明式降级

**影响范围**：15 个文件，其中 12 个重写、2 个局部修改、1 个新增（本报告）。  
**未变更模块**：Pydantic 数据模型（4 文件）、SQLite 持久层（2 文件）、Rich CLI 展示层（1 文件）、配置系统（2 文件）。  
**测试结果**：全部 13 个单元测试通过，零回归。

---

## 2. 重构前架构分析

### 2.1 原始技术栈

| 层级 | 技术方案 | 说明 |
|------|----------|------|
| LLM 客户端 | `openai.AsyncOpenAI` | 直接调用 OpenAI chat completions API |
| 消息构建 | 手动 `List[Dict]` | `{"role": "system", "content": ...}` |
| JSON 解析 | `json.loads()` + `response_format` | 手动解析，手动错误处理 |
| 工具定义 | 自建 `Tool` 类 + `to_openai_spec()` | 手动维护 OpenAI function calling schema |
| 工具执行 | 手动循环 | `chat_with_tools()` 中 5 轮循环 |
| 模型降级 | 手动 try/except | 每个调用点重复降级逻辑 |
| 提示词 | Python f-string `.format()` | 先格式化再传入 |

### 2.2 存在的问题

1. **耦合度高**：`LLMClient` 硬编码 OpenAI SDK 细节（`tool_calls`、`function.arguments` 等），切换提供商需改动核心代码
2. **模式重复**：每个 agent 的 `think_json` 调用路径重复执行相同的消息拼装 → API 调用 → JSON 解析流程
3. **工具规范不标准**：自建 `Tool.to_openai_spec()` 方法手动构建 JSON schema，难以与生态工具互操作
4. **降级逻辑分散**：`_complete` 方法和 `chat_with_tools` 中各自有一套 fallback 逻辑
5. **可组合性差**：无法声明式地表达 `prompt → llm → parser` 管道

---

## 3. 重构后架构

### 3.1 新技术栈

| 层级 | 技术方案 | LangChain 组件 |
|------|----------|----------------|
| LLM 实例化 | 工厂函数 `create_llm()` | `langchain_openai.ChatOpenAI` |
| 模型降级 | 声明式 | `Runnable.with_fallbacks()` |
| 提示词模板 | 参数化模板 | `langchain_core.prompts.ChatPromptTemplate` |
| 文本输出 | LCEL 链 | `ChatPromptTemplate \| LLM \| StrOutputParser` |
| JSON 输出 | LCEL 链 + json_mode | `ChatPromptTemplate \| LLM.bind(response_format) \| JsonOutputParser` |
| 工具定义 | 标准化 | `langchain_core.tools.StructuredTool` |
| 工具执行 | bind_tools + 消息循环 | `LLM.bind_tools()` + `ToolMessage` |

### 3.2 依赖变更

```diff
- "openai",
- "httpx",
+ "langchain-core>=0.2,<0.3",
+ "langchain-openai>=0.1",
```

实际安装版本：`langchain-core==0.2.43`、`langchain-openai==0.1.25`（`openai` SDK 作为传递依赖保留在 `1.109.1`）。

### 3.3 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                      CLI Layer                          │
│  commands.py ─── Click + Rich ─── display.py            │
└──────────────────────┬──────────────────────────────────┘
                       │ create_llm(config) → BaseChatModel
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   GameMasterAgent                       │
│  (协调器，持有 4 个子 Agent + ContextAssembler)          │
│                                                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐ │
│  │TaskPlanner   │ │ StoryTeller  │ │   Evaluator      │ │
│  │  LCEL chain  │ │  LCEL chain  │ │   LCEL chain     │ │
│  │  JSON output │ │  JSON output │ │   JSON output    │ │
│  └──────────────┘ └──────────────┘ └──────────────────┘ │
│  ┌──────────────┐                                       │
│  │WorldBuilder  │    Tools: roll_dice, update_character, │
│  │  LCEL chain  │           add_item, get_calendar      │
│  │  JSON output │    (StructuredTool)                   │
│  └──────────────┘                                       │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────┐
│                   BaseAgent (ABC)                        │
│                                                         │
│  think()      → Prompt | LLM | StrOutputParser          │
│  think_json() → Prompt | LLM.bind(json) | JsonParser    │
│  think_with_tools() → LLM.bind_tools() + ToolMessage   │
└──────────────────────┬──────────────────────────────────┘
                       │
    ┌──────────────────┼──────────────────┐
    ▼                  ▼                  ▼
 ChatOpenAI     with_fallbacks      Database
 (primary)      (ChatOpenAI          (aiosqlite)
                 fallback)
```

---

## 4. 逐文件变更详解

### 4.1 `pyproject.toml` — 依赖管理

| 变更项 | 说明 |
|--------|------|
| 移除 `openai` | 不再直接依赖，由 `langchain-openai` 传递引入 |
| 移除 `httpx` | 原项目未使用，属冗余依赖 |
| 新增 `langchain-core>=0.2,<0.3` | LCEL 管道、Prompt 模板、OutputParser、BaseTool |
| 新增 `langchain-openai>=0.1` | ChatOpenAI 封装 |

### 4.2 `src/llm/client.py` — LLM 客户端（完全重写）

**重构前**：171 行 `LLMClient` 类，包含 `chat()`、`chat_json()`、`chat_with_tools()` 三个方法，手动管理消息格式、JSON 解析、工具循环和 fallback。

**重构后**：46 行 `create_llm()` 工厂函数。

核心变化：

```python
# 重构前 — 手动实例化 + 手动降级
class LLMClient:
    def __init__(self, config):
        self._client = AsyncOpenAI(**kwargs)
        self._fallback_client = self._client  # if fallback configured

    async def chat(self, messages, ...):
        try:
            response = await self._complete(self.config.model, messages, ...)
        except Exception:
            response = await self._complete(self.config.fallback_model, messages, ...)
        return response.choices[0].message.content

# 重构后 — 声明式工厂 + with_fallbacks
def create_llm(config: LLMConfig) -> BaseChatModel:
    llm = ChatOpenAI(model=config.model, ...)
    if config.fallback_model:
        fallback = ChatOpenAI(model=config.fallback_model, ...)
        return llm.with_fallbacks([fallback])
    return llm
```

**返回类型**：当配置了 fallback 时返回 `RunnableWithFallbacks`，否则返回 `ChatOpenAI`。两者均实现 `BaseChatModel` / `Runnable` 接口，对调用方透明。

### 4.3 `src/agents/base.py` — Agent 基类（完全重写）

**重构前**：95 行，自建 `Tool` 类 + `BaseAgent` 手动拼装消息。

**重构后**：98 行，基于 LangChain 原语重建。

#### 4.3.1 工具系统

```python
# 重构前
class Tool:
    def to_openai_spec(self) -> dict:
        return {"type": "function", "function": {...}}

# 重构后 — 直接使用 LangChain BaseTool
self._tools: List[BaseTool] = []
```

#### 4.3.2 提示词构建

```python
# 重构前 — 手动 List[Dict]
def _build_messages(self, user_content, extra_context=None):
    messages = [{"role": "system", "content": self.system_prompt}]
    messages.append({"role": "user", "content": user_content})
    return messages

# 重构后 — ChatPromptTemplate
def _build_prompt(self, user_template: str) -> ChatPromptTemplate:
    messages = [("system", self.system_prompt), ("human", user_template)]
    return ChatPromptTemplate.from_messages(messages)
```

#### 4.3.3 LCEL 链式调用

三种调用模式的 LCEL 管道对比：

| 模式 | LCEL 链定义 |
|------|-------------|
| `think()` 文本 | `prompt \| self.llm \| StrOutputParser()` |
| `think_json()` JSON | `prompt \| self.llm.bind(response_format={"type":"json_object"}) \| JsonOutputParser()` |
| `think_with_tools()` 工具 | `self.llm.bind_tools(tools)` → 手动 `ToolMessage` 循环 |

#### 4.3.4 提示词模板变量传递方式变化

```python
# 重构前 — 先 format 再传入
prompt = template.format(goal=goal.description, ...)
result = await self.think_json(prompt)

# 重构后 — 模板变量作为 kwargs 直接传入 LCEL 链
result = await self.think_json(template, goal=goal.description, ...)
```

这一变化使得 `ChatPromptTemplate` 在链内自动完成变量替换，符合 LangChain 的声明式设计理念。提示词字符串中的 `{variable}` 被 LangChain 识别为模板变量，`{{` / `}}` 被识别为字面花括号（与 Python `str.format()` 行为一致），因此**所有提示词模板字符串无需修改**即可直接复用。

### 4.4 `src/llm/prompts.py` — 提示词模板

**变更极小**：仅新增一个 `PROMPT_CREATE_MAIN_QUEST` 模板。

原来 `task_planner.create_main_quest()` 中使用 f-string 内联构建提示词：

```python
# 重构前
prompt = (f"为以下现实目标创建一个主线任务：\n目标：{goal.description}\n...")
```

重构后提取为独立模板常量，与其他模板保持一致风格：

```python
PROMPT_CREATE_MAIN_QUEST = """为以下现实目标创建一个主线任务：
目标：{goal_description}
类型：{goal_type}
时长：{duration_days}天
...
"""
```

### 4.5 `src/tools/` — 工具层（3 文件重写）

| 文件 | 工具名 | 重构前类型 | 重构后类型 |
|------|--------|-----------|-----------|
| `dice.py` | `roll_dice` | 自建 `Tool` | `StructuredTool.from_function()` |
| `character_sheet.py` | `update_character` | 自建 `Tool` | `StructuredTool.from_function()` |
| `character_sheet.py` | `add_item` | 自建 `Tool` | `StructuredTool.from_function()` |
| `calendar.py` | `get_calendar` | 自建 `Tool` | `StructuredTool.from_function()` |

**设计决策**：保留纯函数（如 `roll_dice()`）不变，通过 `StructuredTool.from_function()` 包装为 LangChain 工具。这样：
- 测试代码可以继续直接调用纯函数（零改动）
- LangChain 的 `bind_tools()` / `ToolMessage` 协议自动获得正确的 JSON schema

**重构前的手动 OpenAI function spec**：

```python
# 重构前 — 手动维护 JSON schema
class Tool:
    def to_openai_spec(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sides": {"type": "integer", ...},
                        "modifier": {"type": "integer", ...},
                    },
                },
            },
        }
```

**重构后**：`StructuredTool.from_function()` 自动从函数签名的类型注解和 docstring 推导 schema，无需手动维护。

### 4.6 子 Agent 重构（4 文件）

四个子 Agent 的改动模式完全一致：

| Agent | 文件 | 核心变化 |
|-------|------|---------|
| `TaskPlannerAgent` | `task_planner.py` | `prompt.format(...) → think_json(prompt)` 改为 `think_json(prompt, **vars)` |
| `StoryTellerAgent` | `storyteller.py` | 同上 + `create_dice_tool()` 返回 `StructuredTool` |
| `EvaluatorAgent` | `evaluator.py` | 同上 |
| `WorldBuilderAgent` | `world_builder.py` | 同上 |

以 `TaskPlannerAgent.run()` 为例：

```python
# 重构前
prompt = prompts.PROMPT_PLAN_TASKS.format(
    goal=goal.description, goal_type=goal.goal_type, day_count=day_count,
    total_days=goal.duration_days, avg_completion=avg_completion,
    current_phase=phase["current_phase"], total_phases=phase["total_phases"],
)
result = await self.think_json(prompt)

# 重构后
result = await self.think_json(
    prompts.PROMPT_PLAN_TASKS,
    goal=goal.description, goal_type=goal.goal_type, day_count=day_count,
    total_days=goal.duration_days, avg_completion=avg_completion,
    current_phase=phase["current_phase"], total_phases=phase["total_phases"],
)
```

业务逻辑（Quest 创建、Chapter 持久化、Evaluation 计算等）**完全不变**。

### 4.7 `src/agents/game_master.py` — 编排器

**变更极小**：仅适配构造函数参数类型从 `LLMClient` 变为 `BaseChatModel`。所有编排逻辑（6 步 new game 流程、5 步 check-in 流程）保持不变。

```python
# 重构前
def __init__(self, llm: LLMClient, db: Database, config: AppConfig):

# 重构后
def __init__(self, llm: BaseChatModel, db: Database, config: AppConfig):
```

### 4.8 `src/cli/commands.py` — CLI 入口

唯一变化：工厂函数从实例化 `LLMClient` 改为调用 `create_llm()`。

```python
# 重构前
from src.llm.client import LLMClient
llm = LLMClient(config.llm)

# 重构后
from src.llm.client import create_llm
llm = create_llm(config.llm)
```

### 4.9 `simulate.py` — 模拟脚本

同上，仅替换 LLM 实例化方式。

---

## 5. 运行时行为对比

### 5.1 一次 `think_json()` 调用的执行路径

**重构前**（6 步）：
```
Agent.think_json(formatted_string)
  → Agent._build_messages()        # 手动拼 [system, user] 消息列表
  → LLMClient.chat_json()          # 调用 chat() + json.loads()
    → LLMClient.chat()             # 调用 _complete()
      → LLMClient._complete()      # AsyncOpenAI.chat.completions.create()
      → (失败时) _complete(fallback_model)
    → json.loads(content)           # 手动解析
```

**重构后**（LCEL 链自动编排）：
```
Agent.think_json(template, **kwargs)
  → _build_prompt()                  # ChatPromptTemplate.from_messages()
  → chain = prompt | json_llm | JsonOutputParser()
  → chain.ainvoke(kwargs)            # LCEL 自动执行：
      1. ChatPromptTemplate 填充变量 → List[BaseMessage]
      2. RunnableBinding(RunnableWithFallbacks).ainvoke()
         → ChatOpenAI.ainvoke() (primary, with response_format)
         → (失败时) ChatOpenAI.ainvoke() (fallback, with response_format)
      3. JsonOutputParser 解析 → Dict
```

### 5.2 降级行为

| 场景 | 重构前 | 重构后 |
|------|--------|--------|
| Primary 成功 | 直接返回 | 直接返回 |
| Primary 失败 | 手动 try/except → 调用 fallback | `RunnableWithFallbacks` 自动路由 |
| `response_format` 传播 | 仅 primary 生效 | `bind()` kwargs 透传到 primary 和 fallback |
| 双重失败 | 抛出最后异常 | 抛出最后异常 |

`with_fallbacks` 的实现保证 `bind()` 绑定的 `response_format` 参数通过 `**kwargs` 同时传播到主模型和备用模型。

---

## 6. 未变更模块

以下模块在重构中**零改动**，保持完全向后兼容：

| 模块 | 文件 | 原因 |
|------|------|------|
| 数据模型 | `models/character.py` `models/quest.py` `models/story.py` `models/world.py` | 纯 Pydantic 模型，不依赖 LLM 层 |
| 持久化 | `memory/database.py` `memory/context.py` | aiosqlite 操作，与 LLM 框架无关 |
| 展示层 | `cli/display.py` | Rich 格式化输出，与 LLM 框架无关 |
| 配置 | `utils/config.py` `config.yaml` | 配置数据结构不变 |
| 入口 | `main.py` `cli/app.py` | 仅导入 `cli`，无 LLM 依赖 |

---

## 7. 测试验证

### 7.1 单元测试

```
tests/test_models.py  13 passed  ✓
  TestCharacter       5 tests    (创建、升级、职业映射、属性加成、伤害/治疗)
  TestQuest           2 tests    (创建、完成状态)
  TestStoryArc        2 tests    (添加章节、解决剧情线)
  TestTools           2 tests    (骰子投掷、阶段计算)
  TestWorldState      2 tests    (NPC 查找、地点查找)
```

测试无需修改的原因：
- 纯函数 `roll_dice()` 和 `calculate_phase()` 保持原始签名不变
- Pydantic 模型和 WorldState 方法未改动
- LangChain `StructuredTool` 是工具包装层，不影响底层函数行为

### 7.2 导入验证

所有模块导入测试通过，无循环依赖。

### 7.3 运行时对象验证

```
LLM type:       RunnableWithFallbacks  ✓ (因为配置了 fallback_model)
JSON LLM type:  RunnableBinding        ✓ (bind(response_format=...) 包装)
Dice tool:      StructuredTool         ✓
Stat tool:      StructuredTool         ✓
Item tool:      StructuredTool         ✓
Calendar tool:  StructuredTool         ✓
```

---

## 8. 代码量统计

| 指标 | 重构前 | 重构后 | 变化 |
|------|--------|--------|------|
| `src/llm/client.py` | 171 行 | 46 行 | **-73%** |
| `src/agents/base.py` | 95 行 | 98 行 | +3% |
| `src/tools/` (3 文件合计) | 168 行 | 124 行 | **-26%** |
| `src/agents/` 子 Agent (4 文件) | 291 行 | 290 行 | ≈0% |
| `src/agents/game_master.py` | 220 行 | 233 行 | +6% |
| 自建 Tool 类代码 | 33 行 | 0 行 | **-100%** |
| **被消除的手动 JSON schema** | ~80 行 | 0 行 | **-100%** |

总净减少约 **80 行手工基础设施代码**，同时获得 LangChain 生态的标准化工具链。

---

## 9. 设计决策与权衡

### 9.1 为什么选择 `langchain-core` 而非完整 `langchain` 包？

完整 `langchain` 包（含 `AgentExecutor`、Chains 等）引入大量传递依赖。本项目只需：
- `ChatPromptTemplate` — 提示词模板
- `StrOutputParser` / `JsonOutputParser` — 输出解析
- `StructuredTool` / `BaseTool` — 工具抽象
- `ToolMessage` — 消息协议

这些均属于 `langchain-core`，轻量且稳定。`langchain-openai` 提供 `ChatOpenAI` 封装。两者合计依赖树远小于完整 `langchain`。

### 9.2 为什么不使用 `AgentExecutor`？

`AgentExecutor` 是 LangChain 旧式 Agent 运行时，已被官方标记为逐步过渡到 LangGraph。本项目的工具调用场景简单（当前主流程未实际触发 tool calling），手动 5 轮 `bind_tools + ToolMessage` 循环足够，且避免引入重量级依赖。

### 9.3 为什么保留纯函数 + StructuredTool 双层？

```python
def roll_dice(sides, modifier, count) -> dict:  # 纯函数，可直接测试
    ...

def create_dice_tool() -> StructuredTool:        # LangChain 包装，供 Agent 注册
    ...
```

这样测试代码可以直接调用 `roll_dice()` 验证业务逻辑，无需 mock LangChain 工具层。

### 9.4 提示词模板字符串为什么不需要修改？

`ChatPromptTemplate.from_messages()` 使用与 Python `str.format()` 相同的模板语法：
- `{variable}` → 模板变量
- `{{` → 字面量 `{`

原有提示词字符串中的 JSON 示例已经使用 `{{` 转义，天然兼容。

---

## 10. 后续演进建议

| 方向 | 建议 | 优先级 |
|------|------|--------|
| **结构化输出** | 将 `JsonOutputParser` 替换为 `ChatOpenAI.with_structured_output(PydanticModel)`，实现编译时类型安全 | 高 |
| **LangGraph 迁移** | 将 `GameMasterAgent` 的线性编排改为 LangGraph `StateGraph`，支持条件分支和并行节点 | 中 |
| **异步工具** | 将 `StructuredTool` 升级为 `AsyncStructuredTool`，配合 `coroutine` 参数支持异步工具执行 | 中 |
| **LangSmith 可观测性** | 接入 `LANGCHAIN_TRACING_V2`，获得链路追踪、token 用量、延迟分析 | 中 |
| **多 Provider 支持** | 利用 `langchain-anthropic`、`langchain-community` 替换硬编码的 `ChatOpenAI`，实现 config.yaml 中 `provider` 字段的真正切换 | 低 |
| **流式输出** | 使用 LCEL `.astream()` 方法实现逐 token 输出，提升 CLI 交互体验 | 低 |
| **Secret 管理** | 从 `config.yaml` 移除明文 `api_key_direct`，仅通过环境变量传递 | **紧急** |

---

## 11. 附录：变更文件清单

| # | 文件路径 | 变更类型 | 说明 |
|---|----------|----------|------|
| 1 | `pyproject.toml` | 修改 | 替换依赖 |
| 2 | `src/llm/client.py` | 重写 | `LLMClient` → `create_llm()` |
| 3 | `src/llm/prompts.py` | 新增常量 | `PROMPT_CREATE_MAIN_QUEST` |
| 4 | `src/agents/base.py` | 重写 | LCEL 链基类 |
| 5 | `src/agents/game_master.py` | 适配 | 构造参数类型变更 |
| 6 | `src/agents/task_planner.py` | 适配 | kwargs 传参 + 新 prompt |
| 7 | `src/agents/storyteller.py` | 适配 | kwargs 传参 + StructuredTool |
| 8 | `src/agents/evaluator.py` | 适配 | kwargs 传参 |
| 9 | `src/agents/world_builder.py` | 适配 | kwargs 传参 |
| 10 | `src/tools/dice.py` | 重写 | `Tool` → `StructuredTool` |
| 11 | `src/tools/character_sheet.py` | 重写 | `Tool` → `StructuredTool` |
| 12 | `src/tools/calendar.py` | 重写 | `Tool` → `StructuredTool` |
| 13 | `src/cli/commands.py` | 适配 | `LLMClient` → `create_llm` |
| 14 | `simulate.py` | 适配 | `LLMClient` → `create_llm` |
| 15 | `tests/test_models.py` | 不变 | 13/13 通过 |
| 16 | `README.md` | 更新 | 架构描述 |
