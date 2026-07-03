"""Allow running the sync server via: python -m cc.sync"""
from cc.sync.http_server import run

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CC Sync Server")
    parser.add_argument("--port", type=int, default=9100)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    run(port=args.port, host=args.host)
