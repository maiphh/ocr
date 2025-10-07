BHXH_SCHEMA = {
    "Họ và tên": {
        "type": "string",
        "required": True,
        "description": "Full name of the patient"
    },
    "Ngày sinh": {
        "type": "date",
        "required": True,
        "format": "iso-date",
        "description": "Date of birth in DD/MM/YYYY format"
    },
    "Mã BHXH/BHYT": {
        "type": "string",
        "required": True,
        "description": "BHXH or BHYT ID number (extract number after BHXH or BHYT phrase)"
    },
    "Loại yêu cầu": {
        "type": "string",
        "required": False,
        "nullable": True,
        "description": "Request type - placeholder N/A if not available"
    },
    "Loại hệ thống": {
        "type": "string",
        "required": False,
        "nullable": True,
        "description": "System type - placeholder N/A if not available"
    },
    "Nhóm quyền lợi": {
        "type": "string",
        "required": False,
        "nullable": True,
        "description": "Benefit group - placeholder N/A if not available"
    },
    "CCCD/CMND": {
        "type": "string",
        "required": False,
        "nullable": True,
        "description": "Personal ID - CCCD/CMND number (extract number after CCCD or CMND phrase)"
    },
    "Ngày bắt đầu": {
        "type": "date",
        "required": True,
        "format": "iso-date",
        "description": "Start date of treatment in DD/MM/YYYY format"
    },
    "Ngày kết thúc": {
        "type": "date",
        "required": True,
        "format": "iso-date",
        "description": "End date of treatment in DD/MM/YYYY format"
    },
    "Tổng số ngày": {
        "type": "number",
        "required": True,
        "description": "Total days of treatment (calculated as end date - start date)"
    },
    "Mã bệnh": {
        "type": "string",
        "required": False,
        "nullable": True,
        "description": "Disease code(s) from diagnosis. Multiple codes separated by semicolon;"
    },
    "Tên bệnh": {
        "type": "string",
        "required": False,
        "nullable": True,
        "description": """
        Disease name(s) from diagnosis. Multiple names separated by semicolon; 
        This field may have mistakes, misspelled, or noise since it is extracted from OCR text, fix and clean this field if there is a clear fix.
        """
    },
    "Số serial": {
        "type": "string",
        "required": False,
        "nullable": True,
        "description": "Document serial number, usually appears at the top"
    },
    "OCR Score": {
        "type": "string",
        "required": False,
        "nullable": True,
        "description": "OCR confidence score of the document"
    },

}