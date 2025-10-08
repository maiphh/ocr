BHXH_SCHEMA = {
    "Họ và tên": {
        "type": "string",
        "required": True,
        "description": "Full name, in capital letters, white space between.",
        "example": "NGUYỄN VĂN A"
    },
    "Ngày sinh": {
        "type": "date",
        "required": True,
        "description": "Date of birth in DD/MM/YYYY format",
        "example": "01/01/2000"
    },
    "Mã BHXH": {
        "type": "string",
        "required": True,
        "description": "BHXH ID number (extract number after BHXH phrase). 10 digits, start with digit only, e.g. 3291759237, if start with DN that is BHYT ID, not BHXH ID -> don't take it",
        "example": "1234567890"
    },

    "Mã BHYT": {
        "type": "string",
        "required": True,
        "description": "BHYT ID number (extract number after BHYT phrase).Start with DN + 13 digits, e.g. DN1234567890123. We only take the last 10 number: 7890123",
        "example": "7890123"
    },

    "Loại yêu cầu": {
        "type": "string",
        "required": False,
        "nullable": True,
        "description": "this is a placeholder, put N/A"
    },
    "Loại hệ thống": {
        "type": "string",
        "required": False,
        "nullable": True,
        "description": "this is a placeholder, put N/A"
    },
    "Nhóm quyền lợi": {
        "type": "string",
        "required": False,
        "nullable": True,
        "description": "this is a placeholder, put N/A"
    },
    "CCCD/CMND": {
        "type": "string",
        "required": True,
        "nullable": True,
        "description": "Personal ID - CCCD/CMND number (extract number after CCCD/CMND/Định danh công dân/Hộ chiếu phrase), number of digits may vary, if no ID are found, use N/A",
        "example": "123456789012"
    },
    "Ngày bắt đầu": {
        "type": "date",
        "required": True,
        "description": "Start date of treatment in DD/MM/YYYY format",
        "example": "01/01/2023"
    },
    "Ngày kết thúc": {
        "type": "date",
        "required": True,
        "description": "End date of treatment in DD/MM/YYYY format",
        "example": "05/01/2023"
    },
    "Tổng số ngày": {
        "type": "number",
        "required": True,
        "description": "Total days of treatment, can be extract from documents, if not available, calculate as (end date - start date + 1)",
        "example": 5 
    },
    "Mã bệnh": {
        "type": "string",
        "required": False,
        "nullable": True,
        "description": "Disease code(s) from diagnosis. Multiple codes separated by semicolon;",
        "example": "A00;B00.1"
        
    },
    "Tên bệnh": {
        "type": "string",
        "required": False,
        "nullable": True,
        "description": """
        Disease name(s) from diagnosis. Multiple names separated by semicolon; 
        This field may have mistakes, misspelled, or noise since it is extracted from OCR text, fix and clean this field if there is a clear fix.
        """,
        "example": "Sốt xuất huyết;Cúm A"
    },
    "Số serial": {
        "type": "string",
        "required": False,
        "nullable": True,
        "description": "Document serial number, usually appears at the top. Usually after phrases like: Số, Ký hiệu, Serial, Seri, Số hiệu, No., No, Số TT, Số thứ tự, Số hiệu phiếu, Số phiếu, Số chứng từ, Số CT, Mã Y tế,...",
        "example": "123456789"
    },
    "Ghi chú" : {
        "type": "string",
        "required": False,
        "nullable": True,
        "description": "Notes, place to put any additional information or remarks. Usually after phrases like: Ghi chú, Lưu ý, Note, Remarks, Additional information,...",
        "example": "Nghỉ 3 ngày từ ngày 01/01/2023 đến 03/01/2023"
    }

}

