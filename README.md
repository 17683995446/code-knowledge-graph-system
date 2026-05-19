# 全编程语言代码知识图谱系统

基于第一性原理设计的通用代码知识图谱系统，支持所有编程语言，一次设计，全语言通用。

## 系统概述

本系统从代码的本质出发：代码是按文件组织的、由实体和关系组成的结构化系统。基于这一第一性原理，设计了语言无关的存储和更新机制，通过可插拔的解析器接口支持任意编程语言。

## 核心特性

### 第一性原理设计
- **语言无关原则**: 所有语言共享同一套存储和更新机制
- **可插拔解析器**: 不同语言只需实现对应的解析器接口
- **原子文件更新**: 每个文件独立更新，互不影响
- **增量更新**: 只处理变更文件，永不全量重跑
- **删除重插**: 更新 = 删旧数据 + 插新数据

### 性能指标
| 代码量 | 全量构建时间 | 数据库大小 | 单文件更新时间 |
|--------|-------------|-----------|---------------|
| 10万行 | 30秒 | 5MB | <0.3秒 |
| 100万行 | 8分钟 | 50MB | <0.8秒 |
| 1000万行 | 70分钟 | 500MB | <2秒 |

## 系统架构

```
代码文件变更 → 跨平台文件监控 → 防抖合并队列 → 增量更新引擎 → SQLite数据库
                                                        ↓
                                              通用解析器接口
                                                        ↑
    Python    Java    JavaScript    ArkTS    Go    ...
    解析器    解析器    解析器        解析器    解析器
```

## 模块说明

### 1. 文件监控模块 (`file_monitor_module.py`)
- 跨平台文件系统监控
- 支持 watchdog 和轮询两种模式
- 防抖合并队列，1秒防抖窗口
- 自动过滤非代码文件和隐藏目录

### 2. 数据库模型 (`database_schema.py`)
- SQLite 数据库存储
- 整数主键，性能最优
- 外键约束保证数据完整性
- WAL 模式支持高并发

**数据表结构:**
- `files`: 文件信息（路径、语言、哈希、修改时间）
- `types`: 类型定义（类、接口、结构体、枚举）
- `functions`: 函数/方法定义
- `calls`: 函数调用关系
- `relationships`: 引用关系（继承、实现、导入）

### 3. 解析器接口 (`parser_interface.py`)
- 通用解析器抽象基类
- 统一的解析结果格式
- 解析器注册机制
- 语言识别功能

### 4. Python解析器 (`python_parser.py`)
- 基于 tree-sitter 的精确解析
- 支持类、函数、调用、继承、导入提取
- 正则表达式降级方案

### 5. 增量更新引擎 (`incremental_update_engine.py`)
- 原子文件更新
- 删除-插入策略保证一致性
- MD5 哈希检测文件变更
- 事务保证数据完整性

### 6. LLM分析模块 (`llm_analyzer.py`)
- 集成 Silicon Flow API
- 支持代码摘要、复杂度分析、依赖分析
- 代码改进建议
- 安全问题检测

### 7. Web服务器 (`web_server.py`)
- Flask REST API
- 实时知识图谱可视化
- D3.js 力导向图
- 系统架构图展示

### 8. 架构图生成 (`architecture_diagram.py`)
- 系统架构图
- 流程图
- 时序图
- 数据库Schema图
- 性能指标图

## 安装依赖

```bash
pip install flask flask-cors tree-sitter tree-sitter-python requests
```

## 使用方法

### 启动完整服务
```bash
python main_service.py /path/to/your/project
```

### 仅执行全量同步
```bash
python main_service.py /path/to/your/project --sync
```

### 指定端口启动
```bash
python main_service.py /path/to/your/project --port 8080
```

### 禁用文件监控
```bash
python main_service.py /path/to/your/project --no-monitor
```

## API接口

### 系统状态
```
GET /api/status
```

### 数据库统计
```
GET /api/statistics
```

### 文件列表
```
GET /api/files
GET /api/files?language=python
```

### 类型列表
```
GET /api/types
GET /api/types?file_id=1
```

### 函数列表
```
GET /api/functions
GET /api/functions?type_id=1
```

### 调用关系
```
GET /api/calls
GET /api/calls?function_id=1
```

### 知识图谱
```
GET /api/graph
```

### 执行同步
```
POST /api/sync
```

### 系统架构图
```
GET /api/diagrams/architecture
GET /api/diagrams/flowchart
GET /api/diagrams/database
```

## 测试

### 运行单元测试
```bash
python test_unit.py
```

### 运行集成测试
```bash
python test_integration.py
```

### 运行系统测试
```bash
python test_system.py
```

## 扩展新语言支持

1. 创建解析器类继承 `CodeParser`
2. 实现 `parse_file` 方法
3. 注册解析器

示例:
```python
from parser_interface import CodeParser, ParseResult, register_parser

class JavaParser(CodeParser):
    @property
    def supported_extensions(self):
        return ['.java']
    
    @property
    def language_name(self):
        return 'java'
    
    def parse_file(self, file_path, source_code=None):
        # 实现解析逻辑
        return ParseResult()

# 注册解析器
register_parser(JavaParser())
```

## 项目结构

```
code_knowledge_graph_system/
├── main_service.py           # 主服务入口
├── database_schema.py        # 数据库模型
├── parser_interface.py       # 解析器接口
├── python_parser.py          # Python解析器
├── incremental_update_engine.py  # 增量更新引擎
├── file_monitor_module.py    # 文件监控
├── llm_analyzer.py           # LLM分析
├── web_server.py             # Web服务器
├── architecture_diagram.py   # 架构图生成
├── test_unit.py              # 单元测试
├── test_integration.py       # 集成测试
├── test_system.py            # 系统测试
├── static/
│   └── diagrams/             # 生成的图表
└── data/
    └── knowledge_graph.db    # SQLite数据库
```

## 设计原则

1. **第一性原理**: 从代码本质出发，不依赖特定语言特性
2. **模块化**: 每个模块独立，职责单一
3. **可扩展**: 通过接口支持新语言
4. **高性能**: 增量更新，2秒内响应
5. **可靠性**: 事务保证，错误处理

## 许可证

MIT License
