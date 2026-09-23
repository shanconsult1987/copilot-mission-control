from mcp.server.fastmcp import FastMCP


mcp = FastMCP("Mission Control Server Point")


MISSIONS = {
    "ROVER-07": {
        "status": "active",
        "battery": 82,
    },
    "ROVER-08": {
        "status": "maintenance",
        "battery": 34,
    },
}


@mcp.tool()
def get_mission_status(rover_id: str) -> dict:
    """Get the current status of a rover."""

    if rover_id not in MISSIONS:
        return {
            "error": f"Rover {rover_id} was not found."
        }

    return {
        "rover_id": rover_id,
        **MISSIONS[rover_id],
    }


if __name__ == "__main__":
    mcp.run()