from __future__ import annotations

import asyncio
import logging

import websockets

from jarvis_agent.auth import create_device_token
from jarvis_agent.config import AgentConfig
from jarvis_agent.executor import CommandExecutor
from jarvis_agent.protocol import (
    make_command_result,
    make_heartbeat,
    make_hello,
)


logger = logging.getLogger(__name__)


class JarvisAgentClient:
    def __init__(
        self,
        config: AgentConfig,
        executor: CommandExecutor,
    ) -> None:
        self.config = config
        self.executor = executor

    async def run_forever(self) -> None:
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Agent connection failed")

            await asyncio.sleep(5)

    async def run_once(self) -> None:
        token = create_device_token(
            self.config.device_id,
            self.config.auth_secret,
        )

        async with websockets.connect(
            self.config.server_url,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
        ) as websocket:
            await websocket.send(
                _encode(
                    make_hello(
                        device_id=self.config.device_id,
                        device_name=self.config.device_name,
                        agent_version=self.config.agent_version,
                        token=token,
                    )
                )
            )

            logger.info("Connected to JARVIS server")

            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(websocket)
            )

            try:
                async for raw_message in websocket:
                    await self._handle_message(
                        websocket,
                        raw_message,
                    )
            finally:
                heartbeat_task.cancel()
                await asyncio.gather(
                    heartbeat_task,
                    return_exceptions=True,
                )

    async def _heartbeat_loop(self, websocket) -> None:
        while True:
            await asyncio.sleep(
                self.config.heartbeat_interval_seconds
            )
            await websocket.send(
                _encode(make_heartbeat(self.config.device_id))
            )

    async def _handle_message(
        self,
        websocket,
        raw_message: str,
    ) -> None:
        import json

        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.warning("Ignoring invalid JSON from server")
            return

        if not isinstance(message, dict):
            logger.warning("Ignoring non-object server message")
            return

        if message.get("type") != "command":
            logger.debug(
                "Ignoring server message type: %s",
                message.get("type"),
            )
            return

        request_id = message.get("request_id")
        tool_name = message.get("tool_name")
        arguments = message.get("arguments", {})

        if (
            not isinstance(request_id, str)
            or not request_id
            or not isinstance(tool_name, str)
            or not tool_name
            or not isinstance(arguments, dict)
        ):
            logger.warning("Ignoring malformed command")
            return

        try:
            result = self.executor.execute(
                tool_name,
                arguments,
            )

            response = make_command_result(
                request_id=request_id,
                success=True,
                result=result,
            )
        except Exception as exc:
            logger.exception(
                "Agent tool execution failed: %s",
                tool_name,
            )

            response = make_command_result(
                request_id=request_id,
                success=False,
                error=str(exc),
            )

        await websocket.send(_encode(response))


def _encode(message: dict) -> str:
    import json

    return json.dumps(
        message,
        separators=(",", ":"),
    )
