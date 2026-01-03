"""
Skew detection service for receipt images.

Uses text line contours method to detect skew angle in images.
Analyzes images in regions to detect non-uniform skew.
"""

import cv2
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional
from math import ceil

logger = logging.getLogger(__name__)


def detect_skew_contours(gray_image: np.ndarray) -> Tuple[float, float, float, int]:
    """
    Detects skew angle in a grayscale image using text line analysis.

    Args:
        gray_image: Grayscale image as numpy array

    Returns:
        Tuple of (median_angle, mean_angle, std_angle, num_contours)
    """
    # Apply binary threshold with Otsu's method (inverted)
    _, binary = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Use morphological dilation with rectangular kernel to connect text into lines
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 2))
    dilated = cv2.dilate(binary, kernel, iterations=1)

    # Find contours in the dilated image
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter contours and extract angles
    angles = []
    for contour in contours:
        # Get bounding rectangle
        x, y, w, h = cv2.boundingRect(contour)

        # Filter: minimum width 50px, minimum height 5px, aspect ratio >= 3
        if w >= 50 and h >= 5 and w / h >= 3:
            # Get minimum area rectangle
            rect = cv2.minAreaRect(contour)
            width, height = rect[1]
            angle = rect[2]

            # Normalize angle
            # minAreaRect returns angle in range [-90, 0]
            # If width < height, the rectangle is rotated by 90°
            if width < height:
                angle = angle + 90

            # Further normalize to [-45, 45] range
            # Since we can't determine text orientation without OCR,
            # we assume skew should be small (< 45°)
            # This maps angles near 180° back to near 0°
            while angle > 45:
                angle -= 90
            while angle < -45:
                angle += 90

            angles.append(angle)

    if not angles:
        return 0.0, 0.0, 0.0, 0

    # Calculate statistics
    angles_array = np.array(angles)
    median_angle = float(np.median(angles_array))
    mean_angle = float(np.mean(angles_array))
    std_angle = float(np.std(angles_array))

    return median_angle, mean_angle, std_angle, len(angles)


def split_into_regions_smart(gray_image: np.ndarray) -> List[Tuple[int, int, np.ndarray]]:
    """
    Splits image into semi-square regions for regional skew analysis.

    Args:
        gray_image: Grayscale image as numpy array

    Returns:
        List of tuples: (y_start, y_end, region_image)
    """
    height, width = gray_image.shape

    # Calculate region height based on image width (creates square-ish regions)
    region_height = width

    # Calculate number of regions
    num_regions = ceil(height / region_height)

    # Check if last region would be too small (< 50% of target height)
    last_region_height = height - (num_regions - 1) * region_height
    if num_regions > 1 and last_region_height < region_height * 0.5:
        # Merge last region with previous
        num_regions -= 1
        region_height = height // num_regions

    # Split image into regions
    regions = []
    for i in range(num_regions):
        y_start = i * region_height
        y_end = min((i + 1) * region_height, height)
        region = gray_image[y_start:y_end, :]
        regions.append((y_start, y_end, region))

    return regions


def get_region_position_name(region_index: int, num_regions: int) -> str:
    """
    Maps region index to human-readable position name.

    Args:
        region_index: 0-based region index
        num_regions: Total number of regions

    Returns:
        Position name: "entire", "upper", "middle", "lower"
    """
    if num_regions == 1:
        return "entire"
    elif num_regions == 2:
        return "upper" if region_index == 0 else "lower"
    else:
        # 3+ regions: divide into thirds
        third = num_regions / 3
        if region_index < third:
            return "upper"
        elif region_index < 2 * third:
            return "middle"
        else:
            return "lower"


def analyze_image_skew(image_path: str) -> Dict:
    """
    Main entry point for skew analysis.

    Args:
        image_path: Path to image file

    Returns:
        Dictionary with skew analysis results:
        {
            'max_skew_angle': float,      # Highest absolute skew
            'max_skew_region': int,       # Region index (0-based)
            'num_regions': int,           # Total number of regions
            'region_details': [           # Per-region statistics
                {
                    'region': int,
                    'y_start': int,
                    'y_end': int,
                    'median': float,
                    'mean': float,
                    'std': float,
                    'contours': int
                }
            ],
            'overall_median': float,      # Overall median across all regions
            'overall_std': float          # Variation between regions
        }
    """
    try:
        # Load image as grayscale
        gray_image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if gray_image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        # Split into smart regions
        regions = split_into_regions_smart(gray_image)
        num_regions = len(regions)

        # Analyze skew for each region
        region_details = []
        all_medians = []
        max_abs_skew = 0.0
        max_skew_region = 0

        for i, (y_start, y_end, region) in enumerate(regions):
            median, mean, std, contours = detect_skew_contours(region)

            region_details.append({
                'region': i,
                'y_start': y_start,
                'y_end': y_end,
                'median': median,
                'mean': mean,
                'std': std,
                'contours': contours
            })

            all_medians.append(median)

            # Track region with maximum absolute skew
            if abs(median) > abs(max_abs_skew):
                max_abs_skew = median
                max_skew_region = i

        # Calculate overall statistics
        all_medians_array = np.array(all_medians)
        overall_median = float(np.median(all_medians_array))
        overall_std = float(np.std(all_medians_array))

        result = {
            'max_skew_angle': max_abs_skew,
            'max_skew_region': max_skew_region,
            'num_regions': num_regions,
            'region_details': region_details,
            'overall_median': overall_median,
            'overall_std': overall_std
        }

        logger.info(f"Skew analysis completed: max_angle={max_abs_skew:.2f}°, "
                   f"region={max_skew_region}, num_regions={num_regions}")

        return result

    except Exception as e:
        logger.error(f"Skew detection failed for {image_path}: {e}")
        # Return safe defaults on error
        return {
            'max_skew_angle': 0.0,
            'max_skew_region': 0,
            'num_regions': 1,
            'region_details': [],
            'overall_median': 0.0,
            'overall_std': 0.0,
            'error': str(e)
        }
