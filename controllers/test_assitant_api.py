"""
测试助手api
"""
from sanic import Blueprint

from common.res_decorator import async_json_resp
from common.token_decorator import check_token
from services.test_assistant_service import extract_toc_to_markdown, query_test_assistant_records
from services.user_service import get_user_info

bp = Blueprint("testAssistant", url_prefix="/ta"***REMOVED***


@bp.post("/word_to_md"***REMOVED***
@async_json_resp
async def convert_doc_to_markdown_api(request***REMOVED***:
    """
    转换word文档 markdown
    :param request:
    :return:
    """
    file_key = request.json.get("file_key"***REMOVED***
    # result = await convert_word_to_md(file_key***REMOVED***
    user_info = await get_user_info(request***REMOVED***
    result = await extract_toc_to_markdown(user_info["id"], file_key***REMOVED***
    return result


@bp.post("/query_test_assistant_records", name="query_test_assistant_records"***REMOVED***
# @check_token
@async_json_resp
async def query_test_assistant(request***REMOVED***:
    """
    查询t_test_assistant表中的记录，支持分页。

    :param request: 请求对象
    :return: JSON格式的查询结果
    """
    # 解析请求参数
    page = int(request.json.get("page", 1***REMOVED******REMOVED***
    limit = int(request.json.get("limit", 10***REMOVED******REMOVED***
    file_key = request.json.get("file_key"***REMOVED***  # 可选参数，用于过滤查询结果

    # 获取用户信息
    # user_info = await get_user_info(request***REMOVED***

    # 调用查询函数并返回结果
    return await query_test_assistant_records(file_key=file_key, page=page, limit=limit***REMOVED***
