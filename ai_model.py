import cv2
import os

class VoterAIVerifier:
    def __init__(self, cascade_path=None):
        if cascade_path is None:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

    def detect_and_validate_face(self, image_path):
        """
        Validates if an uploaded voter photo contains a single valid facial image.
        """
        if not os.path.exists(image_path):
            return False, "Image file not found on server."

        image = cv2.imread(image_path)
        if image is None:
            return False, "Invalid image format or corrupt file."

        # Convert to Grayscale & equalize histogram for consistent contrast
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        # Detect faces with stricter filtering to eliminate false positives
        raw_faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=6,     # Increased to reduce false positive detections
            minSize=(60, 60)    # Ignores small background noise/objects
        )

        # Filter out tiny spurious detections relative to the largest detected face
        faces = []
        if len(raw_faces) > 0:
            # Find the max face area
            max_area = max(w * h for (x, y, w, h) in raw_faces)
            # Only count faces that are at least 30% of the primary face size
            faces = [f for f in raw_faces if (f[2] * f[3]) >= (0.3 * max_area)]

        if len(faces) == 0:
            return False, "No face detected. Please upload a clear, front-facing photo."
        if len(faces) > 1:
            return False, "Multiple faces detected. Please ensure a plain background with a single person."

        return True, "Facial validation successful."