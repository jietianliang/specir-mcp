# specir-mcp

[English](README.md) | [简体中文](README_zh-CN.md)

`specir-mcp` 是一个数据中立的技术规范处理框架，用于将技术文档转换为结构化中间表示（SpecIR），并通过五个稳定的 MCP 工具进行查询。

本仓库不包含任何标准 PDF、提取后的规范正文、知识库数据库、模型权重或厂商专用协议表。仓库内置的演示内容完全虚构。

## 功能

- 文档、章节、表格、图片、实体、原文片段、来源信息和关系边的统一 IR。
- 支持依赖排序和降级运行的可扩展领域插件系统。
- 基于 PDF 目录的章节提取，以及可复用的结构解析器。
- 基于 SQLite 的精确解析、实体获取、组合解释、搜索和状态查询。
- 固定的五工具 FastMCP 接口：
  `specir_resolve`、`specir_fetch`、`specir_explain`、
  `specir_search` 和 `specir_status`。
- 所有查询均返回覆盖状态，避免将“尚未提取”错误理解为“源文档中不存在”。

## 快速开始

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[test]"

# 根据完全虚构的 Acme Device Interface 示例生成小型数据库。
specir-demo --output data/demo.db

export SPEC_IR_DB="$PWD/data/demo.db"
specir-mcp-server
```

也可以直接在源码目录启动：

```bash
fastmcp run src/specir/query/server.py
```

MCP 查询示例：

```text
specir_resolve(kind="command", id="A1h", spec="acme-device")
specir_fetch(uid="acme-device:2.1", include_xrefs=true)
specir_explain(name="Read Telemetry", kind="command", spec="acme-device")
specir_search(query="telemetry", spec="acme-device")
specir_status()
```

当数据库仅登记一个文档时，`spec="auto"` 会自动选择该文档。数据库包含多个文档时，未指定版本的精确查询会返回候选项，并要求显式传入 `spec`。

## 使用自己的数据

使用 `specir.query.schema.create_database` 创建空数据库，然后按照 Python 数据类定义写入文档和实体。启动服务前，将 `SPEC_IR_DB` 指向该数据库。

框架不会自动下载或捆绑任何源文档。

可选的 PDF 提取器可以生成按坐标裁剪的章节记录：

```python
from specir.extractors.pdf import build_section_tree

sections = build_section_tree("my-spec", "path/to/your-document.pdf")
```

使用者应自行确认有权处理和存储所提供的文档。

## 五个 MCP 工具

| 工具 | 用途 |
|---|---|
| `specir_resolve` | 按 kind、标识符和可选 spec 精确解析实体 |
| `specir_fetch` | 根据规范 UID 获取完整实体及可选关系边 |
| `specir_explain` | 组合返回命名实体和定义该实体的章节 |
| `specir_search` | 搜索结构化内容或原文片段 |
| `specir_status` | 查看插件状态和数据库覆盖量 |

## 开发与测试

```bash
pytest
python -m build
python scripts/audit_public_tree.py
```

测试只使用临时生成的虚构数据库，不需要外部规范或网络连接。

GitHub Actions 会在 Python 3.10、3.11 和 3.12 上执行测试、wheel 构建、公开内容审计和安装后冒烟测试。

## 数据与隐私边界

以下内容不会随框架发布：

- PDF 或其他标准原文；
- SQLite 知识库和解析输出；
- embedding 模型或其他模型权重；
- 内部日志、个人配置、凭据和绝对路径；
- 从真实规范整理出的协议常量或 benchmark 数据。

## 许可证

本项目采用 Apache License 2.0，详见 [LICENSE](LICENSE)。
