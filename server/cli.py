"""Command-line entry point for the installed flatnotes application."""

import argparse
import os

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Run the flatnotes web server.")
    parser.add_argument(
        "--host", default=os.getenv("FLATNOTES_HOST", "127.0.0.1")
    )
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("FLATNOTES_PORT", "8080"))
    )
    parser.add_argument(
        "--forwarded-allow-ips",
        default=os.getenv("FLATNOTES_FORWARDED_ALLOW_IPS", "127.0.0.1"),
        help="Trusted reverse proxy addresses for forwarded headers.",
    )
    args = parser.parse_args()
    uvicorn.run(
        "flatnotes.main:app",
        host=args.host,
        port=args.port,
        proxy_headers=True,
        forwarded_allow_ips=args.forwarded_allow_ips,
    )


if __name__ == "__main__":
    main()
