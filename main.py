"""Claude Virtual API - Entry point."""
import uvicorn
import logging

logging.basicConfig(level=logging.DEBUG)


def main():
    """Run the server."""
    uvicorn.run(
        "src.server:app",
        host="127.0.0.1",
        port=8080,
        reload=False,
        log_level="debug"
    )


if __name__ == "__main__":
    main()
