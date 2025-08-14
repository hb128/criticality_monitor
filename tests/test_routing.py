import numpy as np
from cm_modular.routing import AngleBiasedRouter

def test_path_true_length():
    # Triangle: 0-1-2 in a line
    D = np.array([[0.0, 10.0, 20.0],
                  [10.0, 0.0, 10.0],
                  [20.0, 10.0, 0.0]])
    X = np.array([0.0, 10.0, 20.0])
    Y = np.array([0.0, 0.0, 0.0])
    router = AngleBiasedRouter(X, Y)
    path = [0,1,2]
    assert router.path_true_length_m(D, path) == 20.0
