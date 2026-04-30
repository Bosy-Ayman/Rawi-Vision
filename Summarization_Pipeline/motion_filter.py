import cv2


class MotionFilter:
    def __init__(self, threshold=25, min_area=800):
        self.prev_frame = None
        self.threshold = threshold
        self.min_area = min_area

    def is_motion(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        if self.prev_frame is None:
            self.prev_frame = gray
            return True

        diff = cv2.absdiff(self.prev_frame, gray)
        _, thresh = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)

        motion_pixels = cv2.countNonZero(thresh)

        self.prev_frame = gray

        return motion_pixels > self.min_area