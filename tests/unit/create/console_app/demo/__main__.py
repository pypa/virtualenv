from __future__ import annotations


def run() -> None:
    print("magic")  # ruff:ignore[print]  # the demo prints its output, which the test reads from stdout


if __name__ == "__main__":
    run()
