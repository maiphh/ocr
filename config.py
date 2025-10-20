BHXH_SCHEMA = {
  "Loại giấy tờ": {
    "type": "string",
    "description": "Extract the document type exactly as it appears inside the '<section_header_level_1>' tag in the Docling Serve output. This is usually a large, uppercase phrase at the top of the document, starting with GIẤY or GIAY (e.g., 'GIẤY CHỨNG SINH', 'GIẤY CHỨNG NHẬN NGHỈ VIỆC HƯỞNG BHXH', 'GIẤY KHAI SINH', 'GIẤY RA VIỆN')."
},

"Số seri": {
  "type": "string",
  "description": "Extract the unique document serial number with the following priority: (1) If the phrase 'Mã Y tế' or 'Số seri' appears, extract the number immediately following either of these phrases; (2) If neither is found, extract the number after 'Số'or any alternatives. This number is usually found at the top of the page, near the document title. Example: '18232386'."
},

  "Họ và tên người bệnh": {
    "type": "string",
    "description": "Full name of the patient, in uppercase and with spaces between words. Usually appears after phrases like 'Họ tên', 'Người bệnh', or 'Chủ thẻ'. For 'Giấy chứng sinh', this field may be omitted."
  },

  "Mã BHXH": {
    "type": "string",
    "description": "Vietnamese Social Insurance Number (BHXH), always 10 consecutive digits. Typically appears after phrases like 'Mã BHXH', 'Số BHXH', or within a combined string such as 'Mã số BHXH/Thẻ BHYT số: ...'. If multiple numbers are present, select the 10-digit sequence.Example: in 'Mã số BHXH/Thẻ BHYT số: DN475912213507875297', the BHXH number is '9122135078'."
  },

  "Mã BHYT": {
    "type": "string",
    "description": "Vietnamese Health Insurance Card Number (BHYT), usually starts with two uppercase letters followed by digits (e.g., 'DN475912213507875297'). Often found after phrases like 'BHYT', 'Mã thẻ', or 'Số thẻ'. Extract the full code, and if there are multiple, select the one containing the 'Mã BHXH' as its middle part."
  },

  "CCCD/CMND": {
    "type": "string",
    "description": "Vietnamese National ID (CCCD), Citizen ID (CMND), or Passport number. Extract the number following phrases like 'CCCD', 'CMND', 'Số định danh cá nhân', or 'Hộ chiếu'. Select the 12-digit sequence.Example: '056325003858'. If not found, return 'Not Found'."
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

  "Ngày bắt đầu": {
    "type": "date",
    "description": "Start date of treatment or leave, usually after phrases like 'Từ ngày' or 'Bắt đầu ngày'. Format: DD/MM/YYYY. Ignore if only month/year is present."
  },

  "Ngày kết thúc": {
    "type": "date",
    "description": "End date of treatment or leave, usually after phrases like 'đến ngày' or 'đến hết ngày'. Format: DD/MM/YYYY."
  },

  "Tổng số ngày": {
    "type": "number",
    "description": "Total number of days for treatment or leave. Use the value stated in the document, or calculate as (End Date - Start Date + 1). Prefer the explicitly stated value if available."
  },

  "Ngày vào viện": {
    "type": "date",
    "description": "Usually for 'Giấy Ra Viện' type, Date of hospital admission, found after phrases like 'Vào viện' or 'Ngày vào viện'. Ignore time details such as hour or minute. Format: DD/MM/YYYY."
  },


  "Ghi chú": {
    "type": "string",
    "description": "Extract the text after 'Ghi chú'. Usually located near the end of the document, containing instructions or follow-up information. Capture the full sentence or paragraph, including punctuation and dates."
  },

"Ngày sinh của con": {
    "type": "date",
    "description": "Date of birth of the child, in DD/MM/YYYY format, found after phrases like 'Ngày, tháng, năm sinh:' or similar."
  },

  "Họ và Tên Mẹ": {
    "type": "string",
    "description": "Full name of the mother, in uppercase. Appears after phrases like 'Họ tên mẹ', 'Họ, chữ đệm, tên người mẹ', 'Tên mẹ', or 'Mẹ'. If not found, return 'N/A'."
  },

  "Họ và Tên Cha": {
    "type": "string",
    "description": "Full name of the father, in uppercase. Appears after phrases like 'Họ tên cha', 'Họ, chữ đệm, tên người cha', 'Tên cha', or 'Cha'. If not found, return 'N/A'."
  },

  "Số con sinh": {
    "type": "number",
    "description": "Number of children born in this delivery, usually after the phrase 'Số con trong lần sinh này'. Output only the numeric value (e.g., 1, 2). Correct OCR errors if the intended value is clear."
  },

  "Ngày sinh con": {
    "type": "date",
    "description": "Date of the child's birth, found after phrases like 'Đã sinh con vào lúc', followed by time and date. Ignore the time (hour, minute) and return the date in DD/MM/YYYY format. Correct OCR errors if the intended date is clear (e.g., '18 tháng 07 năm 2025' → '18/07/2025')."
  }
}


