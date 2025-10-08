BHXH_SCHEMA = {
    "Họ và tên": {
        "type": "string",
        "description": "Full name, in capital letters, white space between. This name is the name of the person that the document is about. There may be multiple names, take the main name that appear first. Usually appear after phrase like Họ tên, Tên, Người bệnh, Bệnh nhân, Người được cấp thẻ, Người tham gia, Chủ thẻ,... or similar phrases.",
        "example": "NGUYỄN VĂN A"
    },
    "Ngày sinh": {
        "type": "date",
        "description": "Date of birth in DD/MM/YYYY format",
        "example": "01/01/2000"
    },
    "Mã BHXH": {
        "type": "string",
        "description": "BHXH ID number (extract number after BHXH phrase). 10 digits, start with digit only, e.g. 3291759237, if start with DN that is BHYT ID, not BHXH ID -> don't take it",
        "example": "1234567890"
    },

    "Mã BHYT": {
        "type": "string",
        "description": "BHYT ID number. Appear after phrase like: BHYT, Mã thẻ, Thẻ, ... .Start with 2 letters + digits, e.g. DN123456789012342. We only take 10 digits from 4 -> 4 number: 4567890123",
        "example": "4567890123"
    },

    "Loại yêu cầu": {
        "type": "string",
        "description": "this is a placeholder, put N/A"
    },
    "Loại hệ thống": {
        "type": "string",
        "description": "this is a placeholder, put N/A"
    },
    "Nhóm quyền lợi": {
        "type": "string",
        "description": "this is a placeholder, put N/A"
    },
    "CCCD/CMND": {
        "type": "string",
        "description": "Personal ID - CCCD/CMND number (extract number after CCCD/CMND/Định danh công dân/Hộ chiếu phrase), number of digits may vary, if no ID are found, use N/A",
        "example": "123456789012"
    },
    "Ngày bắt đầu": {
        "type": "date",
        "description": "Start date of treatment in DD/MM/YYYY format",
        "example": "01/01/2023"
    },
    "Ngày kết thúc": {
        "type": "date",
        "description": "End date of treatment in DD/MM/YYYY format",
        "example": "05/01/2023"
    },
    "Tổng số ngày": {
        "type": "number",
        "description": "Total days of treatment, can be extract from documents, if not available, calculate as (end date - start date + 1)",
        "example": 5 
    },
    "Mã bệnh": {
        "type": "string",
        "description": "Disease code(s) from diagnosis. Multiple codes separated by semicolon;",
        "format": "letter + digits (e.g. A00;B00.1;S92.4). The first character is always a letter, if it is a digit like 0, it is likely a OCR error, fix it to O",
        "example": "A00;B00.1;S92.4; O54; O84.1"
        
    },
    "Tên bệnh": {
        "type": "string",
        "important": True,
        "description": """
        Disease name(s) from diagnosis. Multiple names separated by semicolon (;). Take any information that relavent to disease/diagnosis. This is a important field so try harder to get information about this field.
        This information may appear after phrase like: Chẩn đoán, Chuẩn đoán, Kết luận, Bệnh, or similar phrases.

        This field may have mistakes, misspelled, or noise since it is extracted from OCR text, fix and clean this field if there is a clear fix.
        """,
        "example": "Sốt xuất huyết;Cúm A; Nhiễm trùng đường ruột, xác định khác"
    },

    "Họ và Tên Cha": {
        "type": "string",
        "description": "Father's full name, in capital letters, white space between. Usually appear in document after phrase like Họ tên cha, Họ tên bố, Tên cha, Tên bố, Cha, Bố,... or similar phrases. If not found, put N/A",
        "example": "NGUYỄN VĂN B"
    },
    "Họ và Tên Mẹ": {
        "type": "string",
        "description": "Mother's full name, in capital letters, white space between. Usually appear in document after phrase like Họ tên mẹ, Tên mẹ, Mẹ,... or similar phrases. If not found, put N/A",
        "example": "TRẦN THỊ C"
    },
    "CCCD/CMND Mẹ": {
        "type": "string",
        "description": "Mother's Personal ID - CCCD/CMND number (extract number after CCCD/CMND/Định danh công dân/Hộ chiếu phrase), number of digits may vary, if no ID are found, use N/A",
        "example": "123456789012"
    },

    "BHYT Mẹ": {
        "type": "string",
        "description": "Mother's BHYT ID number. Appear after phrase like: BHYT, Mã thẻ, Thẻ, ... .Start with 2 letters + digits, e.g. DN123456789012342. We only take 10 digits from 4 -> 14 number: 4567890123. If not found, put N/A",
        "example": "4567890123"
    },

    "BHXH Mẹ": {
        "type": "string",
        "description": "Mother's BHXH ID number (extract number after BHXH phrase). 10 digits, start with digit only, e.g. 3291759237, if start with 2 digits that is BHYT ID, not BHXH ID -> don't take it. If not found, put N/A",
        "example": "1234567890"
    },

    "Số serial": {
        "type": "string",
        "description": "Document serial number, usually appears at the top. Usually after phrases like: Số, Ký hiệu, Serial, Seri, Số hiệu, No., No, Số TT, Số thứ tự, Số hiệu phiếu, Số phiếu, Số chứng từ, Số CT, Mã Y tế,...",
        "example": "123456789"
    },
    "Ghi chú" : {
        "type": "string",
        "description": "Notes, place to put any additional information or remarks. This is a open field, take any information that add context to the case. For example: address, workplace, position, relationship with patient, contact phone, contact email, ...",
        "example": "Nghỉ 3 ngày từ ngày 01/01/2023 đến 03/01/2023,, Địa chỉ, Đơn vị công tác, Chức vụ, Quan hệ với người bệnh, Số điện thoại liên hệ, Email liên hệ, ..."
    }

}

