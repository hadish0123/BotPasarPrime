from app.security.telegram_init_data import validate_init_data


def test_invalid():
    assert validate_init_data("user=x&hash=bad", "token")[0] is False
