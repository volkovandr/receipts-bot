"""
Deskewing service for receipt images.

Applies shear transformation to correct image skew.
"""

import cv2
import numpy as np
import logging
from typing import Tuple, Dict

logger = logging.getLogger(__name__)


def shear_image(image: np.ndarray, angle: float) -> np.ndarray:
    """
    Applies vertical shear transformation to deskew an image.

    This is better than rotation for receipts because:
    - Preserves original width (no expansion)
    - Pure vertical correction (no horizontal distortion)
    - More natural for vertically-oriented documents

    Args:
        image: Input image as numpy array (color or grayscale)
        angle: Skew angle in degrees (positive = tilted right)

    Returns:
        Deskewed image as numpy array
    """
    h, w = image.shape[:2]

    # Convert angle to shear factor
    # Positive angle means top of image tilts right, so we shear left
    # tan(angle) gives us the vertical shift per horizontal pixel
    shear_factor = -np.tan(np.radians(angle))

    # Calculate how much height we need to add
    # Maximum vertical shift will be at the edges
    max_shift = abs(shear_factor * w / 2)
    new_h = int(h + 2 * max_shift)

    # Create shear transformation matrix
    # Format: [[1, 0, tx], [shear_x, 1, ty]]
    # shear_x controls vertical shift based on horizontal position
    M = np.float32([
        [1, 0, 0],                    # No horizontal shift
        [shear_factor, 1, max_shift]  # Vertical shift = shear_factor * x + offset
    ])

    # Apply shear transformation with white background padding
    sheared = cv2.warpAffine(
        image, M, (w, new_h),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )

    return sheared


def deskew_image_by_angle(image_path: str, angle: float, output_path: str) -> Tuple[bool, Dict]:
    """
    Applies deskew correction to an image file.

    Args:
        image_path: Path to input image
        angle: Skew angle in degrees to correct
        output_path: Path to save deskewed image

    Returns:
        Tuple of (success, result_dict)
        result_dict contains:
        - success: bool
        - original_size: tuple (width, height)
        - new_size: tuple (width, height)
        - error: str (if failed)
    """
    try:
        # Load image (color)
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        original_height, original_width = image.shape[:2]

        logger.info(f"Deskewing image: {image_path}")
        logger.info(f"Original size: {original_width}x{original_height}")
        logger.info(f"Applying shear with angle: {angle:.2f}°")

        # Apply shear transformation
        deskewed = shear_image(image, angle)

        new_height, new_width = deskewed.shape[:2]
        logger.info(f"Deskewed size: {new_width}x{new_height}")
        logger.info(f"Width preserved: {original_width} pixels")

        # Save to output path
        cv2.imwrite(output_path, deskewed)
        logger.info(f"Deskewed image saved to: {output_path}")

        return True, {
            'success': True,
            'original_size': (original_width, original_height),
            'new_size': (new_width, new_height)
        }

    except Exception as e:
        logger.error(f"Failed to deskew image {image_path}: {e}")
        return False, {
            'success': False,
            'error': str(e)
        }
