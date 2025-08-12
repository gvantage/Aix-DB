import datetime
import traceback

import pymysql
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("query_qa_record")


@mcp.tool(name="query_qa_record")
async def query_qa_record(chat_id: str):
    """
    查询用户问答记录
    """
    try:
        sql = f"select * from t_user_qa_record where chat_id='{chat_id}' order by id desc limit 1"
        print(sql)
        conn = pymysql.connect(
            host="localhost",
            port=13006,
            user="root",
            password="1",
            database="chat_db",
        )
        # 获得游标
        cursor = conn.cursor()
        # 执行 SQL 查询语句
        cursor.execute(sql)
        # 获取查询结果
        rows = cursor.fetchall()
        index = cursor.description
        result = []
        for res in rows:
            row = {}
            for i in range(len(index)):
                if isinstance(res[i], datetime.datetime):
                    value = res[i].strftime("%Y-%m-%d %H:%M:%S")
                    row[index[i][0]] = value
                else:
                    row[index[i][0]] = res[i]

            result.append(row)

        # 关闭游标和数据库连接
        cursor.close()
        conn.close()
        return result

    except Exception as e:
        traceback.print_exception(e)


if __name__ == "__main__":
    mcp.run()
