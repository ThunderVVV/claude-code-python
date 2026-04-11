"""gRPC server implementation for Claude Code Python"""

from __future__ import annotations

import asyncio
import logging
from concurrent import futures
from typing import AsyncGenerator, Dict, Optional

import grpc
from grpc import aio

from claude_code.core.messages import (
    Message,
    MessageRole,
    TextContent,
    ThinkingContent,
    ToolUseContent,
    ToolResultContent,
    Usage,
    QueryEvent,
    TextEvent as CoreTextEvent,
    ThinkingEvent as CoreThinkingEvent,
    ToolUseEvent as CoreToolUseEvent,
    ToolResultEvent as CoreToolResultEvent,
    MessageCompleteEvent as CoreMessageCompleteEvent,
    TurnCompleteEvent as CoreTurnCompleteEvent,
    ErrorEvent as CoreErrorEvent,
)
from claude_code.core.query_engine import QueryEngine
from claude_code.core.tools import ToolRegistry
from claude_code.core.session_store import SessionStore, PersistedSession
from claude_code.services.openai_client import OpenAIClientConfig
from claude_code.utils.logging_config import log_full_exception

logger = logging.getLogger(__name__)


def check_port_available(host: str, port: int) -> None:
    """Check if a port is available (not already bound by another server).

    Raises RuntimeError if the port is already in use.
    """
    import socket

    check_host = "localhost" if host == "[::]" else host
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.settimeout(0.1)
        result = test_sock.connect_ex((check_host, port))
        test_sock.close()
        if result == 0:
            logger.error(f"Port {port} is already in use by another server.")
            raise RuntimeError(
                f"Port {port} is already in use. Please stop the existing server first (pkill -f cc-server)."
            )
    except socket.error:
        pass


def message_role_to_proto(role: MessageRole) -> int:
    from claude_code.proto import claude_code_pb2

    mapping = {
        MessageRole.USER: claude_code_pb2.MESSAGE_ROLE_USER,
        MessageRole.ASSISTANT: claude_code_pb2.MESSAGE_ROLE_ASSISTANT,
        MessageRole.SYSTEM: claude_code_pb2.MESSAGE_ROLE_SYSTEM,
        MessageRole.TOOL: claude_code_pb2.MESSAGE_ROLE_TOOL,
    }
    return mapping.get(role, claude_code_pb2.MESSAGE_ROLE_UNSPECIFIED)


def proto_to_message_role(role: int) -> MessageRole:
    from claude_code.proto import claude_code_pb2

    mapping = {
        claude_code_pb2.MESSAGE_ROLE_USER: MessageRole.USER,
        claude_code_pb2.MESSAGE_ROLE_ASSISTANT: MessageRole.ASSISTANT,
        claude_code_pb2.MESSAGE_ROLE_SYSTEM: MessageRole.SYSTEM,
        claude_code_pb2.MESSAGE_ROLE_TOOL: MessageRole.TOOL,
    }
    return mapping.get(role, MessageRole.USER)


def content_block_to_proto(block) -> "claude_code_pb2.ContentBlock":
    from claude_code.proto import claude_code_pb2
    import json

    pb = claude_code_pb2.ContentBlock()

    if isinstance(block, TextContent):
        pb.text.text = block.text
    elif isinstance(block, ThinkingContent):
        pb.thinking.thinking = block.thinking
        pb.thinking.signature = block.signature or ""
    elif isinstance(block, ToolUseContent):
        pb.tool_use.id = block.id
        pb.tool_use.name = block.name
        pb.tool_use.input_json = json.dumps(block.input) if block.input else "{}"
    elif isinstance(block, ToolResultContent):
        pb.tool_result.tool_use_id = block.tool_use_id
        pb.tool_result.content = block.content
        pb.tool_result.is_error = block.is_error

    return pb


def proto_to_content_block(pb) -> Optional[object]:
    from claude_code.proto import claude_code_pb2
    import json

    which = pb.WhichOneof("block")
    if which == "text":
        return TextContent(text=pb.text.text)
    elif which == "thinking":
        return ThinkingContent(
            thinking=pb.thinking.thinking,
            signature=pb.thinking.signature,
        )
    elif which == "tool_use":
        return ToolUseContent(
            id=pb.tool_use.id,
            name=pb.tool_use.name,
            input=json.loads(pb.tool_use.input_json) if pb.tool_use.input_json else {},
        )
    elif which == "tool_result":
        return ToolResultContent(
            tool_use_id=pb.tool_result.tool_use_id,
            content=pb.tool_result.content,
            is_error=pb.tool_result.is_error,
        )
    return None


def message_to_proto(msg: Message) -> "claude_code_pb2.Message":
    from claude_code.proto import claude_code_pb2

    pb = claude_code_pb2.Message()
    pb.role = message_role_to_proto(msg.type)
    pb.uuid = msg.uuid
    pb.timestamp = int(msg.timestamp.timestamp()) if msg.timestamp else 0
    pb.original_text = msg.original_text or ""

    for block in msg.content:
        pb.content.append(content_block_to_proto(block))

    usage = msg.get_usage()
    if usage:
        pb.usage.input_tokens = usage.input_tokens
        pb.usage.output_tokens = usage.output_tokens

    return pb


def proto_to_message(pb: "claude_code_pb2.Message") -> Message:
    from datetime import datetime

    content_blocks = []
    for block_pb in pb.content:
        block = proto_to_content_block(block_pb)
        if block:
            content_blocks.append(block)

    return Message(
        type=proto_to_message_role(pb.role),
        content=content_blocks,
        uuid=pb.uuid,
        timestamp=datetime.fromtimestamp(pb.timestamp)
        if pb.timestamp
        else datetime.now(),
        original_text=pb.original_text,
    )


def query_event_to_proto(event: QueryEvent) -> "claude_code_pb2.QueryEvent":
    from claude_code.proto import claude_code_pb2

    pb = claude_code_pb2.QueryEvent()

    if isinstance(event, CoreTextEvent):
        pb.text_event.text = event.text
    elif isinstance(event, CoreThinkingEvent):
        pb.thinking_event.thinking = event.thinking
    elif isinstance(event, CoreToolUseEvent):
        import json

        pb.tool_use_event.tool_use_id = event.tool_use_id
        pb.tool_use_event.tool_name = event.tool_name
        pb.tool_use_event.input_json = json.dumps(event.input) if event.input else "{}"
    elif isinstance(event, CoreToolResultEvent):
        pb.tool_result_event.tool_use_id = event.tool_use_id
        pb.tool_result_event.result = event.result
        pb.tool_result_event.is_error = event.is_error
    elif isinstance(event, CoreMessageCompleteEvent):
        if event.message:
            pb.message_complete_event.message.CopyFrom(message_to_proto(event.message))
    elif isinstance(event, CoreTurnCompleteEvent):
        pb.turn_complete_event.turn = event.turn
        pb.turn_complete_event.has_more_turns = event.has_more_turns
        pb.turn_complete_event.stop_reason = event.stop_reason or ""
    elif isinstance(event, CoreErrorEvent):
        pb.error_event.error = event.error
        pb.error_event.is_fatal = event.is_fatal

    return pb


class SessionManager:
    def __init__(self):
        self._engines: Dict[str, QueryEngine] = {}
        self._session_store = SessionStore()
        self._lock = asyncio.Lock()

    async def get_or_create_engine(
        self,
        session_id: Optional[str],
        client_config: OpenAIClientConfig,
        tool_registry: ToolRegistry,
        working_directory: str = "",
    ) -> QueryEngine:
        async with self._lock:
            if session_id and session_id in self._engines:
                return self._engines[session_id]

            engine = await self._create_engine(
                session_id, client_config, tool_registry, working_directory
            )
            self._engines[engine.get_session_id()] = engine
            return engine

    async def _create_engine(
        self,
        session_id: Optional[str],
        client_config: OpenAIClientConfig,
        tool_registry: ToolRegistry,
        working_directory: str,
    ) -> QueryEngine:
        return await QueryEngine.create_from_session_id(
            session_id=session_id,
            client_config=client_config,
            tool_registry=tool_registry,
            session_store=self._session_store,
            working_directory=working_directory,
        )

    def get_engine(self, session_id: str) -> Optional[QueryEngine]:
        return self._engines.get(session_id)

    def list_sessions(self):
        return self._session_store.list_sessions()

    def get_session(self, session_id: str) -> Optional[PersistedSession]:
        return self._session_store.load_session(session_id)


class ChatServiceServicer:
    def __init__(
        self,
        client_config: OpenAIClientConfig,
        tool_registry: ToolRegistry,
        session_manager: SessionManager,
    ):
        self._client_config = client_config
        self._tool_registry = tool_registry
        self._session_manager = session_manager

    async def StreamChat(
        self,
        request: "claude_code_pb2.ChatRequest",
        context: grpc.aio.ServicerContext,
    ) -> AsyncGenerator["claude_code_pb2.ChatResponse", None]:
        from claude_code.proto import claude_code_pb2

        user_text_str= request.user_text[:100] + "..." if len(request.user_text) > 100 else request.user_text
        logger.info(f"Request received - session_id={request.session_id}, user_text={user_text_str}")

        try:
            engine = await self._session_manager.get_or_create_engine(
                request.session_id or None,
                self._client_config,
                self._tool_registry,
                request.working_directory,
            )

            async for event in engine.submit_message(request.user_text):
                pb_event = query_event_to_proto(event)
                response = claude_code_pb2.ChatResponse(event=pb_event)
                yield response

            logger.info(f"Streaming completed - session_id={request.session_id}")
        except asyncio.CancelledError:
            logger.info(f"Stream chat cancelled - session_id={request.session_id}")
        except Exception as e:
            log_full_exception(logger, "Stream chat error", e)
            error_event = CoreErrorEvent(error=str(e), is_fatal=True)
            pb_event = query_event_to_proto(error_event)
            yield claude_code_pb2.ChatResponse(event=pb_event)

    async def Interrupt(
        self,
        request: "claude_code_pb2.InterruptRequest",
        context: grpc.aio.ServicerContext,
    ) -> "claude_code_pb2.InterruptResponse":
        from claude_code.proto import claude_code_pb2

        logger.info(f"Interrupt received - session_id={request.session_id}, reason={request.reason}")

        response = claude_code_pb2.InterruptResponse()

        engine = self._session_manager.get_engine(request.session_id)
        if engine:
            engine.interrupt(request.reason or "user_interrupt")
            response.success = True
        else:
            response.success = False

        return response


class SessionServiceServicer:
    def __init__(self, session_manager: SessionManager):
        self._session_manager = session_manager

    async def CreateSession(
        self,
        request: "claude_code_pb2.CreateSessionRequest",
        context: grpc.aio.ServicerContext,
    ) -> "claude_code_pb2.CreateSessionResponse":
        from claude_code.proto import claude_code_pb2
        from claude_code.core.messages import generate_uuid

        logger.info(f"CreateSession request")
        response = claude_code_pb2.CreateSessionResponse()
        response.session_id = generate_uuid()
        return response

    async def GetSession(
        self,
        request: "claude_code_pb2.GetSessionRequest",
        context: grpc.aio.ServicerContext,
    ) -> "claude_code_pb2.GetSessionResponse":
        from claude_code.proto import claude_code_pb2

        logger.info(f"GetSession request - session_id={request.session_id}")

        response = claude_code_pb2.GetSessionResponse()

        session = self._session_manager.get_session(request.session_id)
        if session:
            response.session_id = session.session_id
            response.current_turn = session.current_turn
            response.working_directory = session.working_directory or ""
            response.title = session.title or ""

            if session.total_usage:
                response.total_usage.input_tokens = session.total_usage.input_tokens
                response.total_usage.output_tokens = session.total_usage.output_tokens

            for msg in session.messages:
                response.messages.append(message_to_proto(msg))

        return response

    async def ListSessions(
        self,
        request: "claude_code_pb2.ListSessionsRequest",
        context: grpc.aio.ServicerContext,
    ) -> "claude_code_pb2.ListSessionsResponse":
        from datetime import datetime
        from claude_code.proto import claude_code_pb2

        logger.info(f"ListSessions request")

        response = claude_code_pb2.ListSessionsResponse()

        for summary in self._session_manager.list_sessions():
            pb_summary = claude_code_pb2.SessionSummary()
            pb_summary.session_id = summary.session_id
            pb_summary.title = summary.title or ""
            try:
                dt = datetime.fromisoformat(summary.updated_at)
                pb_summary.updated_at = int(dt.timestamp())
            except Exception:
                pb_summary.updated_at = 0
            pb_summary.working_directory = summary.working_directory or ""
            pb_summary.message_count = summary.message_count
            response.sessions.append(pb_summary)

        return response


async def serve(
    client_config: OpenAIClientConfig,
    tool_registry: ToolRegistry,
    host: str = "[::]",
    port: int = 50051,
) -> None:
    from claude_code.proto import claude_code_pb2_grpc

    check_port_available(host, port)

    session_manager = SessionManager()

    chat_servicer = ChatServiceServicer(client_config, tool_registry, session_manager)
    session_servicer = SessionServiceServicer(session_manager)

    server = aio.server(futures.ThreadPoolExecutor(max_workers=10))

    claude_code_pb2_grpc.add_ChatServiceServicer_to_server(chat_servicer, server)
    claude_code_pb2_grpc.add_SessionServiceServicer_to_server(session_servicer, server)

    server.add_insecure_port(f"{host}:{port}")

    logger.info(f"Starting gRPC server on {host}:{port}")
    await server.start()

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        await server.stop(5)
