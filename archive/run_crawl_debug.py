import runpy, sys, traceback, logging, os
os.makedirs(r"data/raw", exist_ok=True)

logging.basicConfig(
    filename="crawl.log", level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8"
)

print("[debug] launching crawl.py …")
try:
    sys.argv = [
        "crawl.py",
        "--query", "入国 日本 手続き",
        "--max", "5",
        "--out", "data/raw",
        "--verbose"
    ]
    runpy.run_path("crawl.py", run_name="__main__")
    print("[debug] finished crawl.py")
except SystemExit as e:
    print("[debug] SystemExit:", e)
    logging.info("SystemExit: %s", e)
except Exception:
    traceback.print_exc()
    logging.exception("UNCAUGHT")
