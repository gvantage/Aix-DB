import asyncio
import json
import logging
import os
import time
import traceback
import uuid
from typing import Optional

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from agent.deepagent.tools.native_sql_tools import (
    set_native_datasource_info,
    sql_db_list_tables,
    sql_db_query,
    sql_db_query_checker,
    sql_db_schema,
)
from common.datasource_util import (
    DB,
    ConnectType,
    DatasourceConfigUtil,
    DatasourceConnectionUtil,
)
from common.llm_util import get_llm
from constants.code_enum import DataTypeEnum, IntentEnum
from model.db_connection_pool import get_db_pool
from services.datasource_service import DatasourceService
from services.user_service import add_user_record, decode_jwt_token

# Langfuse 延迟导入，仅在启用 tracing 时导入

logger = logging.getLogger(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))


class DeepAgent:
    """
    基于DeepAgents的Text-to-SQL智能体，支持多轮对话记忆
    """

    def __init__(self):
        # 全局checkpointer用于持久化所有用户的对话状态
        self.checkpointer = InMemorySaver()

        # 是否启用链路追踪
        self.ENABLE_TRACING = (
            os.getenv("LANGFUSE_TRACING_ENABLED", "false").lower() == "true"
        )

        # 存储运行中的任务
        self.running_tasks = {}

        # === 配置参数 ===
        # 降低递归限制，避免长时间运行和死循环
        # 400 太高，如果陷入循环会运行很长时间
        self.RECURSION_LIMIT = int(os.getenv("RECURSION_LIMIT", 100))

        # === 加载可用技能列表 ===
        self.available_skills = self._load_available_skills()

    def _load_available_skills(self):
        """加载所有可用的技能"""
        skills_dir = os.path.join(current_dir, "skills")
        skills = []
        if os.path.exists(skills_dir):
            for skill_dir in os.listdir(skills_dir):
                skill_path = os.path.join(skills_dir, skill_dir)
                if os.path.isdir(skill_path):
                    skill_file = os.path.join(skill_path, "SKILL.md")
                    if os.path.exists(skill_file):
                        try:
                            with open(skill_file, "r", encoding="utf-8") as f:
                                content = f.read()
                                # 解析 frontmatter
                                if content.startswith("---"):
                                    parts = content.split("---", 2)
                                    if len(parts) >= 3:
                                        frontmatter = parts[1]
                                        skill_info = {}
                                        for line in frontmatter.strip().split("\n"):
                                            if ":" in line:
                                                key, value = line.split(":", 1)
                                                skill_info[key.strip()] = (
                                                    value.strip().strip('"')
                                                )
                                        skill_info["name"] = skill_info.get(
                                            "name", skill_dir
                                        )
                                        skill_info["description"] = skill_info.get(
                                            "description", ""
                                        )
                                        skills.append(skill_info)
                        except Exception as e:
                            logger.warning(f"加载技能 {skill_dir} 失败: {e}")
        return skills

    @staticmethod
    def _create_response(
        content: str,
        message_type: str = "continue",
        data_type: str = DataTypeEnum.ANSWER.value[0],
    ) -> str:
        """封装响应结构"""
        res = {
            "data": {"messageType": message_type, "content": content},
            "dataType": data_type,
        }
        return "data:" + json.dumps(res, ensure_ascii=False) + "\n\n"

    def _create_sql_deep_agent(self, datasource_id: int = None):
        """创建并返回一个 text-to-SQL Deep Agent，支持所有数据源类型"""
        # 优先使用 datasource_id，如果提供则使用数据源
        if datasource_id:
            logger.info(f"使用数据源: {datasource_id}")
            db_pool = get_db_pool()
            with db_pool.get_session() as session:
                datasource = DatasourceService.get_datasource_by_id(
                    session, datasource_id
                )
                if not datasource:
                    raise ValueError(f"数据源 {datasource_id} 不存在")

                # 检查数据源连接类型
                db_enum = DB.get_db(datasource.type, default_if_none=True)

                # 获取 LLM 模型，使用18分钟超时（与前端保持一致）
                # 从环境变量读取或使用默认值
                llm_timeout = int(os.getenv("LLM_TIMEOUT", 18 * 60))
                model = get_llm(timeout=llm_timeout)
                logger.info(f"LLM 模型已创建，超时时间: {llm_timeout}秒 ({llm_timeout // 60}分钟)")

                if db_enum.connect_type == ConnectType.sqlalchemy:
                    # SQLAlchemy 驱动的数据库，使用 SQLDatabaseToolkit
                    logger.info(
                        f"数据源 {datasource_id} ({datasource.type}) 使用 SQLAlchemy 连接"
                    )

                    # 解密配置并构建连接 URI
                    config = DatasourceConfigUtil.decrypt_config(
                        datasource.configuration
                    )
                    uri = DatasourceConnectionUtil.build_connection_uri(
                        datasource.type, config
                    )

                    # 创建 SQLDatabase
                    db = SQLDatabase.from_uri(uri, sample_rows_in_table_info=3)

                    # 创建 SQL toolkit 并获取工具
                    toolkit = SQLDatabaseToolkit(db=db, llm=model)
                    sql_tools = toolkit.get_tools()
                else:
                    # 原生驱动的数据库，使用自定义工具
                    logger.info(
                        f"数据源 {datasource_id} ({datasource.type}) 使用原生驱动连接"
                    )

                    # 设置原生数据源信息（供工具使用）
                    set_native_datasource_info(
                        datasource_id, datasource.type, datasource.configuration
                    )

                    # 使用自定义 SQL 工具
                    sql_tools = [
                        sql_db_list_tables,
                        sql_db_schema,
                        sql_db_query,
                        sql_db_query_checker,
                    ]
        else:
            raise ValueError("必须提供数据源ID (datasource_id)")

        # 添加报告上传工具（从统一的 tools 目录加载）
        try:
            from .tools.upload_tool import (
                upload_html_file_to_minio,
                upload_html_report_to_minio,
            )

            upload_tools = [upload_html_report_to_minio, upload_html_file_to_minio]
            all_tools = sql_tools + upload_tools
            logger.info("报告上传工具已加载")
        except ImportError as e:
            logger.warning(f"报告上传工具导入失败: {e}，仅使用SQL工具")
            all_tools = sql_tools
        except Exception as e:
            logger.warning(f"报告上传工具加载失败: {e}，仅使用SQL工具")
            all_tools = sql_tools

        # 创建 Deep Agent
        agent = create_deep_agent(
            model=model,
            memory=[
                os.path.join(current_dir, "AGENTS.md")
            ],  # Agent identity and general instructions
            skills=[os.path.join(current_dir, "skills/")],  # Specialized workflows
            tools=all_tools,  # SQL database tools + upload tools
            backend=FilesystemBackend(root_dir=current_dir),  # Persistent file storage
        )

        return agent

    async def run_agent(
        self,
        query: str,
        response,
        session_id: Optional[str] = None,
        uuid_str: str = None,
        user_token=None,
        file_list: dict = None,
        datasource_id: int = None,
    ):
        """
        运行智能体，支持多轮对话记忆和实时思考过程输出
        :param query: 用户输入
        :param response: 响应对象
        :param session_id: 会话ID，用于区分同一轮对话
        :param uuid_str: 自定义ID，用于唯一标识一次问答
        :param file_list: 附件
        :param user_token: 用户令牌
        :param datasource_id: 数据源ID
        :return:
        """
        # 检查数据源ID
        if not datasource_id:
            error_msg = "❌ **错误**: 必须提供数据源ID (datasource_id)"
            await response.write(
                self._create_response(error_msg, "error", DataTypeEnum.ANSWER.value[0])
            )
            return

        # 获取用户信息 标识对话状态
        user_dict = await decode_jwt_token(user_token)
        task_id = user_dict["id"]
        task_context = {"cancelled": False}
        self.running_tasks[task_id] = task_context

        try:
            t02_answer_data = []

            # 使用用户会话ID作为thread_id，如果未提供则使用默认值
            thread_id = (
                session_id if session_id else f"sql-agent-{datasource_id}-{task_id}"
            )
            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": self.RECURSION_LIMIT,
            }

            # 准备 tracing 配置
            if self.ENABLE_TRACING:
                # 延迟导入，仅在启用时导入
                from langfuse.langchain import CallbackHandler

                langfuse_handler = CallbackHandler()
                callbacks = [langfuse_handler]
                config["callbacks"] = callbacks
                config["metadata"] = {"langfuse_session_id": session_id}

            # 发送开始消息（可选，根据需求决定是否显示）
            # start_msg = "🔍 **开始分析问题...**\n\n"
            # await response.write(self._create_response(start_msg, "info"))
            # t02_answer_data.append(start_msg)

            # 创建 SQL Deep Agent
            agent = self._create_sql_deep_agent(datasource_id)

            # 准备流式处理参数 - 使用 values 模式进行流式输出
            # values 模式会返回包含 messages 列表的 chunk，可以获取完整的消息历史
            stream_args = {
                "input": {"messages": [HumanMessage(content=query)]},
                "config": config,
                "stream_mode": "values",  # 使用 values 模式以获取完整的消息历史
            }

            # 如果启用 tracing，包裹在 trace 上下文中
            if self.ENABLE_TRACING:
                # 延迟导入，仅在启用时导入
                from langfuse import get_client

                langfuse = get_client()
                with langfuse.start_as_current_observation(
                    input=query,
                    as_type="agent",
                    name="Text-to-SQL",
                ) as rootspan:
                    user_info = await decode_jwt_token(user_token)
                    user_id = user_info.get("id")
                    rootspan.update_trace(session_id=session_id, user_id=user_id)
                    await self._stream_agent_response(
                        agent,
                        stream_args,
                        response,
                        task_id,
                        t02_answer_data,
                        uuid_str,
                        session_id,
                        query,
                        file_list,
                        user_token,
                        datasource_id,  # 传递数据源ID
                    )
            else:
                await self._stream_agent_response(
                    agent,
                    stream_args,
                    response,
                    task_id,
                    t02_answer_data,
                    uuid_str,
                    session_id,
                    query,
                    file_list,
                    user_token,
                    datasource_id,  # 传递数据源ID
                )

        except asyncio.CancelledError:
            # 协程被取消时的处理
            # 检查是否是用户主动取消
            is_user_cancelled = self._is_task_cancelled(task_id)
            if is_user_cancelled:
                logger.info(f"任务 {task_id} 的协程被取消 - 原因: 用户主动取消")
            else:
                logger.info(f"任务 {task_id} 的协程被取消 - 原因: 客户端连接断开或服务器关闭")
            try:
                await self._handle_task_cancellation(response, is_user_cancelled=is_user_cancelled)
            except Exception as e:
                # 如果是连接断开，静默处理
                if not self._is_connection_error(e):
                    logger.error(f"处理取消异常时出错: {e}", exc_info=True)
        except Exception as e:
            # 如果是连接断开，静默处理，不显示错误消息
            if self._is_connection_error(e):
                logger.info(f"客户端连接已断开（run_agent）: {type(e).__name__}: {e}")
            else:
                # 其他异常正常处理
                logger.error(f"Agent运行异常: {e}")
                traceback.print_exception(e)
                try:
                    error_msg = f"❌ **错误**: 智能体运行异常\n\n```\n{str(e)}\n```\n"
                    await self._safe_write(
                        response, error_msg, "error", DataTypeEnum.ANSWER.value[0]
                    )
                except Exception as write_error:
                    # 如果写入失败（可能是连接断开），记录日志但不抛出
                    if not self._is_connection_error(write_error):
                        logger.error(f"发送错误消息失败: {write_error}", exc_info=True)
        finally:
            # 清理任务记录
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]

    @staticmethod
    async def _send_step_progress(
        response,
        step: str,
        step_name: str,
        status: str,
        progress_id: str,
    ) -> None:
        """
        发送步骤进度信息（等待动画）
        :param response: 响应对象
        :param step: 步骤标识（英文）
        :param step_name: 步骤名称（中文）
        :param status: 状态（"start" 或 "complete"）
        :param progress_id: 进度ID（唯一标识）
        """
        if response:
            progress_data = {
                "type": "step_progress",
                "step": step,
                "stepName": step_name,
                "status": status,
                "progressId": progress_id,
            }
            formatted_message = {
                "data": progress_data,
                "dataType": DataTypeEnum.STEP_PROGRESS.value[0],
            }
            await response.write(
                "data:" + json.dumps(formatted_message, ensure_ascii=False) + "\n\n"
            )

    def _is_task_cancelled(self, task_id: str) -> bool:
        """
        检查任务是否已被取消
        :param task_id: 任务ID
        :return: 是否已取消
        """
        return (
            task_id in self.running_tasks
            and self.running_tasks[task_id].get("cancelled", False)
        )

    async def _stream_agent_response(
        self,
        agent,
        stream_args,
        response,
        task_id,
        t02_answer_data,
        uuid_str,
        session_id,
        query,
        file_list,
        user_token,
        datasource_id: int = None,
    ):
        """处理agent流式响应的核心逻辑 - 使用 values 模式进行流式输出"""
        # 深度搜索的等待动画由前端根据 qa_type 自动控制：
        # - 发送消息时显示动画
        # - 读取完成时隐藏动画
        # 无需后端发送 step_progress 事件

        start_time = time.time()
        printed_count = 0
        connection_closed = False
        
        logger.info(f"开始流式响应处理 - 任务ID: {task_id}, 查询: {query[:100]}")
        
        try:
            async for chunk in agent.astream(**stream_args):
                # 在处理每个 chunk 前检查是否已取消
                if self._is_task_cancelled(task_id):
                    await self._handle_task_cancellation(response, is_user_cancelled=True)
                    return

                # 处理消息流 - stream_mode="values" 返回包含 messages 列表的 chunk
                if "messages" in chunk:
                    messages = chunk["messages"]
                    if len(messages) > printed_count:
                        # 只处理新消息
                        for msg in messages[printed_count:]:
                            # 在处理每条消息前检查是否已取消
                            if self._is_task_cancelled(task_id):
                                await self._handle_task_cancellation(response, is_user_cancelled=True)
                                return
                            
                            # 尝试打印消息，如果连接已断开则停止
                            if not await self._print_message(
                                msg, response, t02_answer_data, task_id
                            ):
                                connection_closed = True
                                break
                        printed_count = len(messages)

                        # 如果连接已断开，退出循环
                        if connection_closed:
                            break

                        # 确保实时输出
                        if hasattr(response, "flush"):
                            try:
                                await response.flush()
                            except Exception as e:
                                if self._is_connection_error(e):
                                    logger.info(f"客户端连接已断开（flush）: {type(e).__name__}: {e}")
                                    connection_closed = True
                                    break
                                raise
                        await asyncio.sleep(0)
        except asyncio.CancelledError:
            # 协程被直接取消时的处理
            # 检查是否是用户主动取消
            is_user_cancelled = self._is_task_cancelled(task_id)
            if is_user_cancelled:
                logger.info(f"任务 {task_id} 的协程被取消 - 原因: 用户主动取消")
            else:
                logger.info(f"任务 {task_id} 的协程被取消 - 原因: 客户端连接断开或服务器关闭")
            try:
                await self._handle_task_cancellation(response, is_user_cancelled=is_user_cancelled)
            except Exception as e:
                logger.error(f"处理取消异常时出错: {e}", exc_info=True)
            raise
        except Exception as e:
            # 捕获所有其他异常，判断是否是连接断开
            if self._is_connection_error(e):
                logger.info(f"客户端连接已断开: {type(e).__name__}: {e}")
                connection_closed = True
                # 连接断开时不显示错误消息，静默处理
            else:
                # 检查是否是超时错误
                error_type = type(e).__name__
                error_msg = str(e).lower()
                is_timeout = (
                    "timeout" in error_msg
                    or "timed out" in error_msg
                    or error_type in ["TimeoutError", "asyncio.TimeoutError"]
                )
                
                if is_timeout:
                    logger.error(f"LLM 调用超时: {error_type}: {e}", exc_info=True)
                    try:
                        timeout_msg = (
                            "\n> ⚠️ **LLM 调用超时**\n\n"
                            "请求处理时间过长，可能的原因：\n"
                            "- 数据量较大，查询执行时间较长\n"
                            "- 网络连接不稳定\n"
                            "- 模型响应较慢\n\n"
                            "建议：\n"
                            "- 尝试简化查询条件\n"
                            "- 检查网络连接\n"
                            "- 稍后重试"
                        )
                        await self._safe_write(
                            response, timeout_msg, "error", DataTypeEnum.ANSWER.value[0]
                        )
                        await self._safe_write(
                            response, "", "end", DataTypeEnum.STREAM_END.value[0]
                        )
                    except Exception as write_error:
                        logger.error(f"发送超时错误消息失败: {write_error}", exc_info=True)
                else:
                    # 其他异常记录详细信息并通知用户
                    logger.error(f"Agent 流式响应异常: {error_type}: {e}", exc_info=True)
                    try:
                        error_msg = (
                            f"\n> ❌ **处理异常**\n\n"
                            f"错误类型: {error_type}\n"
                            f"错误信息: {str(e)[:200]}\n\n"
                            "请稍后重试，如问题持续存在请联系管理员。"
                        )
                        await self._safe_write(
                            response, error_msg, "error", DataTypeEnum.ANSWER.value[0]
                        )
                        await self._safe_write(
                            response, "", "end", DataTypeEnum.STREAM_END.value[0]
                        )
                    except Exception as write_error:
                        logger.error(f"发送错误消息失败: {write_error}", exc_info=True)
        finally:
            # 记录处理时间
            elapsed_time = time.time() - start_time
            logger.info(
                f"流式响应处理完成 - 任务ID: {task_id}, "
                f"耗时: {elapsed_time:.2f}秒 ({elapsed_time / 60:.2f}分钟), "
                f"连接状态: {'已断开' if connection_closed else '正常'}"
            )
            
            # 保存记录（安全访问，避免 KeyError）
            if not self._is_task_cancelled(task_id):
                try:
                    await add_user_record(
                        uuid_str,
                        session_id,
                        query,
                        t02_answer_data,
                        {},
                        IntentEnum.REPORT_QA.value[0],  # 使用深度搜索类型
                        user_token,
                        file_list,
                        datasource_id,  # 传递数据源ID
                    )
                except Exception as e:
                    logger.error(f"保存用户记录失败: {e}", exc_info=True)

    def _is_connection_error(self, exception: Exception) -> bool:
        """
        判断是否是连接断开相关的异常（非用户主动取消）
        :param exception: 异常对象
        :return: 是否是连接断开异常
        """
        error_type = type(exception).__name__
        error_msg = str(exception).lower()
        
        # 常见的连接断开异常类型
        connection_error_types = [
            "ConnectionClosed",
            "ConnectionResetError",
            "BrokenPipeError",
            "ConnectionError",
            "OSError",
        ]
        
        # 常见的连接断开错误消息关键词
        connection_error_keywords = [
            "connection closed",
            "connection reset",
            "broken pipe",
            "client disconnected",
            "connection aborted",
            "transport closed",
        ]
        
        # 检查异常类型
        if error_type in connection_error_types:
            return True
        
        # 检查错误消息
        for keyword in connection_error_keywords:
            if keyword in error_msg:
                return True
        
        return False

    async def _safe_write(self, response, content: str, message_type: str = "continue", data_type: str = None):
        """
        安全地写入响应，捕获连接断开异常
        :param response: 响应对象
        :param content: 内容
        :param message_type: 消息类型
        :param data_type: 数据类型
        :return: 是否写入成功
        """
        try:
            if data_type is None:
                data_type = DataTypeEnum.ANSWER.value[0]
            await response.write(self._create_response(content, message_type, data_type))
            if hasattr(response, "flush"):
                await response.flush()
            return True
        except Exception as e:
            # 如果是连接断开，记录日志但不抛出异常
            if self._is_connection_error(e):
                logger.info(f"客户端连接已断开: {type(e).__name__}: {e}")
                return False
            # 其他异常继续抛出
            raise

    async def _handle_task_cancellation(self, response, is_user_cancelled: bool = True):
        """
        处理任务取消的统一方法
        :param response: 响应对象
        :param is_user_cancelled: 是否是用户主动取消（True）还是连接断开（False）
        """
        try:
            if is_user_cancelled:
                message = "\n> ⚠️ 任务已被用户取消"
            else:
                message = "\n> ⚠️ 连接已断开，任务已中断"
            
            await self._safe_write(
                response, message, "info", DataTypeEnum.ANSWER.value[0]
            )
            await self._safe_write(
                response, "", "end", DataTypeEnum.STREAM_END.value[0]
            )
        except Exception as e:
            logger.error(f"发送取消消息失败: {e}", exc_info=True)

    async def _print_message(
        self, msg, response, t02_answer_data, task_id: str = None
    ) -> bool:
        """
        格式化并输出消息，包含思考过程和工具调用，使用美观的格式
        :param msg: 消息对象
        :param response: 响应对象
        :param t02_answer_data: 答案数据列表
        :param task_id: 任务ID，用于检查取消状态
        :return: 是否成功写入（False表示连接已断开）
        """
        # 在处理消息前检查是否已取消
        if task_id and self._is_task_cancelled(task_id):
            return False

        try:
            if isinstance(msg, HumanMessage):
                # 用户消息格式化为框格式
                content = msg.content if hasattr(msg, "content") else str(msg)
                if content and content.strip():
                    formatted_user_msg = self._format_user_message(content)
                    t02_answer_data.append(formatted_user_msg)
                    if not await self._safe_write(response, formatted_user_msg):
                        return False
            elif isinstance(msg, AIMessage):
                content = msg.content
                if isinstance(content, list):
                    # 处理多部分内容
                    text_parts = [
                        p.get("text", "")
                        for p in content
                        if isinstance(p, dict) and p.get("type") == "text"
                    ]
                    content = "\n".join(text_parts)

                # 输出 Agent 的思考过程（内容）- 使用框格式
                if content and content.strip():
                    # 再次检查取消状态（在输出内容前）
                    if task_id and self._is_task_cancelled(task_id):
                        return False
                    
                    # 确保内容格式美观，添加适当的换行
                    formatted_content = self._format_agent_content(content)
                    t02_answer_data.append(formatted_content)
                    if not await self._safe_write(response, formatted_content):
                        return False

                # 处理工具调用 - 在思考内容之后显示工具调用
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        # 在处理每个工具调用前检查是否已取消
                        if task_id and self._is_task_cancelled(task_id):
                            return False
                        
                        name = tc.get("name", "unknown")
                        args = tc.get("args", {})
                        
                        # 如果是上传工具，特别提示用户可能需要等待
                        if "upload" in name.lower() and "html" in name.lower():
                            # 在上传前再次检查取消状态
                            if task_id and self._is_task_cancelled(task_id):
                                return False
                        
                        tool_msg = self._format_tool_call(name, args)
                        if tool_msg:
                            if not await self._safe_write(response, tool_msg, "info"):
                                return False
                            t02_answer_data.append(tool_msg)
            elif isinstance(msg, ToolMessage):
                # 处理工具执行结果
                # 在处理工具结果前检查是否已取消
                if task_id and self._is_task_cancelled(task_id):
                    return False
                
                name = getattr(msg, "name", "")
                content_str = str(msg.content) if msg.content else ""
                tool_result_msg = self._format_tool_result(name, content_str)
                if tool_result_msg:
                    msg_type = "error" if "error" in content_str.lower() else "info"
                    if not await self._safe_write(response, tool_result_msg, msg_type):
                        return False
                    t02_answer_data.append(tool_result_msg)
            return True
        except Exception as e:
            # 如果是连接断开，返回False
            if self._is_connection_error(e):
                logger.info(f"写入消息时连接断开: {type(e).__name__}: {e}")
                return False
            # 其他异常重新抛出
            raise

    def _format_user_message(self, content: str) -> str:
        """格式化用户消息为 Markdown 格式"""
        if not content or not content.strip():
            return content

        content = content.strip()
        # 用户消息使用引用块格式，带图标
        return f"> 💬 **Question**\n> \n> {content}\n\n"

    def _format_agent_content(self, content: str) -> str:
        """格式化 Agent 的思考内容为 Markdown 格式"""
        if not content or not content.strip():
            return content

        content = content.strip()
        # Agent 思考内容，使用简洁的格式
        return f"🤖 {content}\n\n"

    def _format_tool_call(self, name: str, args: dict) -> str:
        """格式化工具调用信息为 Markdown 格式"""
        if name == "sql_db_query":
            query = args.get("query", "")
            formatted_query = query.strip()
            # 使用代码块显示 SQL
            return f"⚡ **Executing SQL**\n```sql\n{formatted_query}\n```\n\n"
        elif name == "sql_db_schema":
            table_names = args.get("table_names", "")
            if isinstance(table_names, list):
                table_names = ", ".join(table_names)
            if table_names:
                return f"🔍 **Checking Schema:** `{table_names}`\n\n"
            else:
                return f"🔍 **Checking Schema...**\n\n"
        elif name == "sql_db_list_tables":
            return f"📋 **Listing Tables...**\n\n"
        elif name == "sql_db_query_checker":
            return f"✅ **Validating Query...**\n\n"
        return None

    def _format_tool_result(self, name: str, content: str) -> str:
        """格式化工具执行结果为 Markdown 格式"""
        if "sql" in name.lower():
            if "error" not in content.lower():
                return f"✓ Query executed successfully\n\n"
            else:
                error_content = content[:300].strip()
                return f"✗ **Query failed:** {error_content}\n\n"
        return None

    async def cancel_task(self, task_id: str) -> bool:
        """
        取消指定的任务
        :param task_id: 任务ID
        :return: 是否成功取消
        """
        if task_id in self.running_tasks:
            self.running_tasks[task_id]["cancelled"] = True
            return True
        return False

    def get_running_tasks(self):
        """
        获取当前运行中的任务列表
        :return: 运行中的任务列表
        """
        return list(self.running_tasks.keys())

    def get_available_skills(self):
        """
        获取所有可用的技能列表
        :return: 技能列表
        """
        return self.available_skills
