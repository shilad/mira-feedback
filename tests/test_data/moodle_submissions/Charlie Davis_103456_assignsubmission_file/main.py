#!/usr/bin/env python3
# Author: Charlie Davis
# Email: charlie.davis@college.org
# Student ID: 103456
# Date: 2024-01-15

def fibonacci(n):
    """Calculate fibonacci number.
    Written by Charlie Davis for CS101.
    """
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

if __name__ == "__main__":
    # Test the function
    for i in range(10):
        print(f"fib({i}) = {fibonacci(i)}")