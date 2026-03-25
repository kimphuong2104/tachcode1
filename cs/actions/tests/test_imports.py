def test_imports():
    # Disable linter warning for unused imports
    # pylint: disable=unused-import
    import cs.audittrail  # noqa: F401
    import cs.taskboard  # noqa: F401

    import cs.actions  # noqa: F401
    import cs.actions.taskboards  # noqa: F401
    import cs.actions.tasks_plugin  # noqa: F401
