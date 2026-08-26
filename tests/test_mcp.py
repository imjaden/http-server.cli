# -*- coding: utf-8 -*-
"""Tests for hs mcp module."""

import json
import pytest

from http_server_cli.mcp import (
    MCPServer,
    MCPTool,
    _TOOLS,
    _TOOL_MAP,
    _build_hs_args,
    _make_response,
    _make_error,
    _ERR_PARSE,
    _ERR_METHOD,
    MCP_PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
)


# ── 工具定义 ────────────────────────────────────────────

class TestToolDefinitions:
    def test_all_eleven_tools(self):
        """应有 11 个工具（6 管理 + 5 数据）"""
        assert len(_TOOLS) == 11

    def test_tool_names(self):
        """工具名符合 hs_ 前缀规范"""
        names = [t.name for t in _TOOLS]
        assert 'hs_list' in names
        assert 'hs_status' in names
        assert 'hs_start' in names
        assert 'hs_kill' in names
        assert 'hs_kill_all' in names
        assert 'hs_config' in names
        assert 'hs_bookmark_list' in names
        assert 'hs_bookmark_add' in names
        assert 'hs_bookmark_remove' in names
        assert 'hs_history' in names
        assert 'hs_search' in names

    def test_tool_map_completeness(self):
        """_TOOL_MAP 覆盖所有工具"""
        assert set(_TOOL_MAP.keys()) == {t.name for t in _TOOLS}

    def test_all_tools_have_descriptions(self):
        """每个工具都有非空描述"""
        for t in _TOOLS:
            assert t.description, f'{t.name} has empty description'

    def test_tool_to_dict_format(self):
        """to_dict 输出符合 MCP 规范"""
        d = _TOOLS[0].to_dict()
        assert 'name' in d
        assert 'description' in d
        assert 'inputSchema' in d

    def test_tool_input_schema_valid(self):
        """inputSchema 结构正确"""
        for t in _TOOLS:
            schema = t.input_schema
            assert schema['type'] == 'object'
            assert 'properties' in schema


# ── JSON-RPC 消息 ──────────────────────────────────────

class TestJSONRPC:
    def test_make_response_with_result(self):
        """构造成功响应"""
        resp = _make_response(1, result={'ok': True})
        assert resp['jsonrpc'] == '2.0'
        assert resp['id'] == 1
        assert resp['result'] == {'ok': True}
        assert 'error' not in resp

    def test_make_response_with_error(self):
        """构造错误响应"""
        err = _make_error(-32602, 'Bad params')
        resp = _make_response(2, error=err)
        assert resp['id'] == 2
        assert resp['error']['code'] == -32602
        assert resp['error']['message'] == 'Bad params'

    def test_make_error_with_data(self):
        """错误包含额外数据"""
        err = _make_error(-32000, 'Failed', data={'detail': 'timeout'})
        assert err['data'] == {'detail': 'timeout'}

    def test_parse_error_format(self):
        """预定义错误格式正确"""
        assert _ERR_PARSE['code'] == -32700
        assert _ERR_METHOD['code'] == -32601


# ── 参数构建 ────────────────────────────────────────────

class TestBuildArgs:
    def test_hs_list_no_params(self):
        """hs_list 生成 ['list']"""
        args = _build_hs_args('hs_list', {})
        assert args == ['list']

    def test_hs_status_with_port(self):
        """hs_status 生成 ['status', '8080']"""
        args = _build_hs_args('hs_status', {'port': 8080})
        assert args == ['status', '8080']

    def test_hs_kill_by_port(self):
        """hs_kill 按端口生成 ['kill', '8080']"""
        args = _build_hs_args('hs_kill', {'port': 8080})
        assert args == ['kill', '8080']

    def test_hs_kill_by_path(self):
        """hs_kill 按路径生成 ['kill', '/tmp/test']"""
        args = _build_hs_args('hs_kill', {'path': '/tmp/test'})
        assert args == ['kill', '/tmp/test']

    def test_hs_start_with_path(self):
        """hs_start 生成 ['start', '/my/proj']"""
        args = _build_hs_args('hs_start', {'path': '/my/proj'})
        assert args == ['start', '/my/proj']

    def test_hs_start_default_path(self):
        """hs_start 无 path 参数时默认为 '.'"""
        args = _build_hs_args('hs_start', {})
        assert args == ['start', '.']

    def test_hs_kill_all_no_params(self):
        """hs_kill_all 生成 ['kill-all']"""
        args = _build_hs_args('hs_kill_all', {})
        assert args == ['kill-all']

    def test_hs_config_no_params(self):
        """hs_config 生成 ['config']"""
        args = _build_hs_args('hs_config', {})
        assert args == ['config']

    def test_hs_bookmark_list_no_params(self):
        """hs_bookmark_list 生成 ['bookmark', 'list']"""
        args = _build_hs_args('hs_bookmark_list', {})
        assert args == ['bookmark', 'list']

    def test_hs_bookmark_add_full(self):
        """hs_bookmark_add 全参（含 -i index_page 与 --force 布尔）"""
        args = _build_hs_args('hs_bookmark_add', {
            'name': 'alpha', 'path': '~/p', 'index_page': 'index.html', 'force': True,
        })
        assert args == ['bookmark', 'add', 'alpha', '~/p', '-i', 'index.html', '--force']

    def test_hs_bookmark_add_minimal(self):
        """hs_bookmark_add 仅 name（path 默认 '.'，无 -i/--force）"""
        args = _build_hs_args('hs_bookmark_add', {'name': 'alpha'})
        assert args == ['bookmark', 'add', 'alpha', '.']

    def test_hs_bookmark_add_no_force(self):
        """hs_bookmark_add force=False 不追加 --force"""
        args = _build_hs_args('hs_bookmark_add', {'name': 'alpha', 'path': '~/p', 'force': False})
        assert args == ['bookmark', 'add', 'alpha', '~/p']

    def test_hs_bookmark_remove(self):
        """hs_bookmark_remove 生成 ['bookmark', 'remove', 'alpha']"""
        args = _build_hs_args('hs_bookmark_remove', {'name': 'alpha'})
        assert args == ['bookmark', 'remove', 'alpha']

    def test_hs_history_no_params(self):
        """hs_history 生成 ['history']"""
        args = _build_hs_args('hs_history', {})
        assert args == ['history']

    def test_hs_search_with_keyword(self):
        """hs_search 生成 ['search', '8081']"""
        args = _build_hs_args('hs_search', {'keyword': '8081'})
        assert args == ['search', '8081']


# ── MCP Resources ──────────────────────────────────────

class TestResources:
    def test_list_resources(self):
        """resources/list 返回 3 项资源"""
        server = MCPServer()
        result = server._handle_list_resources()
        uris = [r['uri'] for r in result['resources']]
        assert uris == ['hs://registry', 'hs://bookmarks', 'hs://config']

    def test_read_resource_missing_file(self, tmp_path, monkeypatch):
        """resources/read 文件缺失返回空 JSON {}（不报错）"""
        from http_server_cli import utils
        monkeypatch.setattr(utils, 'DATA_DIR', str(tmp_path))
        server = MCPServer()
        result = server._handle_read_resource({'uri': 'hs://registry'})
        assert result['contents'][0]['uri'] == 'hs://registry'
        assert result['contents'][0]['mimeType'] == 'application/json'
        assert result['contents'][0]['text'] == '{}'

    def test_read_resource_returns_file(self, tmp_path, monkeypatch):
        """resources/read 返回文件真实内容"""
        from http_server_cli import utils
        (tmp_path / 'bookmarks.json').write_text('{"bookmarks": []}', encoding='utf-8')
        monkeypatch.setattr(utils, 'DATA_DIR', str(tmp_path))
        server = MCPServer()
        result = server._handle_read_resource({'uri': 'hs://bookmarks'})
        assert '"bookmarks"' in result['contents'][0]['text']

    def test_read_unknown_resource(self):
        """未知 URI 抛 ValueError"""
        server = MCPServer()
        with pytest.raises(ValueError):
            server._handle_read_resource({'uri': 'hs://unknown'})

    def test_initialize_capabilities_resources(self):
        """initialize capabilities 含 resources"""
        server = MCPServer()
        result = server._handle_initialize({'protocolVersion': '2025-03-26', 'clientInfo': {}})
        assert 'resources' in result['capabilities']


# ── MCP Server 功能 ────────────────────────────────────

class TestMCPServerInitialization:
    def test_handle_initialize(self):
        """initialize 返回正确的协议版本和 capabilities"""
        server = MCPServer()
        result = server._handle_initialize({
            'protocolVersion': '2025-03-26',
            'clientInfo': {'name': 'test-client', 'version': '1.0'},
        })
        assert result['protocolVersion'] == MCP_PROTOCOL_VERSION
        assert result['serverInfo']['name'] == SERVER_NAME
        assert result['serverInfo']['version'] == SERVER_VERSION
        assert 'tools' in result['capabilities']

    def test_handle_list_tools(self):
        """list_tools 返回所有工具"""
        server = MCPServer()
        result = server._handle_list_tools()
        assert 'tools' in result
        assert len(result['tools']) == 11
        names = [t['name'] for t in result['tools']]
        assert 'hs_list' in names
        assert 'hs_kill' in names

    def test_handle_unknown_method(self):
        """未知 method 抛 ValueError"""
        server = MCPServer()
        with pytest.raises(ValueError, match='Unknown method'):
            server._dispatch('nonexistent', {})

    def test_dispatch_initialize(self):
        """dispatch 正确路由 initialize"""
        server = MCPServer()
        result = server._dispatch('initialize', {
            'protocolVersion': MCP_PROTOCOL_VERSION, 'clientInfo': {},
        })
        assert result['protocolVersion'] == MCP_PROTOCOL_VERSION

    def test_dispatch_list_tools(self):
        """dispatch 正确路由 tools/list（需先 init）"""
        server = MCPServer()
        server._dispatch('initialize', {'protocolVersion': '2025-03-26', 'clientInfo': {}})
        result = server._dispatch('tools/list', {})
        assert 'tools' in result

    def test_dispatch_initialized_notification(self):
        """dispatch 正确处理 notifications/initialized"""
        server = MCPServer()
        server._initialized = False
        result = server._dispatch('notifications/initialized', {})
        assert result == {}
        assert server._initialized is True


class TestMCPServerCallTool:
    def test_call_tool_missing_name(self):
        """tools/call 缺少 name 抛错误"""
        server = MCPServer()
        with pytest.raises(ValueError, match='Missing tool name'):
            server._handle_call_tool({'arguments': {}})

    def test_call_tool_unknown_name(self):
        """tools/call 未知工具名抛错误"""
        server = MCPServer()
        with pytest.raises(ValueError, match='Unknown tool'):
            server._handle_call_tool({'name': 'hs_unknown', 'arguments': {}})

    def test_call_tool_returns_content(self):
        """tools/call 成功返回 content 数组"""
        server = MCPServer()
        result = server._handle_call_tool({
            'name': 'hs_list',
            'arguments': {},
        })
        assert 'content' in result
        assert isinstance(result['content'], list)
        assert result['content'][0]['type'] == 'text'


# ── MCPTool dataclass ─────────────────────────────────

class TestMCPToolDataclass:
    def test_create_tool(self):
        tool = MCPTool(
            name='test_tool',
            description='A test tool',
            input_schema={'type': 'object', 'properties': {'x': {'type': 'string'}}},
        )
        assert tool.name == 'test_tool'
        assert tool.description == 'A test tool'

    def test_default_input_schema(self):
        tool = MCPTool(name='empty', description='No params')
        assert tool.input_schema == {'type': 'object', 'properties': {}}
