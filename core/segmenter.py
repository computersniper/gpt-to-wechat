"""
ChatGPT Sticker Segmentation and Processing Engine.

Detects, segments, mats, and normalizes ChatGPT-generated sticker sheets
(supporting 3x3 / 2x2 grids, dark backgrounds, light backgrounds, and fake checkerboard backgrounds)
into transparent PNGs optimized for WeChat custom emojis.
"""

import os
from typing import List, Optional, Tuple, Union
import numpy as np
from PIL import Image
from scipy import ndimage

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from skimage import measure, morphology
    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False


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
    Supports smart grid slicing (with GrabCut background matting for dark, light, or checkerboard backgrounds)
    and contour-based connected component detection.
    """

    def __init__(
        self,
        mode: str = "auto",
        bg_threshold: int = 35,
        min_area: Optional[int] = None,
        margin: int = 8,
        target_size: int = 240,
        dilation_radius: int = 0,
        grid_rows: int = 3,
        grid_cols: int = 3
    ):
        """
        :param mode: Slicing mode ('auto', 'grid_3x3', 'grid_2x2', 'grid_4x4', 'contour').
        :param bg_threshold: Grayscale brightness threshold below which pixels are treated as background in contour mode.
        :param min_area: Minimum pixel area to be recognized as a valid sticker (None for adaptive).
        :param margin: Extra padding around bounding box.
        :param target_size: Output square dimensions in pixels (default 240x240 for standard WeChat emoji).
        :param dilation_radius: Radius for mask dilation to protect the white die-cut sticker border.
        :param grid_rows: Number of rows in grid mode.
        :param grid_cols: Number of columns in grid mode.
        """
        self.mode = mode
        self.bg_threshold = bg_threshold
        self.min_area = min_area
        self.margin = margin
        self.target_size = target_size
        self.dilation_radius = dilation_radius
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols

    @staticmethod
    def detect_background_type(arr: np.ndarray) -> str:
        """
        Detects background characteristics by sampling image borders:
        - 'checkerboard': alternating light/gray squares (AI fake transparency)
        - 'light': white or bright light-colored background
        - 'dark': black or dark background
        """
        h, w, _ = arr.shape
        border_size = max(5, min(h, w) // 50)
        edges = np.concatenate([
            arr[:border_size, :, :].reshape(-1, 3),
            arr[-border_size:, :, :].reshape(-1, 3),
            arr[:, :border_size, :].reshape(-1, 3),
            arr[:, -border_size:, :].reshape(-1, 3)
        ])
        gray_edges = np.mean(edges, axis=1)
        mean_val = float(np.mean(gray_edges))
        std_val = float(np.std(gray_edges))

        if std_val > 15 and mean_val > 120:
            return "checkerboard"
        elif mean_val > 120:
            return "light"
        else:
            return "dark"

    def _process_grid(
        self,
        arr: np.ndarray,
        rows: int = 3,
        cols: int = 3,
        output_dir: Optional[str] = None,
        prefix: str = "sticker"
    ) -> List[StickerResult]:
        """
        Slices image into rows x cols grid and performs background matting and centering for each cell.
        """
        h, w, _ = arr.shape
        cell_h = h // rows
        cell_w = w // cols
        results: List[StickerResult] = []

        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c + 1
                y1, y2 = r * cell_h, (r + 1) * cell_h
                x1, x2 = c * cell_w, (c + 1) * cell_w
                cell = arr[y1:y2, x1:x2]
                ch, cw, _ = cell.shape

                # Perform matting using GrabCut if cv2 is available
                if HAS_CV2:
                    margin_offset = max(6, min(cw, ch) // 30)
                    rect = (margin_offset, margin_offset, cw - 2 * margin_offset, ch - 2 * margin_offset)
                    mask = np.zeros((ch, cw), np.uint8)
                    bgd_model = np.zeros((1, 65), np.float64)
                    fgd_model = np.zeros((1, 65), np.float64)

                    try:
                        cv2.grabCut(cell, mask, rect, bgd_model, fgd_model, 3, cv2.GC_INIT_WITH_RECT)
                        fg_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
                    except Exception:
                        # Fallback to threshold
                        gray = np.mean(cell, axis=2)
                        fg_mask = np.where(gray > self.bg_threshold, 255, 0).astype(np.uint8)
                else:
                    gray = np.mean(cell, axis=2)
                    fg_mask = np.where(gray > self.bg_threshold, 255, 0).astype(np.uint8)

                # Fill internal holes (eyes, clothes, white interiors)
                filled = ndimage.binary_fill_holes(fg_mask > 0)
                alpha = (filled * 255).astype(np.uint8)

                # Bounding box of segmented sticker
                coords = np.argwhere(alpha > 0)
                if len(coords) > 50:
                    y_min, x_min = coords.min(axis=0)
                    y_max, x_max = coords.max(axis=0)

                    # Apply margin
                    y_min = max(0, y_min - self.margin)
                    x_min = max(0, x_min - self.margin)
                    y_max = min(ch, y_max + self.margin)
                    x_max = min(cw, x_max + self.margin)

                    cropped_cell = cell[y_min:y_max+1, x_min:x_max+1]
                    cropped_alpha = alpha[y_min:y_max+1, x_min:x_max+1]
                    area = int(np.count_nonzero(cropped_alpha))
                else:
                    cropped_cell = cell
                    cropped_alpha = alpha
                    area = 0
                    y_min, x_min, y_max, x_max = 0, 0, ch - 1, cw - 1

                # Assemble RGBA
                rgba = np.zeros((cropped_cell.shape[0], cropped_cell.shape[1], 4), dtype=np.uint8)
                rgba[:, :, :3] = cropped_cell
                rgba[:, :, 3] = cropped_alpha

                sticker_img = Image.fromarray(rgba, "RGBA")
                sw, sh = sticker_img.size
                max_dim = max(sw, sh)
                square_img = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
                square_img.paste(sticker_img, ((max_dim - sw) // 2, (max_dim - sh) // 2), sticker_img)
                final_img = square_img.resize((self.target_size, self.target_size), Image.Resampling.LANCZOS)

                abs_bbox = (y1 + y_min, x1 + x_min, y1 + y_max, x1 + x_max)
                result = StickerResult(
                    index=idx,
                    image=final_img,
                    bbox=abs_bbox,
                    area=area
                )

                if output_dir:
                    file_name = f"{prefix}_{idx:02d}.png"
                    result.save(os.path.join(output_dir, file_name))

                results.append(result)

        return results

    def _process_contour(
        self,
        arr: np.ndarray,
        output_dir: Optional[str] = None,
        prefix: str = "sticker"
    ) -> List[StickerResult]:
        """
        Segments stickers using connected component labeling and morphological contour analysis.
        Best suited for irregular layouts on dark/black backgrounds.
        """
        h, w, _ = arr.shape
        min_area = self.min_area if self.min_area is not None else max(1000, (w * h) // 120)

        # Compute grayscale representation
        gray = np.mean(arr, axis=2)

        # Detect foreground
        foreground_mask = gray > self.bg_threshold

        # Binary hole filling: ensures internal sticker elements stay part of the sticker
        filled_mask = ndimage.binary_fill_holes(foreground_mask)

        # Remove tiny noise specs
        min_component_size = max(500, min_area // 4)
        if HAS_SKIMAGE:
            clean_mask = morphology.remove_small_objects(filled_mask, min_size=min_component_size)
            labels, num_features = ndimage.label(clean_mask)
            objects = measure.regionprops(labels)
            valid_objects = [
                (obj.label, obj.bbox, obj.area, obj.centroid)
                for obj in objects if obj.area >= min_area
            ]
            if not valid_objects:
                fallback_min = max(1000, min_area // 2)
                valid_objects = [
                    (obj.label, obj.bbox, obj.area, obj.centroid)
                    for obj in objects if obj.area >= fallback_min
                ]
        else:
            labels, num_features = ndimage.label(filled_mask)
            areas = ndimage.sum(filled_mask, labels, range(1, num_features + 1))
            slices = ndimage.find_objects(labels)
            centroids = ndimage.center_of_mass(filled_mask, labels, range(1, num_features + 1))

            valid_objects = []
            for i in range(num_features):
                if areas[i] >= min_area:
                    slc = slices[i]
                    bbox = (slc[0].start, slc[1].start, slc[0].stop, slc[1].stop)
                    valid_objects.append((i + 1, bbox, areas[i], centroids[i]))

            if not valid_objects:
                fallback_min = max(1000, min_area // 2)
                for i in range(num_features):
                    if areas[i] >= fallback_min:
                        slc = slices[i]
                        bbox = (slc[0].start, slc[1].start, slc[0].stop, slc[1].stop)
                        valid_objects.append((i + 1, bbox, areas[i], centroids[i]))

        # Filter out objects that cover > 80% of the entire image (unsegmented background)
        valid_objects = [obj for obj in valid_objects if obj[2] < (h * w * 0.8)]

        # Sort in reading order (grid layout: roughly top-to-bottom, left-to-right)
        row_bucket_size = max(50, h // 4)
        valid_objects.sort(key=lambda x: (round(x[3][0] / row_bucket_size), x[3][1]))

        results: List[StickerResult] = []

        for idx, (obj_label, bbox, obj_area, _) in enumerate(valid_objects, 1):
            minr, minc, maxr, maxc = bbox

            # Apply margin
            minr_padded = max(0, minr - self.margin)
            minc_padded = max(0, minc - self.margin)
            maxr_padded = min(h, maxr + self.margin)
            maxc_padded = min(w, maxc + self.margin)

            cropped_arr = arr[minr_padded:maxr_padded, minc_padded:maxc_padded]
            cropped_gray = gray[minr_padded:maxr_padded, minc_padded:maxc_padded]
            base_mask = (labels[minr_padded:maxr_padded, minc_padded:maxc_padded] == obj_label)

            cropped_mask = base_mask & (cropped_gray > self.bg_threshold)
            cropped_mask = ndimage.binary_fill_holes(cropped_mask)

            if self.dilation_radius > 0:
                if HAS_SKIMAGE:
                    dilated = morphology.binary_dilation(cropped_mask, morphology.disk(self.dilation_radius))
                else:
                    r = self.dilation_radius
                    y, x = np.ogrid[-r:r+1, -r:r+1]
                    struct = (x * x + y * y) <= (r * r)
                    dilated = ndimage.binary_dilation(cropped_mask, structure=struct)
                cropped_mask = dilated & (cropped_gray > max(15, self.bg_threshold - 10))
                cropped_mask = ndimage.binary_fill_holes(cropped_mask)

            rgba = np.zeros((cropped_arr.shape[0], cropped_arr.shape[1], 4), dtype=np.uint8)
            rgba[:, :, :3] = cropped_arr
            rgba[:, :, 3] = np.where(cropped_mask, 255, 0)

            sticker_img = Image.fromarray(rgba, "RGBA")
            sw, sh = sticker_img.size
            max_dim = max(sw, sh)
            square_img = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
            offset_x = (max_dim - sw) // 2
            offset_y = (max_dim - sh) // 2
            square_img.paste(sticker_img, (offset_x, offset_y), sticker_img)
            final_img = square_img.resize((self.target_size, self.target_size), Image.Resampling.LANCZOS)

            result = StickerResult(
                index=idx,
                image=final_img,
                bbox=(minr_padded, minc_padded, maxr_padded, maxc_padded),
                area=int(obj_area)
            )

            if output_dir:
                file_name = f"{prefix}_{idx:02d}.png"
                file_path = os.path.join(output_dir, file_name)
                result.save(file_path)

            results.append(result)

        return results

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
        bg_type = self.detect_background_type(arr)

        if self.mode == "grid_3x3" or (self.mode == "grid" and self.grid_rows == 3 and self.grid_cols == 3):
            return self._process_grid(arr, rows=3, cols=3, output_dir=output_dir, prefix=prefix)
        elif self.mode == "grid_2x2":
            return self._process_grid(arr, rows=2, cols=2, output_dir=output_dir, prefix=prefix)
        elif self.mode == "grid_4x4":
            return self._process_grid(arr, rows=4, cols=4, output_dir=output_dir, prefix=prefix)
        elif self.mode == "contour":
            return self._process_contour(arr, output_dir=output_dir, prefix=prefix)
        else:  # mode == "auto"
            # If checkerboard or light background, AI sticker sheets are almost always 3x3 grids
            if bg_type in ("checkerboard", "light"):
                return self._process_grid(arr, rows=self.grid_rows, cols=self.grid_cols, output_dir=output_dir, prefix=prefix)
            else:
                # Dark background: try contour detection first
                stickers = self._process_contour(arr, output_dir=output_dir, prefix=prefix)
                if len(stickers) >= 2:
                    return stickers
                else:
                    # Fallback to 3x3 grid
                    return self._process_grid(arr, rows=self.grid_rows, cols=self.grid_cols, output_dir=output_dir, prefix=prefix)


def split_stickers(
    image_path: str,
    output_dir: Optional[str] = None,
    target_size: int = 240,
    bg_threshold: int = 35,
    mode: str = "auto"
) -> List[StickerResult]:
    """Convenience helper function to segment stickers."""
    segmenter = StickerSegmenter(mode=mode, bg_threshold=bg_threshold, target_size=target_size)
    return segmenter.process(image_path, output_dir=output_dir)
