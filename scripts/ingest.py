import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ingestion import run_full_ingestion


def main():
    print("Running full ingestion pipeline...")
    total_chunks = run_full_ingestion()
    print(f"Total chunks ingested: {total_chunks}")


if __name__ == "__main__":
    main()