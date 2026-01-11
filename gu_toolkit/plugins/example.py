# You can delete this file; it's just an example.

__gu_exports__ = ["hello", "quad"]
__gu_priority__ = 200
__gu_enabled__=False

def _setup(ctx):
    if ctx.get("verbose"):
        print("✓ example_plugin ready")

def hello(name="world"):
    return f"hello {name}"

def quad(x):
    return x * x
