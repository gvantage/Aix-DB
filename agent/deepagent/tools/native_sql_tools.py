"""
原生驱动数据源的 SQL 工具
用于支持 starrocks、doris 等使用原生驱动的数据源

重构说明：
- 使用会话级工具调用管理器替代全局变量
- 解决多会话间状态污染问题
- 增强循环检测和早期终止机制
"""

import asyncio
import logging
import re
from typing import Optional

from langchain_core.tools import tool

from common.datasource_util import (
    DatasourceConfigUtil,
    DatasourceConnectionUtil,
)
from model.db_connection_pool import get_db_pool
from model.datasource_models import DatasourceTable, DatasourceField

from .tool_call_manager import (
    get_tool_call_manager,
)

logger = logging.getLogger(__name__)

# 数据源信息存储（使用模块级全局变量，因为 langchain 工具在不同上下文中执行）
# 注意：这在单用户单会话场景下是安全的
from dataclasses import dataclass


@dataclass
class DatasourceInfo:
    """数据源信息"""
    datasource_id: Optional[int] = None
    datasource_type: Optional[str] = None
    datasource_config: Optional[str] = None
    session_id: Optional[str] = None  # 添加会话ID


# 模块级全局变量
_current_datasource: DatasourceInfo = DatasourceInfo()


def set_native_datasource_info(
    datasource_id: int, 
    datasource_type: str, 
    datasource_config: str,
    session_id: Optional[str] = None
):
    """设置原生数据源信息"""
    global _current_datasource
    _current_datasource = DatasourceInfo(
        datasource_id=datasource_id,
        datasource_type=datasource_type,
        datasource_config=datasource_config,
        session_id=session_id or f"datasource_{datasource_id}",
    )
    logger.info(f"设置数据源信息: ID={datasource_id}, Type={datasource_type}, Session={_current_datasource.session_id}")


def _get_datasource_info() -> tuple[Optional[int], Optional[str], Optional[str]]:
    """获取当前数据源信息"""
    return (
        _current_datasource.datasource_id, 
        _current_datasource.datasource_type, 
        _current_datasource.datasource_config
    )


def _get_session_id() -> str:
    """获取当前会话ID"""
    if _current_datasource.session_id:
        return _current_datasource.session_id
    if _current_datasource.datasource_id:
        return f"datasource_{_current_datasource.datasource_id}"
    return "default"


def _get_table_info_from_metadata() -> dict:
    """从元数据表获取表结构信息"""
    datasource_id, _, _ = _get_datasource_info()
    if not datasource_id:
        return {}
    
    db_pool = get_db_pool()
    table_info = {}
    
    try:
        with db_pool.get_session() as session:
            # 获取该数据源下所有已勾选的表
            tables = session.query(DatasourceTable).filter(
                DatasourceTable.ds_id == datasource_id,
                DatasourceTable.checked == True
            ).all()
            
            # 获取所有表的字段
            table_ids = [t.id for t in tables]
            fields = session.query(DatasourceField).filter(
                DatasourceField.ds_id == datasource_id,
                DatasourceField.table_id.in_(table_ids),
                DatasourceField.checked == True
            ).all()
            
            # 按表ID分组字段
            fields_by_table = {}
            for field in fields:
                if field.table_id not in fields_by_table:
                    fields_by_table[field.table_id] = []
                fields_by_table[field.table_id].append(field)
            
            # 构建表信息
            for table in tables:
                table_fields = fields_by_table.get(table.id, [])
                if not table_fields:
                    continue
                
                columns = {}
                for field in table_fields:
                    columns[field.field_name] = {
                        "type": field.field_type or "",
                        "comment": field.custom_comment or field.field_comment or "",
                    }
                
                table_info[table.table_name] = {
                    "columns": columns,
                    "foreign_keys": [],  # 原生驱动暂不支持外键信息
                    "table_comment": table.custom_comment or table.table_comment or "",
                }
    except Exception as e:
        logger.error(f"从元数据获取表结构失败: {e}", exc_info=True)
    
    return table_info


def _check_tool_call(tool_name: str, query: Optional[str] = None) -> tuple[bool, str]:
    """
    检查工具调用是否允许
    
    Returns:
        tuple[bool, str]: (是否允许, 如果不允许则返回原因)
    """
    session_id = _get_session_id()
    manager = get_tool_call_manager()
    return manager.check_before_call(session_id, tool_name, query)


def _record_tool_call(tool_name: str, success: bool, query: Optional[str] = None) -> None:
    """记录工具调用"""
    session_id = _get_session_id()
    manager = get_tool_call_manager()
    manager.record_call(session_id, tool_name, success, query)
    logger.debug(f"记录工具调用: tool={tool_name}, success={success}, session={session_id}")


@tool
def sql_db_list_tables() -> str:
    """列出数据库中的所有表名。"""
    datasource_id, _, _ = _get_datasource_info()
    if not datasource_id:
        return "错误: 未设置数据源信息"
    
    # 检查是否允许调用
    allowed, reason = _check_tool_call("sql_db_list_tables")
    if not allowed:
        return reason
    
    try:
        table_info = _get_table_info_from_metadata()
        table_names = list(table_info.keys())
        
        if not table_names:
            _record_tool_call("sql_db_list_tables", True)
            return "数据库中没有表"
        
        _record_tool_call("sql_db_list_tables", True)
        
        # 格式化输出，包含表注释
        result_lines = ["数据库中有以下表：\n"]
        for table_name in table_names:
            comment = table_info[table_name].get("table_comment", "")
            if comment:
                result_lines.append(f"- {table_name}: {comment}")
            else:
                result_lines.append(f"- {table_name}")
        
        result_lines.append("\n✅ 表列表已获取完成。如需查看表结构，请使用 sql_db_schema 工具。")
        return "\n".join(result_lines)
        
    except Exception as e:
        _record_tool_call("sql_db_list_tables", False)
        logger.error(f"列出表失败: {e}", exc_info=True)
        return f"列出表失败: {str(e)[:100]}"


@tool
def sql_db_schema(table_names: str) -> str:
    """
    获取指定表的架构信息。
    
    Args:
        table_names: 表名，可以是单个表名或多个表名（用逗号分隔）
    """
    datasource_id, _, _ = _get_datasource_info()
    if not datasource_id:
        return "错误: 未设置数据源信息"
    
    # 检查是否允许调用
    allowed, reason = _check_tool_call("sql_db_schema")
    if not allowed:
        return reason
    
    try:
        table_info = _get_table_info_from_metadata()
        
        # 解析表名（支持逗号分隔的多个表名）
        if isinstance(table_names, str):
            table_list = [t.strip() for t in table_names.split(",")]
        else:
            table_list = [table_names]
        
        schema_parts = []
        for table_name in table_list:
            if table_name not in table_info:
                schema_parts.append(f"表 '{table_name}' 不存在")
                continue
            
            info = table_info[table_name]
            columns = info.get("columns", {})
            table_comment = info.get("table_comment", "")
            
            schema_text = f"\n表 '{table_name}':"
            if table_comment:
                schema_text += f"\n注释: {table_comment}"
            
            schema_text += "\n列:"
            for col_name, col_info in columns.items():
                col_type = col_info.get("type", "")
                col_comment = col_info.get("comment", "")
                schema_text += f"\n  - {col_name} ({col_type})"
                if col_comment:
                    schema_text += f" - {col_comment}"
            
            schema_parts.append(schema_text)
        
        _record_tool_call("sql_db_schema", True)
        
        result = "\n".join(schema_parts) if schema_parts else "未找到表信息"
        result += "\n\n✅ 表架构已获取完成。请基于此信息编写 SQL 查询，无需重复获取架构。"
        return result
        
    except Exception as e:
        _record_tool_call("sql_db_schema", False)
        logger.error(f"获取表架构失败: {e}", exc_info=True)
        return f"获取表架构失败: {str(e)[:100]}"


@tool
def sql_db_query(query: str) -> str:
    """
    执行 SQL SELECT 查询并返回结果。
    只允许执行 SELECT 查询，不允许执行 INSERT、UPDATE、DELETE、DROP 等操作。
    
    Args:
        query: 要执行的 SQL 查询语句
    """
    datasource_id, datasource_type, datasource_config = _get_datasource_info()
    
    if not datasource_id or not datasource_type or not datasource_config:
        return "错误: 未设置数据源信息"
    
    # 安全检查：只允许 SELECT 查询
    query_upper = query.strip().upper()
    forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]
    for keyword in forbidden_keywords:
        if keyword in query_upper:
            return f"错误: 不允许执行 {keyword} 操作，只允许 SELECT 查询"
    
    if not query_upper.startswith("SELECT"):
        return "错误: 只允许执行 SELECT 查询"
    
    # 检查是否允许调用（包含重复查询检测）
    allowed, reason = _check_tool_call("sql_db_query", query)
    if not allowed:
        return reason
    
    logger.info(f"执行 SQL 查询（数据源类型: {datasource_type}）:\n{query[:500]}")
    
    try:
        # 解密配置
        config = DatasourceConfigUtil.decrypt_config(datasource_config)
        
        # 执行查询（添加超时控制）
        result_data = DatasourceConnectionUtil.execute_query(
            datasource_type, config, query
        )
        
        # 记录成功的调用
        _record_tool_call("sql_db_query", True, query)
        
        if not result_data:
            return "✅ 查询成功执行，但没有返回数据。"
        
        # 格式化结果（限制返回行数，避免输出过长）
        max_rows = 50
        result_rows = result_data[:max_rows]
        
        # 构建结果字符串
        if len(result_data) > max_rows:
            result_str = f"✅ 查询成功，返回 {len(result_data)} 行数据（显示前 {max_rows} 行）:\n\n"
        else:
            result_str = f"✅ 查询成功，返回 {len(result_data)} 行数据:\n\n"
        
        # 格式化表格输出
        if result_rows:
            columns = list(result_rows[0].keys())
            
            # 计算每列的最大宽度（限制最大宽度避免过宽）
            col_widths = {}
            for col in columns:
                col_widths[col] = min(
                    max(len(str(col)), max(len(str(row.get(col, ""))[:50]) for row in result_rows)),
                    50
                )
            
            # 构建表头
            header = " | ".join(str(col).ljust(col_widths[col]) for col in columns)
            separator = "-" * min(len(header), 200)
            result_str += header + "\n" + separator + "\n"
            
            # 构建数据行
            for row in result_rows:
                row_str = " | ".join(
                    str(row.get(col, ""))[:50].ljust(col_widths[col]) 
                    for col in columns
                )
                result_str += row_str + "\n"
        
        result_str += "\n✅ 查询已完成。请基于以上结果进行分析，无需重复执行相同查询。"
        return result_str
        
    except Exception as e:
        _record_tool_call("sql_db_query", False, query)
        error_msg = str(e)
        
        # 针对 StarRocks/Doris 的特殊错误处理
        if datasource_type in ("starrocks", "doris"):
            concise_error = _handle_starrocks_error(error_msg, query)
            if concise_error:
                logger.error(f"SQL 查询失败: {error_msg[:200]}")
                return concise_error
        
        # 通用错误处理：返回简洁的错误信息
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        
        logger.error(f"SQL 查询失败: {error_msg}")
        return (
            f"SQL 执行失败: {error_msg}\n\n"
            "请检查 SQL 语法和表结构是否正确。"
            "如果之前已获取表架构，请直接使用已有信息，无需重复查询。"
        )


def _handle_starrocks_error(error_msg: str, query: str) -> Optional[str]:
    """处理 StarRocks/Doris 特殊错误"""
    error_lower = error_msg.lower()
    
    # 检查列无法解析的错误
    if "cannot be resolved" in error_lower:
        column_match = re.search(r"Column\s+['`]([^'`]+)['`]", error_msg, re.IGNORECASE)
        column_name = column_match.group(1) if column_match else "未知列"
        
        # 分析 SQL，提取表别名信息
        table_aliases = set()
        alias_pattern = r"FROM\s+[`]?(\w+)[`]?\s+(\w+)|JOIN\s+[`]?(\w+)[`]?\s+(\w+)"
        matches = re.findall(alias_pattern, query, re.IGNORECASE)
        for match in matches:
            if match[1]:
                table_aliases.add(match[1])
            if match[3]:
                table_aliases.add(match[3])
        
        return (
            f"SQL 执行失败: 列 '{column_name}' 无法解析。\n"
            f"已定义的表别名: {', '.join(sorted(table_aliases)) if table_aliases else '无'}\n\n"
            "请检查：\n"
            "1. 表别名是否正确定义\n"
            "2. 列名是否存在于对应的表中\n"
            "3. JOIN 语句是否正确\n\n"
            "请使用已获取的表架构信息修正 SQL，无需重复查询架构。"
        )
    
    # 检查表不存在的错误
    if "table" in error_lower and ("doesn't exist" in error_lower or "not exist" in error_lower):
        return (
            "SQL 执行失败: 表不存在。\n\n"
            "请检查表名是否正确，可使用 sql_db_list_tables 查看可用表列表。"
        )
    
    return None


@tool
def sql_db_query_checker(query: str) -> str:
    """
    检查 SQL 查询的语法是否正确。
    注意：这只是一个基本的检查，不会实际执行查询。
    
    Args:
        query: 要检查的 SQL 查询语句
    """
    # 检查是否允许调用
    allowed, reason = _check_tool_call("sql_db_query_checker")
    if not allowed:
        return reason
    
    query_upper = query.strip().upper()
    
    # 基本语法检查
    if not query_upper:
        _record_tool_call("sql_db_query_checker", False)
        return "错误: SQL 查询为空"
    
    # 检查是否包含禁止的操作
    forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]
    for keyword in forbidden_keywords:
        if keyword in query_upper:
            _record_tool_call("sql_db_query_checker", False)
            return f"错误: 不允许执行 {keyword} 操作，只允许 SELECT 查询"
    
    if not query_upper.startswith("SELECT"):
        _record_tool_call("sql_db_query_checker", False)
        return "错误: 只允许执行 SELECT 查询"
    
    # 基本结构检查
    issues = []
    if "FROM" not in query_upper:
        issues.append("缺少 FROM 子句")
    
    # 检查括号匹配
    if query.count("(") != query.count(")"):
        issues.append("括号不匹配")
    
    # 检查引号匹配
    if query.count("'") % 2 != 0:
        issues.append("单引号不匹配")
    
    _record_tool_call("sql_db_query_checker", True)
    
    if issues:
        return f"SQL 语法警告: {', '.join(issues)}"
    
    return "✅ SQL 查询语法检查通过，可以执行。"
