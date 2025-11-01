from dev_utils import is_devtools_related


def test_is_devtools_related_positive():
    assert is_devtools_related("A CLI for developers to deploy code")


def test_is_devtools_related_negative():
    assert not is_devtools_related("A cookbook for home chefs")
