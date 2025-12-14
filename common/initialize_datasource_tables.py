"""
数据源表初始化脚本
使用 SQLAlchemy 创建数据源相关的数据库表
"""
import logging
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 确保模型被导入，这样 SQLAlchemy 才能识别它们
from model import Base, get_db_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_datasource_tables():
    """
    创建数据源相关的数据库表
    """
    try:
        db_pool = get_db_pool()
        logger.info("开始创建数据源相关表...")
        
        # 创建所有表（只会创建不存在的表）
        db_pool.create_tables()
        
        logger.info("数据源表创建成功！")
        logger.info("已创建的表：")
        logger.info("  - t_datasource (数据源表)")
        logger.info("  - t_datasource_table (数据源表信息)")
        logger.info("  - t_datasource_field (数据源字段信息)")
        return True
    except Exception as e:
        logger.error(f"创建数据源表失败: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = create_datasource_tables()
    sys.exit(0 if success else 1)

