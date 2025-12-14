"""
数据源工具类
"""

import json
import logging
import urllib.parse
from typing import Dict, Any, List, Optional

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class DatasourceConnectionUtil:
    """数据源连接工具类"""

    @staticmethod
    def build_connection_uri(ds_type: str, config: Dict[str, Any]) -> str:
        """构建数据库连接URI"""
        host = config.get("host", "")
        port = config.get("port", 3306)
        username = config.get("username", "")
        password = config.get("password", "")
        database = config.get("database", "")
        extra_jdbc = config.get("extraJdbc", "")
        mode = config.get("mode", "service_name")

        # URL编码用户名和密码
        username_encoded = urllib.parse.quote(username)
        password_encoded = urllib.parse.quote(password)

        if ds_type == "mysql":
            if extra_jdbc:
                return f"mysql+pymysql://{username_encoded}:{password_encoded}@{host}:{port}/{database}?{extra_jdbc}"
            return f"mysql+pymysql://{username_encoded}:{password_encoded}@{host}:{port}/{database}"

        elif ds_type == "pg":
            if extra_jdbc:
                return (
                    f"postgresql+psycopg2://{username_encoded}:{password_encoded}@{host}:{port}/{database}?{extra_jdbc}"
                )
            return f"postgresql+psycopg2://{username_encoded}:{password_encoded}@{host}:{port}/{database}"

        elif ds_type == "oracle":
            if mode == "service_name":
                if extra_jdbc:
                    return f"oracle+oracledb://{username_encoded}:{password_encoded}@{host}:{port}?service_name={database}&{extra_jdbc}"
                return f"oracle+oracledb://{username_encoded}:{password_encoded}@{host}:{port}?service_name={database}"
            else:
                if extra_jdbc:
                    return (
                        f"oracle+oracledb://{username_encoded}:{password_encoded}@{host}:{port}/{database}?{extra_jdbc}"
                    )
                return f"oracle+oracledb://{username_encoded}:{password_encoded}@{host}:{port}/{database}"

        elif ds_type == "sqlServer":
            if extra_jdbc:
                return f"mssql+pymssql://{username_encoded}:{password_encoded}@{host}:{port}/{database}?{extra_jdbc}"
            return f"mssql+pymssql://{username_encoded}:{password_encoded}@{host}:{port}/{database}"

        elif ds_type == "ck":
            if extra_jdbc:
                return f"clickhouse+http://{username_encoded}:{password_encoded}@{host}:{port}/{database}?{extra_jdbc}"
            return f"clickhouse+http://{username_encoded}:{password_encoded}@{host}:{port}/{database}"

        else:
            raise ValueError(f"不支持的数据源类型: {ds_type}")

    @staticmethod
    def test_connection(ds_type: str, config: Dict[str, Any]) -> (bool, str):
        """测试数据库连接"""
        try:
            uri = DatasourceConnectionUtil.build_connection_uri(ds_type, config)
            engine = create_engine(uri, pool_pre_ping=True, connect_args={"connect_timeout": config.get("timeout", 30)})
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True, ""
        except Exception as e:
            logger.error(f"连接测试失败: {e}")
            return False, str(e)

    @staticmethod
    def get_tables(ds_type: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取数据库表列表"""
        try:
            uri = DatasourceConnectionUtil.build_connection_uri(ds_type, config)
            engine = create_engine(uri, pool_pre_ping=True, connect_args={"connect_timeout": config.get("timeout", 30)})

            inspector = inspect(engine)
            db_schema = config.get("dbSchema") or config.get("database")

            tables = []
            if ds_type in ["pg", "oracle", "sqlServer"]:
                # 需要指定schema
                table_names = inspector.get_table_names(schema=db_schema)
            else:
                table_names = inspector.get_table_names()

            for table_name in table_names:
                try:
                    # 获取表注释
                    comment = None
                    if ds_type == "mysql":
                        with engine.connect() as conn:
                            result = conn.execute(
                                text(
                                    f"SELECT table_comment FROM information_schema.tables "
                                    f"WHERE table_schema = '{config.get('database')}' AND table_name = '{table_name}'"
                                )
                            )
                            row = result.fetchone()
                            comment = row[0] if row else None
                    elif ds_type == "pg":
                        with engine.connect() as conn:
                            result = conn.execute(
                                text(f"SELECT obj_description('{db_schema}.{table_name}'::regclass, 'pg_class')")
                            )
                            row = result.fetchone()
                            comment = row[0] if row else None

                    tables.append(
                        {
                            "tableName": table_name,
                            "tableComment": comment or "",
                        }
                    )
                except Exception as e:
                    logger.warning(f"获取表 {table_name} 注释失败: {e}")
                    tables.append(
                        {
                            "tableName": table_name,
                            "tableComment": "",
                        }
                    )

            return tables
        except Exception as e:
            logger.error(f"获取表列表失败: {e}")
            raise

    @staticmethod
    def get_fields(ds_type: str, config: Dict[str, Any], table_name: str) -> List[Dict[str, Any]]:
        """获取指定表的字段列表（名称/类型/注释）"""
        try:
            uri = DatasourceConnectionUtil.build_connection_uri(ds_type, config)
            engine = create_engine(uri, pool_pre_ping=True, connect_args={"connect_timeout": config.get("timeout", 30)})

            inspector = inspect(engine)
            db_schema = config.get("dbSchema") or config.get("database")
            columns = inspector.get_columns(table_name, schema=db_schema)

            fields = []
            for idx, col in enumerate(columns):
                col_name = col.get("name")
                col_type = str(col.get("type"))
                col_comment = col.get("comment") or ""
                fields.append(
                    {"fieldName": col_name, "fieldType": col_type, "fieldComment": col_comment, "fieldIndex": idx}
                )
            return fields
        except Exception as e:
            logger.error(f"获取表 {table_name} 字段失败: {e}")
            raise

    @staticmethod
    def execute_query(ds_type: str, config: Dict[str, Any], sql: str) -> List[Dict[str, Any]]:
        """执行SQL查询并返回结果"""
        try:
            uri = DatasourceConnectionUtil.build_connection_uri(ds_type, config)
            engine = create_engine(uri, pool_pre_ping=True, connect_args={"connect_timeout": config.get("timeout", 30)})

            with engine.connect() as conn:
                result = conn.execute(text(sql))
                rows = result.fetchall()

                # 转换为字典列表
                columns = result.keys()
                data = []
                for row in rows:
                    row_dict = {}
                    for i, col in enumerate(columns):
                        value = row[i]
                        # 处理日期时间类型
                        if hasattr(value, "isoformat"):
                            value = value.isoformat()
                        elif hasattr(value, "strftime"):
                            value = value.strftime("%Y-%m-%d %H:%M:%S")
                        row_dict[col] = value
                    data.append(row_dict)

                return data
        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            raise


class DatasourceConfigUtil:
    """数据源配置工具类 - 加密/解密"""

    # 简单的加密密钥（生产环境应使用更安全的方式）
    KEY = b"SQLBot1234567890"  # 16字节密钥

    @staticmethod
    def encrypt_config(config: Dict[str, Any]) -> str:
        """加密配置信息"""
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import pad
            import base64

            config_str = json.dumps(config)
            cipher = AES.new(DatasourceConfigUtil.KEY, AES.MODE_ECB)
            padded_data = pad(config_str.encode("utf-8"), AES.block_size)
            encrypted = cipher.encrypt(padded_data)
            return base64.b64encode(encrypted).decode("utf-8")
        except ImportError:
            # 如果没有安装pycryptodome，使用简单的base64编码（不安全，仅用于开发）
            logger.warning("pycryptodome未安装，使用base64编码（不安全）")
            import base64

            config_str = json.dumps(config)
            return base64.b64encode(config_str.encode("utf-8")).decode("utf-8")
        except Exception as e:
            logger.error(f"加密配置失败: {e}")
            raise

    @staticmethod
    def decrypt_config(encrypted_config: str) -> Dict[str, Any]:
        """解密配置信息"""
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
            import base64

            encrypted_data = base64.b64decode(encrypted_config)
            cipher = AES.new(DatasourceConfigUtil.KEY, AES.MODE_ECB)
            decrypted = cipher.decrypt(encrypted_data)
            unpadded = unpad(decrypted, AES.block_size)
            return json.loads(unpadded.decode("utf-8"))
        except ImportError:
            # 如果没有安装pycryptodome，使用简单的base64解码
            logger.warning("pycryptodome未安装，使用base64解码")
            import base64

            config_str = base64.b64decode(encrypted_config).decode("utf-8")
            return json.loads(config_str)
        except Exception as e:
            logger.error(f"解密配置失败: {e}")
            raise
