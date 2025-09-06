"""Command-line interface for Zammad MCP server with HTTP/SSE support."""

import argparse
import logging
import sys

from .http_server import create_http_server
from .server import mcp

logger = logging.getLogger(__name__)


def main() -> None:
    """Main CLI entry point with support for stdio and HTTP/HTTPS modes."""
    parser = argparse.ArgumentParser(description="Zammad MCP Server")
    parser.add_argument(
        "--mode",
        choices=["stdio", "http"],
        default="stdio",
        help="Server mode: stdio (default) for MCP protocol, http for HTTP/HTTPS/SSE",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind HTTP server to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind HTTP server to (default: 8080)",
    )
    parser.add_argument(
        "--ssl",
        action="store_true",
        help="Enable HTTPS with SSL/TLS",
    )
    parser.add_argument(
        "--ssl-cert",
        help="Path to SSL certificate file (PEM format)",
    )
    parser.add_argument(
        "--ssl-key",
        help="Path to SSL private key file (PEM format)",
    )
    parser.add_argument(
        "--ssl-generate",
        action="store_true",
        help="Generate self-signed certificate if cert/key not provided",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if args.mode == "http":
        # Run in HTTP/HTTPS/SSE mode
        ssl_config = None
        
        if args.ssl or args.ssl_cert or args.ssl_key or args.ssl_generate:
            # SSL/HTTPS mode
            if args.ssl_generate and not (args.ssl_cert and args.ssl_key):
                # Generate self-signed certificate
                from .ssl_utils import generate_self_signed_cert
                cert_path, key_path = generate_self_signed_cert(args.host)
                logger.info(f"Generated self-signed certificate: {cert_path}")
                ssl_config = {"cert": cert_path, "key": key_path}
            elif args.ssl_cert and args.ssl_key:
                # Use provided certificate
                ssl_config = {"cert": args.ssl_cert, "key": args.ssl_key}
            else:
                logger.error("SSL enabled but no certificate provided. Use --ssl-cert and --ssl-key, or --ssl-generate")
                sys.exit(1)
                
            protocol = "HTTPS"
        else:
            protocol = "HTTP"
            
        logger.info(f"Starting Zammad MCP server in {protocol} mode on {args.host}:{args.port}")
        
        try:
            http_server = create_http_server(host=args.host, port=args.port, ssl_config=ssl_config)
            http_server.run()
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Failed to start {protocol} server: {e}")
            sys.exit(1)
    else:
        # Run in stdio mode (default MCP protocol)
        logger.info("Starting Zammad MCP server in stdio mode")
        try:
            # FastMCP handles its own async loop
            mcp.run()  # type: ignore[func-returns-value]
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Failed to start stdio server: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()