import json
from collections.abc import Callable
from typing import Any, Self
from uuid import uuid4

from agents import AgentBase, Tool
from agents.decorators import tool
from agents.mcp import MCPServer, MCPUtil
from agents.run_context import RunContextWrapper
from agents.tool import CustomTool, FunctionTool
from agents.tool_context import ToolContext
from rank_bm25 import BM25Okapi

type ProvidedTool = FunctionTool | CustomTool
type TokenizedTools = list[list[str]]
type BM25Factory = Callable[[TokenizedTools], BM25Okapi]


class ToolsProvider:
    """
    Gateway that hides a (potentially large) pool of tools behind a small
    set of meta-tools (search / get schema / exec), using BM25 for search.

    Only `FunctionTool` and `CustomTool` are supported, since those are the
    only `agents.Tool` variants that expose a locally invocable
    `on_invoke_tool` callback. Hosted tools (`WebSearchTool`, `FileSearchTool`,
    `ShellTool`, etc.) are executed by the OpenAI Responses API itself as
    part of a model turn and cannot be proxied through `exec_tool` - if you
    need them, pass them directly to `Agent(tools=...)` alongside
    `get_metatools()`.
    """

    def __init__(
        self,
        tools: list[ProvidedTool],
        bm25_factory: BM25Factory | None = None,
    ) -> None:
        self._tools: dict[str, ProvidedTool] = {}
        for tool_ in tools:
            if tool_.name in self._tools:
                raise ValueError(f"Duplicate tool name: {tool_.name!r}")
            self._tools[tool_.name] = tool_

        self._tool_ids = list(self._tools)

        self._bm25: BM25Okapi | None = None
        if self._tool_ids:
            tokenized_tools = [
                self._tokenize_tool(self._tools[tool_id]) for tool_id in self._tool_ids
            ]

            if bm25_factory is None:
                bm25_factory = BM25Okapi

            self._bm25 = bm25_factory(tokenized_tools)

        self._search_tools_tool = tool(
            self._search_tools_impl,
            name_override="search_tools",
        )
        self._get_tool_schema_tool = tool(
            self._get_tool_schema_impl,
            name_override="get_tool_schema",
        )
        # `arguments` is an intentionally open-ended object (forwarded as-is to
        # the underlying tool), which strict JSON schemas can't express
        # (no `additionalProperties` allowed) - use a non-strict schema here.
        self._exec_tool_tool = tool(
            self._exec_tool_impl,
            name_override="exec_tool",
            strict_mode=False,
        )

    def _get_tool(self, tool_id: str) -> ProvidedTool:
        try:
            return self._tools[tool_id]
        except KeyError:
            raise ValueError(f"Unknown tool: {tool_id}") from None

    # ------------------------------------------------------------------
    # Search index
    # ------------------------------------------------------------------

    def _tokenize_tool(self, tool_: ProvidedTool) -> list[str]:
        """
        Convert a tool into searchable text.

        We index:
        - tool name
        - description
        - parameter names
        - parameter descriptions
        """

        parts: list[str] = [
            tool_.name or "",
            getattr(tool_, "description", "") or "",
        ]

        schema = getattr(tool_, "params_json_schema", None)

        if isinstance(schema, dict):
            properties = schema.get("properties", {})

            if isinstance(properties, dict):
                for name, parameter in properties.items():
                    parts.append(str(name))

                    if isinstance(parameter, dict):
                        description = parameter.get("description")

                        if description:
                            parts.append(str(description))

        text = " ".join(parts)

        return text.lower().split()

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _format_tool_snippet(
        self,
        tool_id: str,
        tool_: ProvidedTool,
    ) -> str:
        return "\n".join(
            (
                f"Tool id: {tool_id}",
                f"Tool name: {tool_.name or '<unknown>'}",
                (f"Description: {getattr(tool_, 'description', None) or '<null>'}"),
            )
        )

    # ------------------------------------------------------------------
    # Meta-tools
    # ------------------------------------------------------------------

    def get_metatools(self) -> list[Tool]:
        return [
            self._search_tools_tool,
            self._get_tool_schema_tool,
            self._exec_tool_tool,
        ]

    async def _search_tools_impl(
        self,
        query: str,
        limit: int = 10,
    ) -> list[tuple[str, float]]:
        """
        Search available tools by name, description and parameters.
        Returns matching tool IDs and relevance scores.
        """

        if limit <= 0 or self._bm25 is None:
            return []

        scores = self._bm25.get_scores(
            query.lower().split(),
        )

        indexes = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )[:limit]

        return [
            (
                self._format_tool_snippet(
                    self._tool_ids[index],
                    self._tools[self._tool_ids[index]],
                ),
                float(scores[index]),
            )
            for index in indexes
        ]

    async def _get_tool_schema_impl(
        self,
        tool_id: str,
    ) -> dict[str, Any]:
        """
        Get the complete schema of a tool by its ID.
        """

        tool_ = self._get_tool(tool_id)

        return {
            "id": tool_id,
            "name": tool_.name,
            "description": getattr(tool_, "description", None),
            "parameters": getattr(
                tool_,
                "params_json_schema",
                None,
            ),
        }

    async def _exec_tool_impl(
        self,
        ctx: ToolContext[Any],
        tool_id: str,
        arguments: dict[str, Any] | None = None,
        raw_input: str | None = None,
    ) -> Any:
        """
        Execute a tool by its ID.

        Pass `arguments` for tools expecting JSON parameters (most tools,
        including MCP tools). Pass `raw_input` instead for tools expecting a
        single raw string input (rare - only some custom tools).
        """

        try:
            tool_ = self._get_tool(tool_id)

            input_str = (
                raw_input if raw_input is not None else json.dumps(arguments or {})
            )

            nested_ctx = ToolContext(
                context=ctx.context,
                usage=ctx.usage,
                tool_name=tool_id,
                tool_call_id=f"{ctx.tool_call_id}:{tool_id}:{uuid4().hex}",
                tool_arguments=input_str,
                run_config=ctx.run_config,
                agent=ctx.agent,
            )

            return await tool_.on_invoke_tool(nested_ctx, input_str)
        except Exception as e:  # noqa: BLE001 - surfaced to the LLM, not swallowed
            return f"[Error executing tool {tool_id!r}]: {e!r}"

    # ------------------------------------------------------------------
    # Construction from MCP servers
    # ------------------------------------------------------------------

    @classmethod
    async def from_mcp_servers(
        cls,
        servers: list[MCPServer],
        *,
        agent: AgentBase,
        run_context: RunContextWrapper[Any] | None = None,
        bm25_factory: BM25Factory | None = None,
    ) -> Self:
        """
        Build a ToolsProvider from a list of MCP servers, fetching all
        available tools from each server and prefixing their names with the
        server name (e.g. `telegram.send_message`) to avoid collisions.
        """

        if run_context is None:
            run_context = RunContextWrapper(context=None)

        all_tools: list[ProvidedTool] = []
        for server in servers:
            server_tools = await MCPUtil.get_function_tools(
                server,
                convert_schemas_to_strict=True,
                run_context=run_context,
                agent=agent,
                tool_name_override=lambda mcp_tool, sn=server.name: (
                    f"{sn}.{mcp_tool.name}"
                ),
            )
            for server_tool in server_tools:
                if not isinstance(server_tool, FunctionTool):
                    raise TypeError(
                        f"Expected MCP server {server.name!r} to produce FunctionTool "
                        f"instances, got {type(server_tool).__name__}"
                    )
                all_tools.append(server_tool)

        return cls(tools=all_tools, bm25_factory=bm25_factory)
