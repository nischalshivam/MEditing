from pathlib import Path

from PIL import Image

from scenebrain.product_hardening import ResourcePolicy, import_character_folder, inventory_gallery, validate_reference


def test_unreadable_reference_fails_closed(tmp_path: Path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not an image")
    result = validate_reference(bad)
    assert result["approval_state"] == "REJECTED"
    assert "UNREADABLE_IMAGE" in result["issues"]


def test_character_import_is_copied_and_deduplicated(tmp_path: Path):
    source = tmp_path / "source"
    folder = source / "walter white"
    folder.mkdir(parents=True)
    image = Image.new("RGB", (320, 320), "gray")
    image.save(folder / "a.jpg")
    image.save(folder / "duplicate.jpg")
    before = {p.name: p.read_bytes() for p in folder.iterdir()}

    manifest = import_character_folder(tmp_path / "media", "Breaking Bad", source)
    assert manifest["originals_modified"] is False
    assert manifest["characters"][0]["total_references"] == 1
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before
    assert inventory_gallery(tmp_path / "media")["gallery_count"] == 1


def test_resource_policy_fails_over_safely():
    policy = ResourcePolicy()
    assert policy.backend("whisper", {"whisper_cuda_runtime_pass": False}) == "CPU"
    assert policy.backend("whisper", {"whisper_cuda_runtime_pass": True}) == "CUDA"
    assert policy.backend("ffmpeg_encode", {"nvenc_runtime_pass": False}) == "CPU"
    assert policy.cpu_workers <= 4
    assert policy.heavy_gpu_concurrency == 1

