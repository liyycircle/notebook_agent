import os
from typing import Dict, Any

# ============= 基础配置 =============

# DeepSeek配置
OPENAI_CONFIG = {
    "model": "deepseek-chat",
    "api_key": "sk-0003fa142e07463aa6114176e9516bd6",
    "base_url": "https://api.deepseek.com",
    "temperature": 0.0,
}

# 系统配置
SYSTEM_CONFIG = {
    "output_directory": "/home/mw/project",
    "max_file_size": 10 * 1024 * 1024,  # 10MB
}

# LangSmith追踪配置
LANGSMITH_CONFIG = {
    "tracing_enabled": True,  # 是否启用追踪
    "project_name": "programming-assistant",  # 项目名称
    "api_key": os.getenv("LANGCHAIN_API_KEY", "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"),  # LangSmith API Key
    "endpoint": os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),  # LangSmith端点
    "session_name": "notebook-agent-session",  # 会话名称
}

# # ============= Agent配置 =============

# # Supervisor Agent配置
# SUPERVISOR_CONFIG = {
#     "name": "supervisor",
#     "model": OPENAI_CONFIG["model"],
#     "temperature": OPENAI_CONFIG["temperature"],
#     "prompt": """你是编程助手系统的监督者，协调两个专业代理：

# 1. CodingAgent：代码生成
# 2. NotebookAgent：Notebook有关的所有任务（创建、读取、添加、修改等等）

# 工具：
# - assign_to_coding_agent：分配编程任务
# - assign_to_notebook_agent：分配Notebook任务
# - request_user_action：用户交互

# 工作原则：
# - 如果是简单的问题直接回答，如果是工作任务首先分解步骤
# - 根据上下文判断
# - 纯代码生成/优化 → CodingAgent
# - Notebook相关（创建、管理、代码生成、代码修复） → NotebookAgent
# - 任务完成后总结，避免重复分配
# - 必要时询问用户"""
# }

# # CodingAgent配置
# CODING_AGENT_CONFIG = {
#     "name": "coding_agent",
#     "model": OPENAI_CONFIG["model"],
#     "temperature": OPENAI_CONFIG["temperature"],
#     "prompt": """你是Python编程专家，专注于生成高质量代码。

# 工作模式：
# 1. **生成代码**：根据需求和上下文生成相应代码
# 2. **返回适当的agent**：根据任务来源返回

# 判断和返回逻辑：
# - 如果任务来自NotebookAgent（包含Notebook上下文、文件名、单元格信息等）→ 使用assign_to_notebook_agent返回
# - 如果任务来自Supervisor（纯代码生成请求，无Notebook上下文）→ 使用return_to_supervisor返回

# 判断标准：
# - 有"上下文"、"可用变量"信息 → 基于状态生成代码
# - 无状态信息 → 生成完整独立代码（包含导入、数据加载等）

# 代码生成要求：
# - 简洁、有注释、易理解
# - 考虑错误处理和边界情况
# - 如果在Jupyter环境中，多使用print输出以便分析结果
# - 只返回代码，不添加多余解释

# 完成代码生成后，立即使用相应的工具返回到调用方，不要停留。"""
# }

# # NotebookAgent配置
# NOTEBOOK_AGENT_CONFIG = {
#     "name": "notebook_agent",
#     "model": OPENAI_CONFIG["model"],
#     "temperature": OPENAI_CONFIG["temperature"],
#     "prompt": """你是Jupyter Notebook专家，管理有状态的Notebook环境。

# 核心分工：
# - Notebook管理：创建、读取、添加、修改、用户交互
# - 代码生成：转交给CodingAgent

# 工具：
# - create_notebook（创建notebook）
# - add_cell（添加cell）
# - read_notebook（读取notebook内容）
# - update_cell_by_id（通过ID更新修改cell内容）
# - request_user_action（请求用户执行代码/提供反馈）
# - assign_to_coding_agent（代码生成/修复）

# 转交CodingAgent格式：
# "请为Notebook生成代码：
# 上下文：[已运行的关键代码和输出结果] 
# 需求：[具体编程任务]
# 错误：[如果是修复任务，提供错误信息和cell信息]

# 注意：这是Jupyter Notebook环境任务，请生成代码后返回NotebookAgent处理后续工作流。"

# 工作流程：
# 基于上下文和任务类型灵活选择：
# - 创建新notebook：直接create_notebook
# - 简单查询/一般问题：直接输出结果
# - 需要了解当前状态：read_notebook后决定下一步
# - 生成/修改代码：read_notebook → assign_to_coding_agent → add_cell/update_cell_by_id → request_user_action
# - 任务完成或需要用户反馈：request_user_action

# 数据分析工作流：
# - 处理数据文件时，先生成探索性代码（数据形状、列名、统计信息、前N行等）
# - 让用户执行后，读取输出结果，再生成针对性的分析代码
# """
# }

# ============= 工具函数 =============

def get_config(config_name: str) -> Dict[str, Any]:
    """获取配置"""
    configs = {
        # "supervisor": SUPERVISOR_CONFIG,
        # "coding_agent": CODING_AGENT_CONFIG,
        # "notebook_agent": NOTEBOOK_AGENT_CONFIG,
        "system": SYSTEM_CONFIG,
        "openai": OPENAI_CONFIG,
        "langsmith": LANGSMITH_CONFIG,
    }
    return configs.get(config_name, {})

def setup_langsmith_tracing():
    """设置LangSmith追踪环境变量"""
    langsmith_config = get_config("langsmith")
    
    if langsmith_config.get("tracing_enabled", False):
        # 设置LangSmith追踪相关环境变量
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = langsmith_config.get("project_name", "programming-assistant")
        
        # 如果配置了API Key，则设置
        api_key = langsmith_config.get("api_key", "")
        if api_key:
            os.environ["LANGCHAIN_API_KEY"] = api_key
        
        # 设置端点（如果不是默认值）
        endpoint = langsmith_config.get("endpoint", "")
        if endpoint and endpoint != "https://api.smith.langchain.com":
            os.environ["LANGCHAIN_ENDPOINT"] = endpoint
            
        print(f"✅ LangSmith追踪已启用 - 项目: {langsmith_config.get('project_name')}")
        return True
    else:
        print("❌ LangSmith追踪已禁用")
        return False

def validate_environment() -> bool:
    """验证环境配置"""
    # 使用内置的API密钥，不需要环境变量验证
    setup_langsmith_tracing()
    return True


def setup_output_directory():
    """设置输出目录"""
    output_dir = SYSTEM_CONFIG["output_directory"]
    os.makedirs(output_dir, exist_ok=True)
    return output_dir 