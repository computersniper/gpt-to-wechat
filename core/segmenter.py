"""
ChatGPT Sticker Segmentation and Processing Engine.

Detects, segments, mats, and normalizes ChatGPT-generated sticker sheets
(such as 3x3 grids with white die-cut outlines on dark backgrounds)
into transparent PNGs optimized for WeChat custom emojis.
"""

import os
from typing import List, Optional, Tuple, Union
import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import measure, morphology


class StickerResult:
    """Represents a single segmented sticker."""
    def __init__(self, index: int, image: Image.Image, bbox: Tuple[int, int, int, int], area: int, path: Optional[str] = None):
        self.index = index
        self.image = image
        self.bbox = bbox  # (minr, minc, maxr, maxc)
        self.area = area
        self.path = path

    def save(self, file_path: str, format: str = "PNG") -> str:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        self.image.save(file_path, format=format)
        self.path = file_path
        return file_path


class StickerSegmenter:
    """
    Intelligent segmentation algorithm for ChatGPT sticker sheets.
    """

    def __init__(
        self,
        bg_threshold: int = 35,
        min_area: int = 8000,
        margin: int = 8,
        target_size: int = 240,
        dilation_radius: int = 2
    ):
        """
        :param bg_threshold: Grayscale brightness threshold below which pixels are treated as background.
        :param min_area: Minimum pixel area to be recognized as a valid sticker.
        :param margin: Extra padding around bounding box.
        :param target_size: Output square dimensions in pixels (default 240x240 for standard WeChat emoji).
        :param dilation_radius: Radius for mask dilation to protect the white die-cut sticker border.
        """
        self.bg_threshold = bg_threshold
        self.min_area = min_area
        self.margin = margin
        self.target_size = target_size
        self.dilation_radius = dilation_radius

    def process(
        self,
        image_input: Union[str, Image.Image, bytes],
        output_dir: Optional[str] = None,
        prefix: str = "sticker"
    ) -> List[StickerResult]:
        """
        Processes an input sticker sheet and returns a list of StickerResults.
        """
        if isinstance(image_input, str):
            img = Image.open(image_input).convert("RGB")
        elif isinstance(image_input, bytes):
            import io
            img = Image.open(io.BytesIO(image_input)).convert("RGB")
        elif isinstance(image_input, Image.Image):
            img = image_input.convert("RGB")
        else:
            raise TypeError("Unsupported image_input type")

        arr = np.array(img)
        h, w, _ = arr.shape

        # Compute grayscale representation
        gray = np.mean(arr, axis=2)

        # Detect foreground (anything brighter than threshold)
        foreground_mask = gray > self.bg_threshold

        # Binary hole filling: ensures internal sticker elements (e.g. eyes, clothes) stay part of the sticker
        filled_mask = ndimage.binary_fill_holes(foreground_mask)

        # Remove tiny noise specs
        clean_mask = morphology.remove_small_objects(filled_mask, min_size=max(1000, self.min_area // 4))

        # Label connected components
        labels, num_features = ndimage.label(clean_mask)
        objects = measure.regionprops(labels)

        # Filter regions by minimum area
        valid_objects = [obj for obj in objects if obj.area >= self.min_area]

        if not valid_objects:
            # Fallback if threshold is too strict
            fallback_min = max(2000, self.min_area // 2)
            valid_objects = [obj for obj in objects if obj.area >= fallback_min]

        # Sort in reading order (grid layout: roughly top-to-bottom, left-to-right)
        row_bucket_size = max(50, h // 4)
        valid_objects.sort(key=lambda x: (round(x.centroid[0] / row_bucket_size), x.centroid[1]))

        results: List[StickerResult] = []

        for idx, obj in enumerate(valid_objects, 1):
            minr, minc, maxr, maxc = obj.bbox

            # Apply margin
            minr_padded = max(0, minr - self.margin)
            minc_padded = max(0, minc - self.margin)
            maxr_padded = min(h, maxr + self.margin)
            maxc_padded = min(w, maxc + self.margin)

            # Crop array and component mask
            cropped_arr = arr[minr_padded:maxr_padded, minc_padded:maxc_padded]
            cropped_mask = (labels[minr_padded:maxr_padded, minc_padded:maxc_padded] == obj.label)

            # Slightly dilate mask to ensure smooth white die-cut borders are completely included
            if self.dilation_radius > 0:
                cropped_mask = morphology.binary_dilation(cropped_mask, morphology.disk(self.dilation_radius))

            # Assemble RGBA
            rgba = np.zeros((cropped_arr.shape[0], cropped_arr.shape[1], 4), dtype=np.uint8)
            rgba[:, :, :3] = cropped_arr
            rgba[:, :, 3] = np.where(cropped_mask, 255, 0)

            sticker_img = Image.fromarray(rgba, "RGBA")

            # Center on square transparent canvas
            sw, sh = sticker_img.size
            max_dim = max(sw, sh)
            square_img = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
            offset_x = (max_dim - sw) // 2
            offset_y = (max_dim - sh) // 2
            square_img.paste(sticker_img, (offset_x, offset_y), sticker_img)

            # Resize to target dimension using high quality Lanczos filter
            final_img = square_img.resize((self.target_size, self.target_size), Image.Resampling.LANCZOS)

            result = StickerResult(
                index=idx,
                image=final_img,
                bbox=(minr_padded, minc_padded, maxr_padded, maxc_padded),
                area=obj.area
            )

            if output_dir:
                file_name = f"{prefix}_{idx:02d}.png"
                file_path = os.path.join(output_dir, file_name)
                result.save(file_path)

            results.append(result)

        return results


def split_stickers(
    image_path: str,
    output_dir: Optional[str] = None,
    target_size: int = 240,
    bg_threshold: int = 35
) -> List[StickerResult]:
    """Convenience helper function to segment stickers."""
    segmenter = StickerSegmenter(bg_threshold=bg_threshold, target_size=target_size)
    return segmenter.process(image_path, output_dir=output_dir)
