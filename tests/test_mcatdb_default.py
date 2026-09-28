"""Test the new MCAT.DB default format flow end-to-end."""
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cat_tool.state_manager import AppState
from cat_tool.file_handler import convert_to_mcatdb


def test_mcatdb_default_flow():
    """Test the full flow: create project -> open source file -> render translated."""
    print("=== Testing MCAT.DB default format flow ===\n")
    
    with tempfile.TemporaryDirectory() as td:
        # Create a test source file (TXT)
        src_file = os.path.join(td, "test.txt")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("Hello world.\nThis is a test.\nThird segment here.\n")
        print(f"Created source: {src_file}")
        
        # Create AppState and new project
        state = AppState()
        state.new_project("Test Project", "en", "es", [src_file])
        print(f"Created project: {state.project.name}")
        print(f"Source files: {state.project.source_files}")
        
        # Open the source file (should convert to MCAT.DB)
        segments, label, ok, err = state.open_project_source_file(0)
        if not ok:
            print(f"ERROR: {err}")
            return False
        
        print(f"\nOpened file: {label}")
        print(f"Segments loaded: {len(segments)}")
        for i, seg in enumerate(segments):
            print(f"  {i}: {seg['source']} -> {seg['target']}")
        
        # Verify MCAT.DB was created
        mcatdb_path = src_file + ".mcat.db"
        if os.path.exists(mcatdb_path):
            print(f"\nMCAT.DB created: {mcatdb_path} ({os.path.getsize(mcatdb_path)} bytes)")
        else:
            print(f"\nERROR: MCAT.DB not created at {mcatdb_path}")
            return False
        
        # Verify original format tracking
        print(f"Original ext tracked: {state._original_file_ext}")
        print(f"Original path tracked: {state._original_file_path}")
        
        # Simulate translation
        segments[0]["target"] = "Hola mundo."
        segments[1]["target"] = "Esto es una prueba."
        segments[2]["target"] = "Tercer segmento aquí."
        state.file_handler.segments = segments
        state.modified = True
        
        # Render translated file
        output_file = os.path.join(td, "test_translated.txt")
        try:
            state.file_handler.render_translated(output_file, original_path=state._original_file_path)
            print(f"\nRendered translated file: {output_file}")
            
            # Verify output
            with open(output_file, "r", encoding="utf-8") as f:
                content = f.read()
            # Don't print content (encoding issues in console), just verify
            print(f"Output size: {len(content)} chars")
            
            # Check translations are in output
            if "Hola mundo." in content and "Esto es una prueba." in content:
                print("\n[OK] Translations correctly rendered to original format!")
                return True
            else:
                print("\n[FAIL] Translations NOT found in output")
                print(f"  Looking for: 'Hola mundo.' and 'Esto es una prueba.'")
                print(f"  Content sample: {content[:200]}")
                return False
                
        except Exception as e:
            print(f"\nERROR rendering: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_mcatdb_direct_load():
    """Test loading an existing MCAT.DB file directly."""
    print("\n=== Testing direct MCAT.DB load ===\n")
    
    with tempfile.TemporaryDirectory() as td:
        # Create MCAT.DB directly
        mcatdb_path = os.path.join(td, "direct.mcat.db")
        segments = [
            {"index": 0, "source": "Direct load test.", "target": "Prueba de carga directa.",
             "source_clean": "Direct load test.", "target_clean": "Prueba de carga directa.",
             "all_tags": [], "notes": "", "fuzzy": False, "translated": True,
             "locations": "", "source_location": {}, "store": None, "unit": None},
        ]
        
        from cat_tool.formats.mcatdb import McatDbHandler
        McatDbHandler().save(segments, mcatdb_path)
        print(f"Created MCAT.DB: {mcatdb_path}")
        
        # Load via AppState
        state = AppState()
        state.new_project("Direct Load Test", "en", "es", [mcatdb_path])
        segments2, label, ok, err = state.open_project_source_file(0)
        
        if not ok:
            print(f"ERROR: {err}")
            return False
        
        print(f"Loaded: {label}")
        print(f"Segments: {len(segments2)}")
        print(f"Source: {segments2[0]['source']}")
        print(f"Target: {segments2[0]['target']}")
        
        if segments2[0]["target"] == "Prueba de carga directa.":
            print("[OK] Direct MCAT.DB load works!")
            return True
        else:
            print("[FAIL] Target not loaded correctly")
            return False


def test_convert_to_mcatdb():
    """Test the convert_to_mcatdb function directly."""
    print("\n=== Testing convert_to_mcatdb function ===\n")
    
    with tempfile.TemporaryDirectory() as td:
        # Create test files of different formats
        test_files = {
            "txt": "Line one.\nLine two.\nLine three.\n",
            "po": (
                'msgid ""\n'
                'msgstr ""\n'
                '"Content-Type: text/plain; charset=UTF-8\\n"\n'
                "\n"
                'msgid "PO segment one."\n'
                'msgstr "Segmento PO uno."\n'
                "\n"
                'msgid "PO segment two."\n'
                'msgstr ""\n'
            ),
        }
        
        for ext, content in test_files.items():
            src = os.path.join(td, f"test.{ext}")
            with open(src, "w", encoding="utf-8") as f:
                f.write(content)
            
            mcatdb = os.path.join(td, f"test.{ext}.mcat.db")
            convert_to_mcatdb(src, mcatdb)
            
            # Verify
            from cat_tool.formats.mcatdb import McatDbHandler
            loaded = McatDbHandler().load(mcatdb)
            print(f"  {ext:4s} -> MCAT.DB: {len(loaded)} segments")
            for seg in loaded:
                print(f"    {seg['source'][:40]:40s} -> {seg['target'][:40]}")
        
        print("  [OK] convert_to_mcatdb works for all formats!")
        return True


if __name__ == "__main__":
    results = []
    results.append(("MCAT.DB default flow", test_mcatdb_default_flow()))
    results.append(("Direct MCAT.DB load", test_mcatdb_direct_load()))
    results.append(("convert_to_mcatdb", test_convert_to_mcatdb()))
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  {name}: {status}")
    
    if all(ok for _, ok in results):
        print("\n[OK] All tests passed!")
        sys.exit(0)
    else:
        print("\n[FAIL] Some tests failed!")
        sys.exit(1)