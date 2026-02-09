import threading
import cv2

class ThreadedCamera:
    def __init__(self, src=0):
        self.capture = cv2.VideoCapture(src, cv2.CAP_V4L2)
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()

    def update(self):
        while True:
            ret, frame = self.capture.read()
            if not ret:
                break
            self.frame = frame

    def read(self):
        return self.frame

