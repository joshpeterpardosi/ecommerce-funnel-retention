import time
from pathlib import Path
import duckdb

def run_benchmark():
    conn = duckdb.connect()
    sql_files = ["funnel.sql", "cohort_retention.sql", "rfm_segmentation.sql", "data_quality.sql"]
    print("Running DuckDB Query Latency Benchmark...\n" + "-" * 50)
    
    for filename in sql_files:
        filepath = Path("sql") / filename
        query = filepath.read_text(encoding="utf-8")
        
        # Warmup run
        conn.execute(query).df()
        
        # Measured run
        start_time = time.perf_counter()
        df = conn.execute(query).df()
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        print(f"[{filename}] Execution time: {elapsed_ms:.2f} ms ({len(df)} rows returned)")

if __name__ == "__main__":
    run_benchmark()
