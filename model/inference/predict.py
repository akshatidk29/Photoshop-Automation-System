from ultralytics import YOLO

model = YOLO("C:\\Users\\Vansh\\Desktop\\photoshopAutomation\\model\\inference\\best.pt")
model.predict(source="C:\\Users\\Vansh\\Desktop\\photoshopAutomation\\model\\inference\\test.jpg", conf=0.01, save=True)
