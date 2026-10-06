import asyncio
import logging

from jarvis_agent.client import JarvisAgentClient
from jarvis_agent.config import AgentConfig
from jarvis_agent.executor import CommandExecutor
from jarvis_agent.windows_operations import NativeWindowsOperations


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = AgentConfig.from_environment()
    operations = NativeWindowsOperations()
    executor = CommandExecutor(operations=operations)
    client = JarvisAgentClient(config, executor)

    asyncio.run(client.run_forever())


if __name__ == "__main__":
    main()
