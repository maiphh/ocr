from rapidocr import RapidOCR

ocr = RapidOCR(
    cls_model_dir=None
)

result, elapse = ocr("/Users/phu.mai/Projects/ocr/data/Absence-cert-BHXH-NewVer 2.pdf")
for line in result:
    print(line[1])  # prints recognized text
