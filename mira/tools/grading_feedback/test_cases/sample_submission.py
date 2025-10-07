"""
Sample student submission for testing the grading tool.
This implements a simple binary search algorithm.
"""


def binary_search(arr, target):
    """
    Perform binary search on a sorted array.

    Args:
        arr: Sorted list of comparable elements
        target: Element to search for

    Returns:
        Index of target if found, -1 otherwise
    """
    left, right = 0, len(arr) - 1

    while left <= right:
        mid = (left + right) // 2

        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1


# Test the implementation
if __name__ == "__main__":
    test_array = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]

    # Test cases
    print(f"Search for 7: {binary_search(test_array, 7)}")  # Should return 3
    print(f"Search for 1: {binary_search(test_array, 1)}")  # Should return 0
    print(f"Search for 19: {binary_search(test_array, 19)}")  # Should return 9
    print(f"Search for 4: {binary_search(test_array, 4)}")  # Should return -1