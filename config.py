BHXH_SCHEMA = {
    "Số serial": {
        "type": "string",
        "description": "Document serial number, usually appears at the top, after phrases like: Số, Ký hiệu, Serial, Seri, Số hiệu, No., Số CT, Mã Y tế,...",
        "example": "123456789"
    },

    "Mã BHXH": {
        "type": "string",
        "description": "Social insurance number (BHXH). Usually appears after phrases like 'Mã BHXH', 'Số BHXH', or combined in 'Mã số BHXH/Thẻ BHYT số: ...'. Always 10 digits starting with a number. Example: in 'Mã số BHXH/Thẻ BHYT số: DN475912213507875297', the BHXH number is '9122135078'.",
        "example": "9122135078"
    },

    "Mã BHYT": {
        "type": "string",
        "description": "Health insurance card number (BHYT). Often appears after 'BHYT', 'Mã thẻ', or 'Số thẻ'. Starts with 2 uppercase letters followed by digits, e.g. 'DN475912213507875297' or 'HC4797929137657'. Extract the full code.",
        "example": "DN475912213507875297",
        "relation_to_BHXH": "The 10-digit 'Mã BHXH' is the middle part of the 'Mã BHYT'."
    },

    "Loại chứng từ": {
        "type": "string",
        "description": "Identify and extract the main document title indicating its type. Usually starts with 'GIẤY' (e.g. 'GIẤY RA VIỆN', 'GIẤY CHỨNG SINH', 'GIẤY KHAI SINH', 'GIẤY CHỨNG NHẬN NGHỈ VIỆC HƯỞNG BHXH'). Fix OCR errors or missing accents if clear.",
        "example": "GIẤY CHỨNG NHẬN NGHỈ VIỆC HƯỞNG BHXH"
    },

    "Họ và tên người bệnh": {
        "type": "string",
        "description": "Full name of the patient, in uppercase, with spaces between words. Usually appears after 'Họ tên', 'Người bệnh', or 'Chủ thẻ'.",
        "example": "NGUYỄN VĂN A"
    },

    "CCCD/CMND": {
        "type": "string",
        "description": "Personal ID (CCCD/CMND). Extract number after 'CCCD', 'CMND', 'Định danh cá nhân', or 'Hộ chiếu'. If not found, return 'Not Found'.",
        "example": "123456789012"
    },

    "Ngày bắt đầu": {
        "type": "date",
        "description": "Start date of treatment or leave, usually after 'Từ ngày' or 'Bắt đầu ngày'. Format DD/MM/YYYY.",
        "example": "01/01/2023"
    },

    "Ngày kết thúc": {
        "type": "date",
        "description": "End date of treatment or leave, usually after 'đến ngày' or 'đến hết ngày'. Format DD/MM/YYYY.",
        "example": "05/01/2023"
    },

    "Tổng số ngày": {
        "type": "number",
        "description": "Total days of treatment or leave. Use value from document, or calculate as (end date - start date + 1).",
        "example": 5
    },

    "Ngày vào viện": {
        "type": "date",
        "description": "Admission date, found after 'Vào viện' or similar. Ignore time details like 'giờ', 'phút'. Output as DD/MM/YYYY. Fix OCR errors if obvious.",
        "example": "25/09/2025"
    },

    "Mã bệnh": {
        "type": "string",
        "description": "ICD disease code(s) from diagnosis, separated by semicolons (;). Each code starts with a letter followed by digits (e.g. A00, B00.1). If the first character is 0, correct to O.",
        "example": "A00;B00.1;S92.4;O54;O84.1"
    },

    "Tên bệnh": {
        "type": "string",
        "description": "Full disease name(s) and ICD code(s) from the diagnosis section (e.g. after 'Chẩn đoán', 'Kết luận'). Include all diseases and codes, separated by semicolons (;). Fix OCR errors if the intended text is clear.",
        "example": "Mắt trái: Chắp (H00.1); Bệnh khác của tuyến lệ (H04.1)"
    },

    "Ngày tháng năm sinh của con": {
        "type": "date",
        "description": "Date of birth in DD/MM/YYYY format, found after 'Ngày, tháng, năm sinh:' or similar.",
        "example": "01/01/2000"
    },

    "Ghi chú": {
        "type": "string",
        "description": "Extract text after 'Ghi chú'. Usually near the end of the document, containing notes or follow-up instructions. Capture full sentence or paragraph, including punctuation or dates.",
        "example": "Toa về. Tái khám sau 3 ngày. Nghỉ thêm 2 ngày từ 21/8/2025 đến 22/08/2025."
    },

    "Họ và Tên Cha": {
        "type": "string",
        "description": "Father's full name in uppercase. Appears after 'Họ tên cha','Họ, chữ đệm, tên người cha', 'Tên cha', or 'Cha'. If not found, return 'N/A'.",
        "example": "NGUYỄN VĂN B"
    },

    "Họ và Tên Mẹ": {
        "type": "string",
        "description": "Mother's full name in uppercase. Appears after 'Họ tên mẹ','Họ, chữ đệm, tên người mẹ', 'Tên mẹ', or 'Mẹ'. If not found, return 'N/A'.",
        "example": "TRẦN THỊ CHÂN"
    },

    "Số con sinh": {
        "type": "number",
        "description": "Extract the number of children born in this delivery. Usually appears after the phrase 'Số con trong lần sinh này'. Output only the numeric value (e.g. '1', '2'). Fix OCR errors if obvious.",
        "example": 1
    },
    "Ngày sinh con": {
        "type": "date",
        "description": "Child birth date. Appears after phrases like 'Đã sinh con vào lúc', followed by time and date. Ignore time (giờ, phút) and return date in DD/MM/YYYY format. Fix OCR errors if clear (e.g. '18 tháng 07 năm 2025' → '18/07/2025').",
        "example": "18/07/2025"
    }
}


