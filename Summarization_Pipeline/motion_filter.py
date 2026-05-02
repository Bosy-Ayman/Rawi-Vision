import cv2
import numpy as np
import logging
from collections import deque

logger = logging.getLogger(__name__)


class MotionFilter:
    def __init__(
        self,
        threshold: int = 25,
        min_area: int = 800,
        adaptive: bool = True,
        history_len: int = 30,        
        global_change_ratio: float = 0.80,  
    ):
        self.base_threshold = threshold
        self.threshold = threshold
        self.min_area = min_area
        self.adaptive = adaptive
        self.global_change_ratio = global_change_ratio

        self.prev_frame = None

        # dynamically re-calibrate the threshold for this scene.
        self._motion_history: deque = deque(maxlen=history_len)

        # morphological kernel to kill salt-and-pepper noise
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

  

    def is_motion(self, frame: np.ndarray) -> bool:
        
        gray = self._preprocess(frame)

        if self.prev_frame is None:
            self.prev_frame = gray
            return True   # baseline keyframe

        diff = cv2.absdiff(self.prev_frame, gray)
        self.prev_frame = gray

        _, thresh = cv2.threshold(
            diff, self.threshold, 255, cv2.THRESH_BINARY
        )

        # Noise removal (morphological erosion then dilation) 
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, self._kernel)

        total_pixels = thresh.size
        motion_pixels = cv2.countNonZero(thresh)
        motion_ratio = motion_pixels / total_pixels

        # Global illumination guard
        if motion_ratio > self.global_change_ratio:
            logger.debug(
                f"Global illumination event detected "
                f"(ratio={motion_ratio:.2f}) – skipping frame"
            )
            self._adapt(motion_ratio)
            return False

        # Adaptive threshold update
        self._adapt(motion_ratio)

        return motion_pixels > self.min_area

    def reset(self):
        self.prev_frame = None
        self._motion_history.clear()
        self.threshold = self.base_threshold


    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)
        return gray

    def _adapt(self, motion_ratio: float):
        if not self.adaptive:
            return

        self._motion_history.append(motion_ratio)

        if len(self._motion_history) < 10:
            return  

        background_ratio = float(np.median(self._motion_history))
        background_pixels = background_ratio * (640 * 360)  

        new_threshold = int(
            np.clip(self.base_threshold + background_pixels * 0.01, 10, 60)
        )

        if new_threshold != self.threshold:
            logger.debug(
                f"Adaptive threshold: {self.threshold} → {new_threshold} "
                f"(background_ratio={background_ratio:.4f})"
            )
            self.threshold = new_threshold
