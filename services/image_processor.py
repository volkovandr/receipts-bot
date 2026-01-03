"""
Image processing module for receipt images.

Processes receipt images by:
1. Cropping to detect and isolate the receipt
2. Converting to grayscale
3. Resizing to max 1200px height
"""

import os
import logging
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image
from services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Handles receipt image processing operations."""

    def __init__(self, processed_dir: str = "./images/processed"):
        """
        Initialize image processor.

        Args:
            processed_dir: Directory to save processed images
        """
        self.processed_dir = Path(processed_dir)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.max_height = 1200

    def process_receipt_image(self, input_path: str, skip_crop: bool = False) -> Optional[str]:
        """
        Process a receipt image: crop, grayscale, resize.

        Args:
            input_path: Path to the original image
            skip_crop: If True, skip the cropping step (e.g., for pre-scanned PDFs)

        Returns:
            Path to processed image, or None if processing failed
        """
        # Track processing duration with metrics
        with MetricsService.image_processing_duration.time():
            try:
                # Read image
                image = cv2.imread(input_path)
                if image is None:
                    logger.error(f"Failed to read image: {input_path}")
                    return None

                logger.info(f"Processing image: {input_path}, shape: {image.shape}, skip_crop: {skip_crop}")

                # Step 1: Convert to grayscale first (simplifies detection)
                grayscale = self._convert_to_grayscale(image)

                # Step 2: Crop to receipt (skip for PDFs as they are already scanned)
                if skip_crop:
                    cropped = grayscale
                    logger.info("Skipping crop step (already scanned)")
                else:
                    cropped = self._crop_receipt(grayscale)

                # Step 3: Resize if needed
                resized = self._resize_image(cropped)

                # Save processed image with JPEG compression
                output_path = self._generate_output_path(input_path)
                # Use JPEG quality setting (85 is good balance between quality and size)
                success = cv2.imwrite(str(output_path), resized, [cv2.IMWRITE_JPEG_QUALITY, 90])

                if not success:
                    logger.error(f"Failed to save processed image: {output_path}")
                    return None

                logger.info(f"Saved processed image: {output_path}, shape: {resized.shape}")
                return str(output_path)

            except Exception as e:
                logger.error(f"Error processing image {input_path}: {e}", exc_info=True)
                return None

    def _crop_receipt(self, image: np.ndarray) -> np.ndarray:
        """
        Detect and crop the receipt using multiple strategies.

        Args:
            image: Input image (BGR format)

        Returns:
            Cropped image containing the receipt
        """
        try:
            # Try multiple detection strategies
            strategies = [
                self._strategy_edge_detection,
                self._strategy_brightness_detection,
                self._strategy_color_based_detection
            ]

            for i, strategy in enumerate(strategies):
                result = strategy(image)
                if result is not None:
                    x, y, w, h = result

                    # Validate the crop is reasonable (between 20% and 90% of original)
                    crop_area = w * h
                    img_area = image.shape[0] * image.shape[1]
                    crop_percentage = crop_area / img_area

                    if 0.20 <= crop_percentage <= 0.90:
                        # Add small padding
                        pad_x = int(image.shape[1] * 0.02)
                        pad_y = int(image.shape[0] * 0.02)

                        x = max(0, x - pad_x)
                        y = max(0, y - pad_y)
                        w = min(image.shape[1] - x, w + 2 * pad_x)
                        h = min(image.shape[0] - y, h + 2 * pad_y)

                        cropped = image[y:y+h, x:x+w]
                        logger.info(f"Strategy {i} succeeded: {image.shape} -> {cropped.shape} ({crop_percentage*100:.1f}%)")
                        return cropped
                    else:
                        logger.debug(f"Strategy {i} crop too large/small: {crop_percentage*100:.1f}%")

            logger.warning("All cropping strategies failed, using original image")
            return image

        except Exception as e:
            logger.warning(f"Error cropping receipt, using original image: {e}")
            return image

    def _strategy_edge_detection(self, image: np.ndarray) -> Optional[tuple]:
        """Strategy 1: Edge detection with contour filtering."""
        try:
            # Image is already grayscale
            gray = image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (7, 7), 0)
            edges = cv2.Canny(blurred, 30, 100)

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
            dilated = cv2.dilate(edges, kernel, iterations=2)

            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Filter by aspect ratio and size
            for contour in sorted(contours, key=cv2.contourArea, reverse=True):
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = h / w if w > 0 else 0

                if aspect_ratio > 1.2:  # Receipt-like shape
                    return (x, y, w, h)

            return None
        except:
            return None

    def _strategy_brightness_detection(self, image: np.ndarray) -> Optional[tuple]:
        """Strategy 2: Detect bright receipt on dark background using thresholding."""
        try:
            # Image is already grayscale
            gray = image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Calculate threshold based on image statistics
            mean_brightness = np.mean(gray)
            threshold_value = max(mean_brightness + 30, 140)

            # Threshold to find bright areas (receipt)
            _, thresh = cv2.threshold(gray, threshold_value, 255, cv2.THRESH_BINARY)

            # Clean up with morphology - smaller kernel to preserve details
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
            morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

            # Additional opening to remove noise
            morph = cv2.morphologyEx(morph, cv2.MORPH_OPEN, kernel, iterations=1)

            # Find contours
            contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Find largest receipt-shaped contour
            for contour in sorted(contours, key=cv2.contourArea, reverse=True):
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = h / w if w > 0 else 0

                if aspect_ratio > 1.1:  # Slightly relaxed for this strategy
                    return (x, y, w, h)

            return None
        except:
            return None

    def _strategy_color_based_detection(self, image: np.ndarray) -> Optional[tuple]:
        """Strategy 3: Detect white/light receipt using brightness (works on grayscale)."""
        try:
            # Image is already grayscale, use simple thresholding
            gray = image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Threshold for bright/white paper (value > 170)
            _, mask = cv2.threshold(gray, 170, 255, cv2.THRESH_BINARY)

            # Clean up
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)

            # Find contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Find largest receipt-shaped contour
            for contour in sorted(contours, key=cv2.contourArea, reverse=True):
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = h / w if w > 0 else 0

                if aspect_ratio > 1.0:  # Very relaxed for color-based
                    return (x, y, w, h)

            return None
        except:
            return None

    def _convert_to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """
        Convert image to grayscale.

        Args:
            image: Input image (BGR or already grayscale)

        Returns:
            Grayscale image
        """
        if len(image.shape) == 2:
            # Already grayscale
            return image
        elif image.shape[2] == 3:
            # Convert BGR to grayscale
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            logger.warning(f"Unexpected image shape: {image.shape}, returning as-is")
            return image

    def _resize_image(self, image: np.ndarray) -> np.ndarray:
        """
        Resize image if height exceeds max_height, maintaining aspect ratio.

        Args:
            image: Input image

        Returns:
            Resized image (or original if already smaller)
        """
        height, width = image.shape[:2]

        if height <= self.max_height:
            logger.info(f"Image height {height}px <= {self.max_height}px, no resizing needed")
            return image

        # Calculate new dimensions maintaining aspect ratio
        ratio = self.max_height / height
        new_width = int(width * ratio)
        new_height = self.max_height

        resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        logger.info(f"Resized image: {width}x{height} -> {new_width}x{new_height}")

        return resized

    def _generate_output_path(self, input_path: str) -> Path:
        """
        Generate output path for processed image.

        Args:
            input_path: Path to original image

        Returns:
            Path for processed image
        """
        input_file = Path(input_path)
        # Keep the same filename, just change the directory
        output_path = self.processed_dir / input_file.name
        return output_path
