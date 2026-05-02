import cv2

path = "C:/Users/pouss/Videos/Screen Recordings/vid1.mp4"
cap = cv2.VideoCapture(path)

print("Opened:", cap.isOpened())

while True:
    ret, frame = cap.read()
    print("Frame:", ret)

    if not ret:
        break

    cv2.imshow("Test", frame)

    if cv2.waitKey(30) == 27:
        break

cap.release()
cv2.destroyAllWindows()