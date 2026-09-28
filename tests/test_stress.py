"""Stress test for mcat: massive files (500k segments) and compute-heavy operations.

Run: python tests/test_stress.py
"""
import os
import sys
import time
import tempfile
import shutil
import gc
import tracemalloc
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cat_tool.file_handler import CATFileHandler, convert_to_po
from cat_tool.segmentation import advanced_segmenter, DEFAULT_RULES
from cat_tool.workers import SegmentationWorker
from cat_tool.formats.text import TextHandler
from cat_tool.formats.mcatdb import McatDbHandler


def format_bytes(b):
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def format_time(seconds):
    if seconds < 1:
        return f"{seconds*1000:.1f} ms"
    if seconds < 60:
        return f"{seconds:.2f} s"
    return f"{seconds/60:.1f} min"


def measure_memory():
    """Return current memory usage in MB."""
    import psutil
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)


def generate_massive_txt(path, num_segments=500000, avg_words=10):
    """Generate a large text file with many segments."""
    print(f"  Generating {num_segments:,} segments...")
    sentences = [
        "The quick brown fox jumps over the lazy dog.",
        "Translation memory systems improve productivity significantly.",
        "Segmentation rules vary by language and domain.",
        "Quality assurance checks catch common errors automatically.",
        "Glossary terms ensure consistent terminology across projects.",
        "Machine translation post-editing requires careful review.",
        "File formats like XLIFF and TMX enable interoperability.",
        "Large projects benefit from parallel processing.",
        "Unicode support is essential for global localization.",
        "Regular expressions power advanced segmentation rules.",
    ]
    with open(path, "w", encoding="utf-8") as f:
        for i in range(num_segments):
            s = sentences[i % len(sentences)]
            # Vary length slightly
            if i % 7 == 0:
                s = s + " " + s
            f.write(s + "\n")
    size = os.path.getsize(path)
    print(f"  Generated {format_bytes(size)} ({num_segments:,} lines)")


def generate_massive_po(path, num_segments=500000):
    """Generate a large PO file."""
    print(f"  Generating PO with {num_segments:,} entries...")
    header = (
        'msgid ""\n'
        'msgstr ""\n'
        '"Project-Id-Version: stress test\\n"\n'
        '"MIME-Version: 1.0\\n"\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Content-Transfer-Encoding: 8bit\\n"\n'
        '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n'
        "\n"
    )
    entries = []
    for i in range(num_segments):
        entries.append(
            f'msgid "Segment {i+1}: The quick brown fox jumps over the lazy dog."\n'
            f'msgstr "Segmento {i+1}: El zorro marrón salta sobre el perro perezoso."\n'
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(entries))
    size = os.path.getsize(path)
    print(f"  Generated {format_bytes(size)}")


def test_load_massive_txt():
    """Test loading a massive text file."""
    print("\n=== TEST: Load massive TXT (500k segments) ===")
    with tempfile.TemporaryDirectory() as td:
        txt_path = os.path.join(td, "massive.txt")
        generate_massive_txt(txt_path, 500000)

        gc.collect()
        tracemalloc.start()
        mem_before = measure_memory()

        t0 = time.perf_counter()
        handler = TextHandler()
        segments = handler.load(txt_path)
        t_load = time.perf_counter() - t0

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        mem_after = measure_memory()

        print(f"  Load time: {format_time(t_load)}")
        print(f"  Segments loaded: {len(segments):,}")
        print(f"  Memory delta: {mem_after - mem_before:.1f} MB (process)")
        print(f"  Tracemalloc peak: {peak / (1024*1024):.1f} MB")
        print(f"  Per-segment memory: {peak / len(segments) / 1024:.2f} KB")

        # Test save roundtrip
        out_path = os.path.join(td, "massive_out.txt")
        t0 = time.perf_counter()
        # TextHandler uses render for output
        handler.render(txt_path, segments, out_path)
        t_save = time.perf_counter() - t0
        print(f"  Save time: {format_time(t_save)}")
        print(f"  Output size: {format_bytes(os.path.getsize(out_path))}")

        return {
            "load_time": t_load,
            "save_time": t_save,
            "segments": len(segments),
            "mem_mb": mem_after - mem_before,
            "peak_mb": peak / (1024 * 1024),
        }


def test_load_massive_po():
    """Test loading a massive PO file."""
    print("\n=== TEST: Load massive PO (500k segments) ===")
    with tempfile.TemporaryDirectory() as td:
        po_path = os.path.join(td, "massive.po")
        generate_massive_po(po_path, 500000)

        gc.collect()
        tracemalloc.start()
        mem_before = measure_memory()

        t0 = time.perf_counter()
        handler = CATFileHandler()
        segments = handler.load_file(po_path)
        t_load = time.perf_counter() - t0

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        mem_after = measure_memory()

        print(f"  Load time: {format_time(t_load)}")
        print(f"  Segments loaded: {len(segments):,}")
        print(f"  Memory delta: {mem_after - mem_before:.1f} MB")
        print(f"  Tracemalloc peak: {peak / (1024*1024):.1f} MB")

        return {
            "load_time": t_load,
            "segments": len(segments),
            "mem_mb": mem_after - mem_before,
            "peak_mb": peak / (1024 * 1024),
        }


def test_segmentation_large_text():
    """Test segmentation on a large text (simulating 500k segments worth of text)."""
    print("\n=== TEST: Segmentation on large text ===")
    # Create a text that would produce ~500k segments
    # Using shorter text but with many segment boundaries
    text = "Sentence one. " * 100000  # ~100k sentences
    print(f"  Input text: {len(text):,} chars, ~100k sentences")

    gc.collect()
    tracemalloc.start()
    mem_before = measure_memory()

    t0 = time.perf_counter()
    segments = advanced_segmenter(text, DEFAULT_RULES, "en")
    t_seg = time.perf_counter() - t0

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    mem_after = measure_memory()

    print(f"  Segmentation time: {format_time(t_seg)}")
    print(f"  Segments produced: {len(segments):,}")
    print(f"  Memory delta: {mem_after - mem_before:.1f} MB")
    print(f"  Tracemalloc peak: {peak / (1024*1024):.1f} MB")

    return {
        "seg_time": t_seg,
        "segments": len(segments),
        "mem_mb": mem_after - mem_before,
        "peak_mb": peak / (1024 * 1024),
    }


def test_worker_chunking():
    """Test SegmentationWorker chunk emission on large segment list."""
    print("\n=== TEST: Worker chunk emission (500k segments) ===")
    # Create dummy segments
    segments = [
        {"index": i, "source": f"Segment {i}", "target": "", "source_clean": f"Segment {i}",
         "target_clean": "", "all_tags": [], "notes": "", "fuzzy": False,
         "translated": False, "locations": "", "source_location": {}, "store": None, "unit": None}
        for i in range(500000)
    ]
    print(f"  Created {len(segments):,} dummy segments")

    worker = SegmentationWorker()
    chunks_received = []
    total_received = 0

    def on_chunk(chunk, count, label):
        nonlocal total_received
        chunks_received.append(len(chunk))
        total_received += len(chunk)

    worker.chunk_ready.connect(on_chunk)

    gc.collect()
    mem_before = measure_memory()

    t0 = time.perf_counter()
    worker._emit_chunks(segments, "test")
    t_emit = time.perf_counter() - t0

    mem_after = measure_memory()

    print(f"  Chunk emission time: {format_time(t_emit)}")
    print(f"  Chunks emitted: {len(chunks_received)}")
    print(f"  Total segments in chunks: {total_received:,}")
    print(f"  Chunk sizes: min={min(chunks_received)}, max={max(chunks_received)}, avg={sum(chunks_received)/len(chunks_received):.1f}")
    print(f"  Memory delta: {mem_after - mem_before:.1f} MB")

    return {
        "emit_time": t_emit,
        "chunks": len(chunks_received),
        "total_segments": total_received,
        "mem_mb": mem_after - mem_before,
    }


def test_mcatdb_roundtrip():
    """Test MCAT.DB save/load with many segments."""
    print("\n=== TEST: MCAT.DB roundtrip (100k segments) ===")
    # 500k might be too slow for DB, use 100k
    segments = [
        {"index": i, "source": f"Source segment {i}", "target": f"Target segment {i}",
         "source_clean": f"Source segment {i}", "target_clean": f"Target segment {i}",
         "all_tags": [], "notes": "", "fuzzy": False, "translated": True,
         "locations": "", "source_location": {}, "store": None, "unit": None}
        for i in range(100000)
    ]
    print(f"  Created {len(segments):,} segments with translations")

    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "test.mcat.db")
        handler = McatDbHandler()

        gc.collect()
        mem_before = measure_memory()

        t0 = time.perf_counter()
        handler.save(segments, db_path)
        t_save = time.perf_counter() - t0

        mem_after_save = measure_memory()

        t0 = time.perf_counter()
        loaded = handler.load(db_path)
        t_load = time.perf_counter() - t0

        mem_after_load = measure_memory()

        print(f"  Save time: {format_time(t_save)}")
        print(f"  Load time: {format_time(t_load)}")
        print(f"  Segments saved: {len(segments):,}")
        print(f"  Segments loaded: {len(loaded):,}")
        print(f"  DB size: {format_bytes(os.path.getsize(db_path))}")
        print(f"  Memory delta (save): {mem_after_save - mem_before:.1f} MB")
        print(f"  Memory delta (load): {mem_after_load - mem_after_save:.1f} MB")

        return {
            "save_time": t_save,
            "load_time": t_load,
            "segments": len(segments),
            "db_size_mb": os.path.getsize(db_path) / (1024 * 1024),
            "mem_save_mb": mem_after_save - mem_before,
            "mem_load_mb": mem_after_load - mem_after_save,
        }


def test_convert_to_po_large():
    """Test convert_to_po on a large text file."""
    print("\n=== TEST: convert_to_po on large TXT (100k lines) ===")
    with tempfile.TemporaryDirectory() as td:
        txt_path = os.path.join(td, "large.txt")
        generate_massive_txt(txt_path, 100000)
        po_path = os.path.join(td, "large.txt.po")

        gc.collect()
        mem_before = measure_memory()

        t0 = time.perf_counter()
        convert_to_po(txt_path, po_path)
        t_conv = time.perf_counter() - t0

        mem_after = measure_memory()

        # Verify
        handler = CATFileHandler()
        segs = handler.load_file(po_path)

        print(f"  Convert time: {format_time(t_conv)}")
        print(f"  PO size: {format_bytes(os.path.getsize(po_path))}")
        print(f"  Segments in PO: {len(segs):,}")
        print(f"  Memory delta: {mem_after - mem_before:.1f} MB")

        return {
            "conv_time": t_conv,
            "segments": len(segs),
            "po_size_mb": os.path.getsize(po_path) / (1024 * 1024),
            "mem_mb": mem_after - mem_before,
        }


def test_ui_table_simulation():
    """Simulate table population with many rows (no actual Qt)."""
    print("\n=== TEST: Table population simulation (500k rows) ===")
    # Simulate what _on_segmentation_chunk does: extend a list
    table_rows = []

    segments = [
        {"index": i, "source": f"Segment {i}", "target": "", "source_clean": f"Segment {i}",
         "target_clean": "", "all_tags": [], "notes": "", "fuzzy": False,
         "translated": False, "locations": "", "source_location": {}, "store": None, "unit": None}
        for i in range(500000)
    ]

    gc.collect()
    mem_before = measure_memory()

    t0 = time.perf_counter()
    # Simulate chunked addition (10 at a time like the worker)
    chunk_size = 10
    for i in range(0, len(segments), chunk_size):
        chunk = segments[i:i + chunk_size]
        table_rows.extend(chunk)
    t_populate = time.perf_counter() - t0

    mem_after = measure_memory()

    print(f"  Population time: {format_time(t_populate)}")
    print(f"  Rows in table: {len(table_rows):,}")
    print(f"  Memory delta: {mem_after - mem_before:.1f} MB")
    print(f"  Per-row memory: {(mem_after - mem_before) * 1024 / len(table_rows):.2f} KB")

    return {
        "populate_time": t_populate,
        "rows": len(table_rows),
        "mem_mb": mem_after - mem_before,
    }


def main():
    print("=" * 60)
    print("MCAT STRESS TEST — 500k segments / compute-heavy ops")
    print("=" * 60)

    # Check dependencies
    try:
        import psutil
    except ImportError:
        print("Installing psutil for memory tracking...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil", "-q"])
        import psutil

    results = {}

    # Run tests
    results["txt_load"] = test_load_massive_txt()
    results["po_load"] = test_load_massive_po()
    results["segmentation"] = test_segmentation_large_text()
    results["worker_chunks"] = test_worker_chunking()
    results["mcatdb"] = test_mcatdb_roundtrip()
    results["convert_po"] = test_convert_to_po_large()
    results["table_sim"] = test_ui_table_simulation()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Test':<25} {'Time':>12} {'Segments':>12} {'Memory':>10}")
    print("-" * 60)
    for name, r in results.items():
        t = r.get("load_time") or r.get("seg_time") or r.get("emit_time") or r.get("save_time") or r.get("conv_time") or r.get("populate_time", 0)
        segs = r.get("segments", r.get("total_segments", r.get("rows", 0)))
        mem = r.get("mem_mb", r.get("mem_save_mb", 0))
        print(f"{name:<25} {format_time(t):>12} {segs:>12,} {mem:>9.1f} MB")

    print("\nKEY FINDINGS:")
    print("-" * 60)

    # Analyze
    txt_load = results["txt_load"]["load_time"]
    po_load = results["po_load"]["load_time"]
    seg_time = results["segmentation"]["seg_time"]
    emit_time = results["worker_chunks"]["emit_time"]
    populate_time = results["table_sim"]["populate_time"]

    print(f"1. TXT load (500k): {format_time(txt_load)} — {'OK' if txt_load < 5 else 'SLOW'}")
    print(f"2. PO load (500k): {format_time(po_load)} — {'OK' if po_load < 10 else 'SLOW'}")
    print(f"3. Segmentation (100k sent): {format_time(seg_time)} — {'OK' if seg_time < 5 else 'SLOW'}")
    print(f"4. Worker chunking (500k): {format_time(emit_time)} — {'OK' if emit_time < 1 else 'SLOW'}")
    print(f"5. Table population (500k): {format_time(populate_time)} — {'OK' if populate_time < 2 else 'SLOW'}")

    # Memory
    max_mem = max(r.get("mem_mb", 0) for r in results.values())
    print(f"\n6. Peak process memory delta: {max_mem:.1f} MB")
    print(f"   Per-segment overhead (TXT): {results['txt_load']['peak_mb'] / results['txt_load']['segments'] * 1024:.2f} KB")

    # Bottlenecks
    print("\nBOTTLENECKS IDENTIFIED:")
    if txt_load > 5:
        print("  - TXT loading: consider streaming/chunked parsing")
    if po_load > 10:
        print("  - PO loading: translate.storage parsing is slow at scale")
    if seg_time > 5:
        print("  - Segmentation: regex-based segmenter doesn't scale linearly")
    if emit_time > 1:
        print("  - Worker chunking: Python list slicing overhead")
    if populate_time > 2:
        print("  - Table population: list.extend() in loop — consider pre-allocation")

    print("\nRECOMMENDATIONS:")
    print("  - For 500k+ segments: use MCAT.DB format (SQLite, indexed)")
    print("  - Implement lazy/virtual table model (load visible rows only)")
    print("  - Add progress callbacks for long operations")
    print("  - Consider multiprocessing for segmentation (CPU-bound)")
    print("  - Streaming PO parser for large files")


if __name__ == "__main__":
    main()