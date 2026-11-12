import pytest

from cloud_browser_worker import (
    WorkerError,
    build_search_url,
    parse_product_card,
    validate_search_query,
)


def test_search_query_is_validated_and_encoded():
    query = validate_search_query({"query": "body spray under ₹1000"})
    assert query == "body spray under ₹1000"
    assert build_search_url(query).startswith("https://www.flipkart.com/search?q=")
    assert "www.flipkart.com" in build_search_url(query)


@pytest.mark.parametrize("arguments", [None, {}, {"query": ""}, {"query": "x" * 201}, {"query": "hello\nworld"}])
def test_rejects_invalid_search_arguments(arguments):
    with pytest.raises(WorkerError):
        validate_search_query(arguments)


def test_extracts_only_grounded_public_product_fields():
    product = parse_product_card(
        "4.2 ★ 1,234 Ratings ₹799",
        "Example Body Spray 150 ml",
        "https://www.flipkart.com/example/p/itm123",
    )
    assert product == {
        "name": "Example Body Spray 150 ml",
        "price": "₹799",
        "rating": "4.2",
        "reviews": "1,234",
        "url": "https://www.flipkart.com/example/p/itm123",
    }


def test_does_not_return_links_to_untrusted_hosts():
    product = parse_product_card(
        "₹799",
        "Example Body Spray",
        "https://attacker.example/redirect",
    )
    assert product["url"] is None


def test_requires_name_and_price_to_accept_a_product():
    assert parse_product_card("₹799", "", None) is None
    assert parse_product_card("No listed price", "Example Body Spray", None) is None
