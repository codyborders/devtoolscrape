from dev_utils import is_devtools_related


def test_is_devtools_related_positive():
    assert is_devtools_related("A CLI for developers to deploy code")


def test_is_devtools_related_negative():
    assert not is_devtools_related("A cookbook for home chefs")


def test_substring_false_positives_rejected():
    """Bug #5: keyword matching must use word boundaries, not substring 'in'.
    'log' should not match 'blog' or 'catalog'.
    'API' should not match 'therapist'.
    'CI' should not match 'social' or 'ancient'.
    'CD' should not match 'CDs' ... actually 'CD' as a standalone word is a
    valid match, but embedded inside other words it should not match.
    """
    # "log" embedded in "blog" -- must not match
    assert not is_devtools_related("A blog about cooking recipes")
    # "log" embedded in "catalog" -- must not match
    assert not is_devtools_related("An online catalog of vintage items")
    # "API" embedded in "therapist" -- must not match
    assert not is_devtools_related("Find a therapist near you")
    # "CI" embedded in "ancient" -- must not match
    assert not is_devtools_related("An ancient history forum")
    # "CI" embedded in "social" -- must not match
    assert not is_devtools_related("A social networking platform")


def test_whole_word_keywords_still_match():
    """Ensure legitimate whole-word keyword matches still work after the fix."""
    assert is_devtools_related("Set up CI for your project")
    assert is_devtools_related("Build a REST API quickly")
    assert is_devtools_related("A log aggregation tool")
    assert is_devtools_related("Continuous CD pipeline for containers")
