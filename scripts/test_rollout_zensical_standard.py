"""Tests for resolve_publish_flags in rollout_zensical_standard.py.

Guards against the 2026-06-07 regression where a rollout without --no-publish
silently flipped build-only repos to publish=true (Configure Pages then fails
because Pages is disabled). See memory project_buildonly_rollout_gotcha.
"""
from audit_zensical_standard import REPOS_BUILD_ONLY, REPOS_PUBLISHING
from rollout_zensical_standard import resolve_publish_flags

BUILD_ONLY = REPOS_BUILD_ONLY[0]
PUBLISHING = REPOS_PUBLISHING[0]


def test_build_only_defaults_to_no_publish_and_allow_no_pages():
    # No flags given: build-only repo must NOT publish and must allow no pages.
    assert resolve_publish_flags(BUILD_ONLY, None, False) == (False, True)


def test_publishing_repo_defaults_to_publish():
    assert resolve_publish_flags(PUBLISHING, None, False) == (True, False)


def test_explicit_no_publish_on_publishing_repo_is_honored():
    assert resolve_publish_flags(PUBLISHING, False, False) == (False, False)


def test_explicit_publish_on_build_only_is_honored_but_still_allows_no_pages():
    # Operator override wins for publish, but allow-no-pages stays true (harmless;
    # only relaxes the drift Pages check) so the combo can't half-break.
    assert resolve_publish_flags(BUILD_ONLY, True, False) == (True, True)


def test_allow_no_pages_flag_respected_for_publishing_repo():
    assert resolve_publish_flags(PUBLISHING, None, True) == (True, True)


def test_unknown_repo_preserves_historical_publish_default():
    assert resolve_publish_flags("LukeEvansTech/some-brand-new-repo", None, False) == (True, False)


def test_every_build_only_repo_resolves_to_no_publish_by_default():
    for repo in REPOS_BUILD_ONLY:
        assert resolve_publish_flags(repo, None, False) == (False, True), repo
