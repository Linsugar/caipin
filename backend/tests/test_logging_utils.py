from app.logging_utils import redact_for_log, truncate_for_log


def test_redacts_api_keys_and_image_base64_payloads():
    payload = {
        "Authorization": "Bearer sk-test",
        "deepseek_api_key": "sk-test",
        "image_url": {"url": "data:image/jpeg;base64," + "a" * 1000},
    }

    redacted = redact_for_log(payload)

    assert redacted["Authorization"] == "***"
    assert redacted["deepseek_api_key"] == "***"
    assert redacted["image_url"]["url"].startswith("data:image/jpeg;base64,<redacted:")
    assert "sk-test" not in str(redacted)


def test_truncates_long_log_text():
    assert truncate_for_log("abcdef", max_chars=4) == "abcd...<truncated>"
