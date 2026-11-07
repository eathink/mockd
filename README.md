# mockd

**用 JSON 配置快速起一个 mock HTTP 服务。**

一个配置文件、一条命令，就能给前端联调、集成测试、故障演练提供可控的假接口。纯标准库，零依赖，不需要写代码。

[![Python](https://img.shields.io/badge/python-3.10%2B-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![Zero deps](https://img.shields.io/badge/dependencies-0-brightgreen)](#设计取舍)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)
[![CI](https://github.com/eathink/mockd/actions/workflows/ci.yml/badge.svg)](https://github.com/eathink/mockd/actions/workflows/ci.yml)

## 为什么需要它

联调时后端还没好、测试需要稳定复现超时、演示不想依赖真实上游——这些场景通常需要"一个能返回指定内容的 HTTP 服务"。现成的 mock 工具要么要写代码、要么要起一整套框架、要么依赖 Node 运行时。

`mockd` 的取舍是：**配置即服务**。JSON 描述路由，进程起来就能用，退出即清理。

## 快速开始

```bash
pipx install git+https://github.com/eathink/mockd
mockd examples/mockd.json
```

```console
$ mockd examples/mockd.json
mockd 监听 http://127.0.0.1:8080（4 条路由）
GET /health -> 200
GET /api/users?page=2 -> 200
```

另开一个终端：

```console
$ curl -s localhost:8080/health
{"ok": true}

$ curl -s "localhost:8080/api/users?page=2"
[{"id": 1, "name": "Ada"}, {"id": 2, "name": "Linus"}]

$ curl -i -X POST localhost:8080/api/users
HTTP/1.0 201 Created
Content-Type: application/json
Content-Length: 8

{"id": 3}
```

## 配置格式

```json
{
  "routes": [
    {
      "method": "GET",
      "path": "/health",
      "status": 200,
      "headers": { "Content-Type": "application/json" },
      "body": "{\"ok\": true}",
      "delay_ms": 0
    }
  ]
}
```

| 字段 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `path` | 是 | — | 以 `/` 开头；结尾 `*` 表示前缀匹配。`/api/*` 匹配 `/api/` 及其子路径，`/api/users*` 同时匹配 `/api/users` 和 `/api/users/1` |
| `method` | 否 | `GET` | HTTP 方法，大小写不敏感；`*` 匹配任意方法 |
| `status` | 否 | `200` | 100–599 的整数 |
| `headers` | 否 | `text/plain; charset=utf-8` | 字符串到字符串的对象 |
| `body` | 否 | 空 | 响应体字符串 |
| `delay_ms` | 否 | `0` | 响应前延迟的毫秒数，用于模拟慢接口 |

校验是严格的：未知字段、非法方法、越界状态码都会直接报错并指出 `routes[i]`，避免拼写错误静默生效。

## 行为约定

- **按声明顺序匹配，第一条生效**——把更具体的路由放在前面
- **查询串不参与匹配**：`/api/users?page=2` 命中 `/api/users`
- 未匹配返回 `404` 和 JSON 错误体，包含请求方法与路径
- 每条请求打印一行日志；`--quiet` 关闭
- 自动设置 `Content-Length`，HEAD 请求只回头不返体
- 每个响应后关闭连接（HTTP/1.0），避免未读取的请求体影响下一个请求

## 命令行

```bash
mockd CONFIG [--host 127.0.0.1] [--port 8080] [--quiet]
```

| 选项 | 说明 |
| --- | --- |
| `--host` | 监听地址，默认 `127.0.0.1` |
| `--port` | 监听端口，默认 `8080`；`0` 表示随机端口并打印实际地址 |
| `--quiet` | 不打印每条请求 |
| `--version` | 版本号 |

## 典型用法

**前端联调**——后端未就绪时先按约定返回：

```bash
mockd examples/mockd.json
```

**模拟慢接口 / 故障**——加延迟或直接返回 5xx：

```json
{ "method": "GET", "path": "/api/slow", "delay_ms": 3000, "body": "timeout" },
{ "method": "*", "path": "/api/error", "status": 503, "body": "unavailable" }
```

**集成测试**——测试里起进程，用随机端口：

```bash
mockd test/fixtures/api.json --port 0
```

## 设计取舍

- **纯标准库**：`http.server` 足够撑住联调和测试，不引入框架依赖
- **JSON 而不是 YAML**：少一个依赖，配置本身也不复杂
- **只做响应，不做流量录制/回放**：录制代理是另一个问题域，混进来会让行为不可预测
- **不做模板、不做状态**：同一请求永远得到同一响应，便于断言
- **严格校验**：宁可启动失败，也不要带着拼写错误跑起来

## 开发

```bash
git clone https://github.com/eathink/mockd
cd mockd

# 仅用标准库，无需安装依赖
PYTHONPATH=src python3 -m unittest discover -s tests -v

# 本地运行
PYTHONPATH=src python3 -m mockd examples/mockd.json
```

## License

[MIT](LICENSE)
