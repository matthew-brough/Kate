from app.settings import redis_url_with_password


def test_redis_url_with_password_adds_auth() -> None:
    assert (
        redis_url_with_password("redis://redis-master:6379/0", "p@ss word")
        == "redis://:p%40ss%20word@redis-master:6379/0"
    )


def test_redis_url_with_password_keeps_existing_auth() -> None:
    assert (
        redis_url_with_password("redis://:existing@redis-master:6379/0", "new")
        == "redis://:existing@redis-master:6379/0"
    )
