"""Smoke manual após uv sync; não executado no Python do sistema."""

import numpy as np
import pandas as pd


def summarize(values):
    observations = pd.DataFrame({"value": np.asarray(values, dtype=float)})
    return observations.describe()


if __name__ == "__main__":
    print(summarize(np.arange(5, dtype=float)))
