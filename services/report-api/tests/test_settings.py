from app.settings import broker_url_with_redis_password


def test_broker_url_with_redis_password_adds_auth() -> None:
    assert (
        broker_url_with_redis_password("redis://redis-master:6379/0", "p@ss word")
        == "redis://:p%40ss%20word@redis-master:6379/0"
    )


def test_broker_url_with_redis_password_keeps_existing_auth() -> None:
    assert (
        broker_url_with_redis_password("redis://:existing@redis-master:6379/0", "new")
        == "redis://:existing@redis-master:6379/0"
    )
