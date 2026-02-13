def test_import():
    import sys, os

    print("sys.path in pytest", sys.path[:5])
    import cerebras.cloud.sdk

    print("import success")
