import hashlib

import pytest

from scripts.download_thermal_samples import fetch_ranges, range_parts


def test_range_parts_accepts_single_http_206_binary_payload():
    payload = b"\x00PBT\r\n\xff"
    headers = (
        b"HTTP/1.1 206 Partial Content\r\n"
        b"Content-Type: application/octet-stream\r\n"
        b"Content-Range: bytes 18-24/100\r\n\r\n"
    )

    assert range_parts(headers, payload) == {18: payload}


def test_range_parts_preserves_binary_multipart_payloads_with_crlf():
    first = b"\x00A\r\nB\xff"
    second = b"\x80\r\nZ"
    boundary = b"thermal-range-boundary"
    headers = (
        b"HTTP/1.1 206 Partial Content\r\n"
        b"Content-Type: multipart/byteranges; boundary=thermal-range-boundary\r\n\r\n"
    )
    body = (
        b"--" + boundary + b"\r\n"
        b"Content-Type: application/octet-stream\r\n"
        b"Content-Range: bytes 40-45/100\r\n\r\n"
        + first + b"\r\n"
        b"--" + boundary + b"\r\n"
        b"Content-Type: application/octet-stream\r\n"
        b"Content-Range: bytes 7-10/100\r\n\r\n"
        + second + b"\r\n"
        b"--" + boundary + b"--\r\n"
    )

    assert range_parts(headers, body) == {40: first, 7: second}


def test_range_parts_rejects_truncated_single_range_response():
    headers = (
        b"HTTP/1.1 206 Partial Content\r\n"
        b"Content-Type: application/octet-stream\r\n"
        b"Content-Range: bytes 5-9/100\r\n\r\n"
    )

    with pytest.raises(ValueError, match="Truncated byte-range response"):
        range_parts(headers, b"shrt")


def test_range_parts_rejects_response_without_content_range():
    headers = (
        b"HTTP/1.1 206 Partial Content\r\n"
        b"Content-Type: application/octet-stream\r\n\r\n"
    )

    with pytest.raises(ValueError, match="no full-scene fallback"):
        range_parts(headers, b"data")


def test_range_parts_rejects_server_full_response_to_range_request():
    headers = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/octet-stream\r\n"
        b"Content-Length: 1000\r\n\r\n"
    )

    with pytest.raises(ValueError, match="no full-scene fallback"):
        range_parts(headers, b"full scene")


def test_fetch_ranges_rejects_cached_range_with_wrong_requested_length(tmp_path):
    url = "https://example.invalid/product.img"
    requested = [(30, 32)]
    specification = "30-32"
    key = hashlib.sha256((url + specification).encode()).hexdigest()[:24]
    (tmp_path / f"{key}.http.txt").write_bytes(
        b"HTTP/1.1 206 Partial Content\r\n"
        b"Content-Type: application/octet-stream\r\n"
        b"Content-Range: bytes 30-31/100\r\n\r\n"
    )
    (tmp_path / f"{key}.bin").write_bytes(b"xy")

    with pytest.raises(ValueError, match="Incomplete/mismatched multipart range"):
        fetch_ranges(url, requested, tmp_path)
