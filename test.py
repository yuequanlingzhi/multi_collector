import cv2

cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
#设置曝光为-6
cap.set(cv2.CAP_PROP_EXPOSURE, -6)

while True:
    ret, frame = cap.read()
    if not ret:
        break
    cv2.imshow("Frame", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()