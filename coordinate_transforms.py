import numpy as np
from scipy.optimize import curve_fit

def into_3(vectors):
    return np.append(vectors, [[1]] * vectors.shape[0], axis=1)

def from_3(vectors):
    return vectors[:, :2] / vectors[:, [2]]

def cylinder2cartesian(points: np.array):
    """points is (n, 2) array.
    [:, 0] is the radius, [:, 1] the angle (in rad)."""
    cartesian = points[:, 0] * np.array([np.cos(points[:, 1]), np.sin(points[:, 1])])
    return cartesian.T

def transform(vectors, matrix):
    vectors = into_3(vectors)
    transformed = vectors @ matrix
    return from_3(transformed)

def get_matrix_for_transform(vectors_in, vectors_out):
    assert len(vectors_in) == len(vectors_out) == 4
    
    def fit(vectors_in, *matrix_values):
        matrix = np.array(matrix_values + (1.,)).reshape((3, 3))
        return transform(vectors_in, matrix)
    
    *popt, _ = curve_fit(fit, vectors_in, vectors_out, np.identity(3).flatten()[:-1])
    matrix = np.array(popt + (1.,)).reshape((3, 3))
    return matrix
