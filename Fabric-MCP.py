import asyncio
import os

from azure.identity import DefaultAzureCredential
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("Fabric Data Agent")


WORKSPACE_ID = os.environ["FABRIC_WORKSPACE_ID"]
DATA_AGENT_ID = os.environ["FABRIC_DATA_AGENT_ID"]


FABRIC_MCP_URL = (
    "https://api.fabric.microsoft.com/v1/mcp/"
    f"workspaces/{WORKSPACE_ID}/"
    f"dataagents/{DATA_AGENT_ID}/agent"
)


credential = DefaultAzureCredential()


def get_headers():
    token = credential.get_token(
        "https://api.fabric.microsoft.com/.default"
    )

    return {
        "Authorization": f"Bearer {token.token}"
    }


async def ask_fabric(question: str) -> str:

    headers = get_headers()

    async with streamablehttp_client(
        FABRIC_MCP_URL,
        headers=headers
    ) as (read, write, _):

        async with ClientSession(read, write) as session:

            await session.initialize()

            tools = await session.list_tools()

            if not tools.tools:
                return "No Fabric Data Agent tool was found."

            fabric_tool = tools.tools[0]

            argument_name = next(
                iter(
                    fabric_tool.inputSchema["properties"]
                )
            )

            result = await session.call_tool(
                fabric_tool.name,
                {
                    argument_name: question
                }
            )

            answers = []

            for block in result.content:

                if block.type == "text":
                    answers.append(block.text)

            return "\n".join(answers)


@mcp.tool()
async def ask_fabric_data_agent(
    question: str
) -> str:
    """
    Ask the Microsoft Fabric Data Agent
    a natural-language question about
    enterprise data.
    """

    return await ask_fabric(question)


if __name__ == "__main__":
    mcp.run()