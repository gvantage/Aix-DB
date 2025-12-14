# 数据源管理依赖安装指南

## 已配置的依赖

数据源管理功能所需的依赖已添加到项目配置文件中：

### 加密库
- ✅ **pycryptodome** (>=3.23.0) - 用于配置信息加密

### 数据库驱动
- ✅ **pymysql** (>=1.1.1) - MySQL 数据库驱动
- ✅ **psycopg2-binary** (>=2.9.9) - PostgreSQL 数据库驱动
- ✅ **oracledb** (>=2.0.0) - Oracle 数据库驱动
- ✅ **pymssql** (>=2.2.11) - SQL Server 数据库驱动
- ✅ **clickhouse-driver** (>=0.2.7) - ClickHouse 数据库驱动

## 安装方法

### 方法一：使用 uv（推荐）

如果项目使用 `uv` 作为包管理器：

```bash
# 安装所有依赖（包括新增的数据库驱动）
uv sync

# 或者只安装新增的依赖
uv add pycryptodome psycopg2-binary oracledb pymssql clickhouse-driver
```

### 方法二：使用 pip

```bash
# 安装所有依赖
pip install -r requirements.txt

# 或者只安装新增的依赖
pip install pycryptodome psycopg2-binary oracledb pymssql clickhouse-driver
```

## 验证安装

安装完成后，可以通过以下方式验证：

```python
# 测试导入
try:
    from Crypto.Cipher import AES
    print("✅ pycryptodome 安装成功")
except ImportError:
    print("❌ pycryptodome 未安装")

try:
    import pymysql
    print("✅ pymysql 安装成功")
except ImportError:
    print("❌ pymysql 未安装")

try:
    import psycopg2
    print("✅ psycopg2 安装成功")
except ImportError:
    print("❌ psycopg2 未安装")

try:
    import oracledb
    print("✅ oracledb 安装成功")
except ImportError:
    print("❌ oracledb 未安装")

try:
    import pymssql
    print("✅ pymssql 安装成功")
except ImportError:
    print("❌ pymssql 未安装")

try:
    import clickhouse_driver
    print("✅ clickhouse-driver 安装成功")
except ImportError:
    print("❌ clickhouse-driver 未安装")
```

## 注意事项

1. **Oracle 驱动**：`oracledb` 是 Oracle 官方推荐的现代 Python 驱动，替代了旧的 `cx_Oracle`。

2. **PostgreSQL 驱动**：使用 `psycopg2-binary` 版本，它包含了预编译的二进制文件，安装更简单，无需系统依赖。

3. **SQL Server 驱动**：`pymssql` 是纯 Python 实现，无需额外的系统库。

4. **ClickHouse 驱动**：`clickhouse-driver` 是官方推荐的 Python 客户端。

5. **加密库**：如果 `pycryptodome` 安装失败，系统会回退到 base64 编码（不安全，仅用于开发环境）。

## 故障排除

### Oracle 驱动问题

如果使用 Oracle 数据库，可能需要安装 Oracle Instant Client：

```bash
# macOS
brew install instantclient-basic instantclient-sdk

# Linux
# 下载并安装 Oracle Instant Client
# https://www.oracle.com/database/technologies/instant-client/downloads.html
```

### PostgreSQL 驱动问题

如果 `psycopg2-binary` 安装失败，可以尝试：

```bash
# 安装系统依赖（Linux）
sudo apt-get install libpq-dev python3-dev

# 然后安装 psycopg2（非binary版本）
pip install psycopg2
```

### SQL Server 驱动问题

如果 `pymssql` 安装失败，可能需要安装 FreeTDS：

```bash
# macOS
brew install freetds

# Linux
sudo apt-get install freetds-dev
```



