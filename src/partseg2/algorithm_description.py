from partseg2.segment_algorithms import LowerThresholdAlgorithm, UpperThresholdAlgorithm, RangeThresholdAlgorithm
from project_utils.algorithms_description import AlgorithmProperty
from copy import  deepcopy

lower_threshold_algorithm = [AlgorithmProperty("threshold", "Threshold", 10000, (0, 10 ** 6), 100),
                       AlgorithmProperty("minimum_size", "Minimum size", 8000, (0, 10 ** 6), 1000),
                       AlgorithmProperty("use_gauss", "Use gauss", False, (True, False)),
                       AlgorithmProperty("gauss_radius", "Gauss radius", 1.0, (0, 10), 0.1)]

upper_threshold_algorithm = deepcopy(lower_threshold_algorithm)

range_threshold_algorithm = [AlgorithmProperty("lower_threshold", "Lower threshold", 10000, (0, 10 ** 6), 100),
                             AlgorithmProperty("upper_threshold", "Upper threshold", 10000, (0, 10 ** 6), 100),
                             AlgorithmProperty("minimum_size", "Minimum size", 8000, (0, 10 ** 6), 1000),
                             AlgorithmProperty("use_gauss", "Use gauss", False, (True, False)),
                             AlgorithmProperty("gauss_radius", "Gauss radius", 1.0, (0, 10), 0.1)]


part_algorithm_dict = {
    "Lower threshold": (lower_threshold_algorithm, LowerThresholdAlgorithm),
    "Upper threshold": (upper_threshold_algorithm, UpperThresholdAlgorithm),
    "Range threshold": (range_threshold_algorithm, RangeThresholdAlgorithm)
}