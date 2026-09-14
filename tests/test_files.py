import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from ezy.errors import EzyRuntimeError


def test_create_write_read_file(ezy, tmp_path):
    p = tmp_path / "hello.txt"
    ezy.run(f'create file "{p}"\nwrite "Hello" to "{p}"\nsay read "{p}"\n')
    assert ezy.lines == ["Hello"]
    assert p.read_text() == "Hello"


def test_append_to_file(ezy, tmp_path):
    p = tmp_path / "log.txt"
    ezy.run(f'write "a" to "{p}"\nappend "b" to "{p}"\nsay read "{p}"\n')
    assert ezy.lines == ["ab"]


def test_delete_file(ezy, tmp_path):
    p = tmp_path / "gone.txt"
    p.write_text("x")
    ezy.run(f'delete file "{p}"\nsay file "{p}" exists\n')
    assert ezy.lines == ["false"]


def test_delete_nonexistent_file_raises(ezy, tmp_path):
    p = tmp_path / "nope.txt"
    with pytest.raises(EzyRuntimeError) as exc:
        ezy.run(f'delete file "{p}"\n')
    assert exc.value.error_type == "FileError"


def test_read_nonexistent_file_raises(ezy, tmp_path):
    p = tmp_path / "nope.txt"
    with pytest.raises(EzyRuntimeError) as exc:
        ezy.run(f'say read "{p}"\n')
    assert exc.value.error_type == "FileError"


def test_create_and_list_folder(ezy, tmp_path):
    folder = tmp_path / "projects"
    (tmp_path / "existing.txt").write_text("x")
    ezy.run(f'create folder "{folder}"\n')
    assert folder.is_dir()
    (folder / "a.txt").write_text("1")
    (folder / "b.txt").write_text("2")
    ezy.run(f'files = list files in "{folder}"\nsay length(files)\n')
    assert ezy.lines == ["2"]


def test_delete_folder_recursive(ezy, tmp_path):
    folder = tmp_path / "toDelete"
    folder.mkdir()
    (folder / "a.txt").write_text("1")
    ezy.run(f'delete folder "{folder}"\nsay folder "{folder}" exists\n')
    assert ezy.lines == ["false"]


def test_path_properties(ezy, tmp_path):
    p = tmp_path / "archive.tar.gz"
    p.write_text("data")
    ezy.run(f'p = path("{p}")\nsay p.name\nsay p.extension\n')
    assert ezy.lines == ["archive.tar.gz", "gz"]


def test_empty_file_read(ezy, tmp_path):
    p = tmp_path / "empty.txt"
    p.write_text("")
    ezy.run(f'say read "{p}"\nsay length(read "{p}")\n')
    assert ezy.lines == ["", "0"]


def test_write_creates_missing_parent_dirs(ezy, tmp_path):
    p = tmp_path / "nested" / "dir" / "file.txt"
    ezy.run(f'write "x" to "{p}"\n')
    assert p.read_text() == "x"


def test_read_binary_file_raises_clear_error(ezy, tmp_path):
    p = tmp_path / "binary.dat"
    p.write_bytes(bytes([0xFF, 0xFE, 0x00, 0x01, 0x80]))
    with pytest.raises(EzyRuntimeError) as exc:
        ezy.run(f'say read "{p}"\n')
    assert exc.value.error_type == "FileError"
