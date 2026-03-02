"""Entry point for `python -m vibe_harness_mcp` and the console script."""

from vibe_harness_mcp.server import mcp


def main():
    """Run the Vibe Harness MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
